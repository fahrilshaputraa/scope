from django import forms
from django.template.loader import render_to_string

from apps.richtext import RICH_FIELDS


class SearchableCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    is_picker = True

    def render(self, name, value, attrs=None, renderer=None):
        context = self.get_context(name, value, attrs)
        context["widget"]["picker_label"] = self.attrs.get("aria-label", "Pilihan")
        return render_to_string("widgets/choice_picker.html", context)


def fill_missing_defaults(form, names):
    """Keep model/initial defaults when a compact form omits planning fields."""
    if not form.is_bound:
        return
    data = form.data.copy()
    for name in names:
        if name in form.fields and name not in data:
            value = form.initial.get(name, getattr(form.instance, name, None))
            value = form.fields[name].prepare_value(value)
            data[name] = "" if value is None else str(value)
    form.data = data


def style_form(form, primary=None):
    labels = {
        "name": "Nama",
        "code": "Kode project",
        "description": "Deskripsi",
        "manager": "Project Manager",
        "members": "Anggota project",
        "team": "Tim",
        "current_phase": "Tahap saat ini",
        "start_date": "Tanggal mulai",
        "end_date": "Tanggal selesai",
        "target_end_date": "Target selesai",
        "due_date": "Target selesai",
        "progress_override": "Penyesuaian progress PM (%)",
        "sequence": "Urutan phase",
        "date": "Tanggal",
        "planned_percent": "Planned progress (%)",
        "title": "Judul",
        "content": "Isi",
        "tags": "Tags",
        "assignee": "Dikerjakan oleh",
        "collaborators": "Rekan pengerjaan (opsional)",
        "weight": "Bobot",
        "progress": "Progress (%)",
        "priority": "Prioritas",
        "severity": "Tingkat dampak",
        "owner": "Penanggung jawab",
        "blocked_reason": "Alasan hambatan",
        "blocked_dependency": "Menunggu siapa?",
        "order": "Urutan pekerjaan",
        "parent_task": "Activity induk",
        "dependencies": "Task prasyarat",
        "baseline_start_date": "Baseline mulai",
        "baseline_end_date": "Baseline selesai",
        "mitigation": "Rencana mitigasi",
        "resolution": "Resolusi",
        "decision": "Keputusan",
        "reason": "Alasan",
        "context": "Konteks",
        "impact": "Dampak",
        "decision_maker": "Pembuat keputusan",
        "first_name": "Nama depan",
        "last_name": "Nama belakang",
        "username": "Nama pengguna",
        "email": "Surel",
        "role": "Peran",
        "is_active": "Akun aktif",
        "display_name": "Nama tampilan",
        "job_title": "Jabatan",
        "password1": "Kata sandi",
        "password2": "Konfirmasi kata sandi",
        "new_password1": "Kata sandi baru",
        "new_password2": "Konfirmasi kata sandi baru",
    }
    for name, field in form.fields.items():
        field.label = labels.get(name, field.label)
    for name, field in form.fields.items():
        if isinstance(field, forms.ModelChoiceField):
            multiple = isinstance(field, forms.ModelMultipleChoiceField)
            field.empty_label = None if multiple else "Belum dipilih"
            if field.queryset.model._meta.label == "auth.User":
                if not multiple:
                    field.empty_label = "Belum ditugaskan"
                field.queryset = field.queryset.select_related("pcc_profile").order_by(
                    "first_name", "username"
                )
                field.label_from_instance = lambda user: (
                    f"{user.pcc_profile.name} ({user.username})"
                    if user.pcc_profile.name != user.username
                    else user.username
                )
        if isinstance(field, forms.ModelMultipleChoiceField):
            field.widget = SearchableCheckboxSelectMultiple(attrs={"aria-label": field.label})
            field.widget.choices = field.choices
        if isinstance(field, forms.DateField):
            field.widget = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
        if isinstance(field.widget, forms.HiddenInput):
            continue
        described_by = []
        if field.help_text:
            described_by.append("help-" + name)
        if form.is_bound and name in form.errors:
            described_by.append("error-" + name)
        if described_by:
            field.widget.attrs["aria-describedby"] = " ".join(described_by)
        if field.required:
            field.widget.attrs["aria-required"] = "true"
        if form.is_bound and name in form.errors:
            field.widget.attrs["aria-invalid"] = "true"
        if isinstance(field.widget, (forms.CheckboxSelectMultiple, forms.CheckboxInput)):
            continue
        field.widget.attrs["class"] = "pcc-field"
        if isinstance(field.widget, forms.SelectMultiple):
            field.widget.attrs["style"] = "min-height: 120px"
        if isinstance(field.widget, forms.Textarea):
            field.widget.attrs["rows"] = 4
            if name in RICH_FIELDS:
                field.widget.attrs["data-wysiwyg"] = "true"

    visible = list(form.visible_fields())
    form.primary_fields = [f for f in visible if primary is None or f.name in primary]
    form.extra_fields = [f for f in visible if primary is not None and f.name not in primary]
    form.extra_errors = form.is_bound and any(f.errors for f in form.extra_fields)
