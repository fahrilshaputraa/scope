"""Halaman Template project (Admin, ``template.manage``) dan field tambahan project."""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.form_widgets import style_form
from apps.identity.permissions import can_manage_project
from apps.identity.roles import has_perm

from .models import ActivityAction, ProjectTemplate, ProjectType, WeightMode
from .project_templates import (
    field_definitions_text,
    outline_to_structure,
    parse_field_definitions,
    save_project_as_template,
    structure_summary,
    structure_to_outline,
)
from .services import record_activity
from .views import _project_or_404


def _require_templates(user):
    if not has_perm(user, "template.manage"):
        raise PermissionDenied


class TemplateForm(forms.Form):
    name = forms.CharField(max_length=200, label="Nama template")
    project_type = forms.ChoiceField(choices=ProjectType.choices, label="Jenis project")
    outline = forms.CharField(
        widget=forms.Textarea,
        required=False,
        label="Struktur (outline)",
        help_text="Baris biasa = phase, + work package, - task | hari, -- detail | hari, "
        "* milestone | hari ke-n. Contoh: '- Analisis kebutuhan | 5'.",
    )
    description = forms.CharField(widget=forms.Textarea, required=False, label="Deskripsi")
    weight_mode = forms.ChoiceField(choices=WeightMode.choices, label="Mode bobot")
    fields_text = forms.CharField(
        widget=forms.Textarea,
        required=False,
        label="Field tambahan",
        help_text="Satu per baris: 'Label | teks', 'Label | angka', atau 'Label | tanggal'.",
    )
    is_active = forms.BooleanField(
        required=False, initial=True, label="Bisa dipilih saat membuat project"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self, primary=["name", "project_type", "outline"])
        self.fields["outline"].widget.attrs["rows"] = 12
        self.fields["outline"].widget.attrs["placeholder"] = (
            "Perencanaan\n- Kickoff | 2\nPengembangan\n+ Backend\n- API | 10\n* Go-live | 30"
        )

    def clean_outline(self):
        text = self.cleaned_data["outline"]
        self.structure = outline_to_structure(text)
        return text

    def clean_fields_text(self):
        self.custom_fields = parse_field_definitions(self.cleaned_data["fields_text"])
        return self.cleaned_data["fields_text"]


@login_required
def template_list(request):
    _require_templates(request.user)
    templates = list(ProjectTemplate.objects.select_related("created_by__pcc_profile"))
    for template in templates:
        template.summary = structure_summary(template.structure_config or {})
        template.project_count = template.projects.count()
    return render(request, "projects/templates/list.html", {"templates": templates})


def _initial(template):
    return {
        "name": template.name,
        "project_type": template.project_type,
        "outline": structure_to_outline(template.structure_config or {}),
        "description": template.description,
        "weight_mode": template.weight_mode,
        "fields_text": field_definitions_text(template.custom_fields or []),
        "is_active": template.is_active,
    }


@login_required
def template_edit(request, tid=None):
    _require_templates(request.user)
    template = get_object_or_404(ProjectTemplate, pk=tid) if tid else None
    initial = (
        _initial(template) if template else {"weight_mode": WeightMode.AUTO, "is_active": True}
    )
    form = TemplateForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        template = template or ProjectTemplate(created_by=request.user)
        content_changed = template.pk and (
            data["outline"].strip() != initial["outline"].strip()
            or form.custom_fields != (template.custom_fields or [])
            or data["weight_mode"] != template.weight_mode
        )
        if not template.pk or data["outline"].strip() != initial.get("outline", "").strip():
            template.structure_config = form.structure
        template.name = data["name"]
        template.project_type = data["project_type"]
        template.description = data["description"]
        template.weight_mode = data["weight_mode"]
        template.custom_fields = form.custom_fields
        template.is_active = data["is_active"]
        if content_changed:
            template.version += 1
        template.save()
        messages.success(
            request,
            f"Template disimpan (v{template.version}). Project yang sudah dibuat tidak berubah.",
        )
        return redirect("projects:template_list")
    return render(
        request,
        "governance/form.html",
        {
            "form": form,
            "title": template.name if template else "Template baru",
            "subtitle": "Template project",
            "back_url": reverse("projects:template_list"),
        },
    )


