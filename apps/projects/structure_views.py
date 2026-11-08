"""Struktur project: phase → work package → task → subtask, bobot, dan metode progress.

R7.2–R7.4. Halaman ini juga menjadi tempat mengatur mode bobot dan persentase metode
status-based per project.
"""

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
from apps.work import weights as weight_service
from apps.work.models import STATUS_PROGRESS_DEFAULTS, Task

from .models import ActivityAction, WeightMode, WorkPackage
from .services import record_activity
from .views import _project_or_404, project_context


def can_edit_structure(user, project) -> bool:
    return has_perm(user, "structure.update") and can_manage_project(user, project)


def _require_edit(request, project):
    if not can_edit_structure(request.user, project):
        raise PermissionDenied


class WorkPackageForm(forms.ModelForm):
    class Meta:
        model = WorkPackage
        fields = ["name", "phase", "start_date", "end_date", "sequence", "description"]

    def __init__(self, *args, project, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.project = project
        self.fields["phase"].queryset = project.phases.all()
        style_form(self, primary=["name", "phase", "start_date", "end_date"])
        self.fields["name"].label = "Nama work package"
        self.fields["sequence"].label = "Urutan"
        self.fields["phase"].label = "Phase"
        self.fields["name"].widget.attrs["placeholder"] = "Contoh: Pengembangan backend"


class ProgressSettingsForm(forms.Form):
    weight_mode = forms.ChoiceField(choices=WeightMode.choices, label="Mode bobot")
    in_progress = forms.DecimalField(
        min_value=0, max_value=100, decimal_places=2, label="Progress saat Sedang dikerjakan (%)"
    )
    review = forms.DecimalField(
        min_value=0, max_value=100, decimal_places=2, label="Progress saat Menunggu pemeriksaan (%)"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self)
        self.fields[
            "weight_mode"
        ].help_text = (
            "Otomatis: setiap task baru atau diarsipkan membuat bobot kelompoknya dibagi rata."
        )
        self.fields["review"].help_text = (
            "Berlaku untuk task bermetode Berdasarkan status. Backlog/To Do 0%, Done 100%, "
            "Terhambat mempertahankan progress terakhir."
        )


class GroupWeightsForm(forms.Form):
    def __init__(self, *args, tasks, **kwargs):
        super().__init__(*args, **kwargs)
        self.tasks = tasks
        for task in tasks:
            self.fields[f"w{task.pk}"] = forms.DecimalField(
                min_value=0, max_value=100, decimal_places=2, label=task.title, initial=task.weight
            )
        style_form(self)

    def clean(self):
        data = super().clean()
        values = [data.get(f"w{t.pk}") for t in self.tasks]
        if all(v is not None for v in values):
            try:
                weight_service.validate_manual(values)
            except ValidationError as exc:
                raise forms.ValidationError(exc.messages) from exc
        return data

    def weights(self):
        return [self.cleaned_data[f"w{t.pk}"] for t in self.tasks]


def _tree(project):
    phases = list(project.phases.all())
    packages = list(project.work_packages.select_related("phase"))
    tasks = list(
        Task.objects.filter(project=project, parent_task__isnull=True)
        .select_related("assignee__pcc_profile", "work_package")
        .prefetch_related("subtasks")
        .order_by("order", "pk")
    )

    def task_rows(items):
        return [{"task": t, "details": list(t.subtasks.all())} for t in items]

    def package_rows(phase_id):
        return [
            {"package": wp, "tasks": task_rows([t for t in tasks if t.work_package_id == wp.pk])}
            for wp in packages
            if wp.phase_id == phase_id
        ]

    tree = [
        {
            "phase": phase,
            "packages": package_rows(phase.pk),
            "tasks": task_rows(
                [t for t in tasks if t.phase_id == phase.pk and not t.work_package_id]
            ),
        }
        for phase in phases
    ]
    loose_packages = package_rows(None)
    loose = task_rows([t for t in tasks if not t.phase_id and not t.work_package_id])
    if loose_packages or loose:
        tree.append({"phase": None, "packages": loose_packages, "tasks": loose})
    return tree


@login_required
def project_structure(request, pk):
    project = _project_or_404(request, pk)
    if not has_perm(request.user, "structure.view"):
        raise PermissionDenied
    config = {**STATUS_PROGRESS_DEFAULTS, **(project.progress_config or {})}
    return render(
        request,
        "projects/project/structure.html",
        {
            **project_context(request, project, "structure"),
            "tree": _tree(project),
            "groups": weight_service.groups(project),
            "can_edit": can_edit_structure(request.user, project),
            "status_config": config,
        },
    )


def _form_page(request, project, form, title):
    return render(
        request,
        "governance/form.html",
        {
            "form": form,
            "project": project,
            "title": title,
            "subtitle": project.name,
            "back_url": reverse("projects:project_structure", args=[project.pk]),
        },
    )


@login_required
def work_package_edit(request, pk, wp_id=None):
    project = _project_or_404(request, pk)
    _require_edit(request, project)
    package = get_object_or_404(WorkPackage, pk=wp_id, project=project) if wp_id else None
    form = WorkPackageForm(request.POST or None, instance=package, project=project)
    if request.method == "POST" and form.is_valid():
        package = form.save()
        if package.phase_id:
            Task.objects.filter(work_package=package).update(phase_id=package.phase_id)
        record_activity(
            project,
            request.user,
            ActivityAction.STRUCTURE_UPDATED,
            f'Work package "{package.name}" {"diperbarui" if wp_id else "ditambahkan"}.',
        )
        messages.success(request, "Work package disimpan.")
        return redirect("projects:project_structure", pk=project.pk)
    return _form_page(
        request, project, form, "Edit work package" if wp_id else "Tambah work package"
    )


@login_required
@require_POST
def work_package_delete(request, pk, wp_id):
    project = _project_or_404(request, pk)
    _require_edit(request, project)
    package = get_object_or_404(WorkPackage, pk=wp_id, project=project)
    name = package.name
    package.delete()  # task tetap ada, hanya kehilangan pengelompokan
    record_activity(
        project,
        request.user,
        ActivityAction.STRUCTURE_UPDATED,
        f'Work package "{name}" dihapus; task di dalamnya tetap tersimpan.',
    )
    messages.success(request, "Work package dihapus. Task di dalamnya tidak terhapus.")
    return redirect("projects:project_structure", pk=project.pk)


def _parent_id(request):
    value = request.POST.get("parent") or request.GET.get("parent") or ""
    return int(value) if value.isdigit() else None


@login_required
@require_POST
def weights_action(request, pk):
    project = _project_or_404(request, pk)
    _require_edit(request, project)
    parent_id = _parent_id(request)
    action = request.POST.get("action")
    try:
        if action == "equalize":
            weight_service.equalize(project, parent_id, request.user)
        elif action == "normalize":
            weight_service.normalize(project, parent_id, request.user)
        else:
            raise ValidationError("Aksi bobot tidak dikenal.")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Bobot diperbarui. Total kelompok sekarang 100%.")
    return redirect("projects:project_structure", pk=project.pk)


@login_required
def weights_edit(request, pk):
    project = _project_or_404(request, pk)
    _require_edit(request, project)
    parent_id = _parent_id(request)
    tasks = weight_service.group_tasks(project, parent_id)
    form = GroupWeightsForm(request.POST or None, tasks=tasks)
    if request.method == "POST" and form.is_valid():
        try:
            weight_service.set_weights(project, tasks, form.weights(), request.user)
        except ValidationError as exc:
            form.add_error(None, exc.messages)
        else:
            if project.weight_mode == WeightMode.AUTO:
                project.weight_mode = WeightMode.MANUAL
                project.save(update_fields=["weight_mode", "updated_at"])
            messages.success(request, "Bobot disimpan.")
            return redirect("projects:project_structure", pk=project.pk)
    label = "task utama" if parent_id is None else "detail activity"
    return _form_page(request, project, form, f"Atur bobot {label} (total 100%)")


@login_required
def progress_settings(request, pk):
    project = _project_or_404(request, pk)
    _require_edit(request, project)
    config = {**STATUS_PROGRESS_DEFAULTS, **(project.progress_config or {})}
    form = ProgressSettingsForm(
        request.POST or None,
        initial={
            "weight_mode": project.weight_mode,
            "in_progress": config["in_progress"],
            "review": config["review"],
        },
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        project.weight_mode = data["weight_mode"]
        project.progress_config = {
            "in_progress": float(data["in_progress"]),
            "review": float(data["review"]),
        }
        project.save(update_fields=["weight_mode", "progress_config", "updated_at"])
        if project.weight_mode == WeightMode.AUTO:
            for parent_id in {t.parent_task_id for t in Task.objects.filter(project=project)}:
                weight_service.rebalance_if_auto(project, parent_id)
        # Task bermetode status dihitung ulang dengan persentase baru.
        for task in Task.objects.filter(project=project, progress_method="status"):
            task.save()
        record_activity(
            project,
            request.user,
            ActivityAction.WEIGHTS_UPDATED,
            f"Pengaturan progress: bobot {project.get_weight_mode_display().lower()}, "
            f"In Progress {data['in_progress']}%, In Review {data['review']}%.",
        )
        messages.success(request, "Pengaturan progress disimpan.")
        return redirect("projects:project_structure", pk=project.pk)
    return _form_page(request, project, form, "Pengaturan bobot dan progress")