@login_required
@require_POST
def template_delete(request, tid):
    _require_templates(request.user)
    template = get_object_or_404(ProjectTemplate, pk=tid)
    template.delete()  # project yang memakai template ini tetap utuh (SET_NULL)
    messages.success(request, "Template dihapus. Project yang dibuat darinya tidak berubah.")
    return redirect("projects:template_list")


class SaveAsTemplateForm(forms.Form):
    name = forms.CharField(max_length=200, label="Nama template")
    description = forms.CharField(widget=forms.Textarea, required=False, label="Deskripsi")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self)


@login_required
def project_save_template(request, pk):
    project = _project_or_404(request, pk)
    _require_templates(request.user)
    form = SaveAsTemplateForm(request.POST or None, initial={"name": f"Template {project.name}"})
    if request.method == "POST" and form.is_valid():
        template = save_project_as_template(
            project, form.cleaned_data["name"], request.user, form.cleaned_data["description"]
        )
        record_activity(
            project,
            request.user,
            ActivityAction.TEMPLATE_APPLIED,
            f'Struktur project disimpan sebagai template "{template.name}".',
        )
        messages.success(request, f"Template {template.name} dibuat dari project ini.")
        return redirect("projects:template_list")
    return render(
        request,
        "governance/form.html",
        {
            "form": form,
            "project": project,
            "title": "Simpan sebagai template",
            "subtitle": f"{project.name} · phase, work package, task, milestone, dan aturan",
            "back_url": reverse("projects:project_detail", args=[project.pk]),
        },
    )


# ----------------------------------------------------------- custom fields ---


class CustomFieldsForm(forms.Form):
    definitions = forms.CharField(
        widget=forms.Textarea,
        required=False,
        label="Daftar field",
        help_text="Satu per baris: 'Label | teks', 'Label | angka', atau 'Label | tanggal'.",
    )

    def __init__(self, *args, project, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        kinds = {"text": forms.CharField, "number": forms.DecimalField, "date": forms.DateField}
        for field in project.custom_fields or []:
            klass = kinds.get(field["type"], forms.CharField)
            extra = {"max_length": 300} if klass is forms.CharField else {}
            self.fields["cf_" + field["key"]] = klass(required=False, label=field["label"], **extra)
            self.initial["cf_" + field["key"]] = (project.custom_values or {}).get(field["key"])
        self.initial["definitions"] = field_definitions_text(project.custom_fields or [])
        style_form(self)

    def clean_definitions(self):
        try:
            self.parsed = parse_field_definitions(self.cleaned_data["definitions"])
        except ValidationError as exc:
            raise forms.ValidationError(exc.messages) from exc
        return self.cleaned_data["definitions"]

    def values(self):
        result = {}
        keys = {f["key"] for f in self.parsed}
        for name, value in self.cleaned_data.items():
            if name.startswith("cf_") and name[3:] in keys and value not in (None, ""):
                result[name[3:]] = str(value)
        return result


@login_required
def project_custom_fields(request, pk):
    project = _project_or_404(request, pk)
    if not can_manage_project(request.user, project):
        raise PermissionDenied
    form = CustomFieldsForm(request.POST or None, project=project)
    if request.method == "POST" and form.is_valid():
        project.custom_fields = form.parsed
        project.custom_values = form.values()
        project.save(update_fields=["custom_fields", "custom_values", "updated_at"])
        record_activity(
            project, request.user, ActivityAction.PROJECT_UPDATED, "Field tambahan diperbarui."
        )
        messages.success(request, "Field tambahan disimpan.")
        return redirect("projects:project_detail", pk=project.pk)
    return render(
        request,
        "governance/form.html",
        {
            "form": form,
            "project": project,
            "title": "Field tambahan",
            "subtitle": project.name,
            "back_url": reverse("projects:project_detail", args=[project.pk]),
        },
    )
