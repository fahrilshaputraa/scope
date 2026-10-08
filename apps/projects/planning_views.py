import json

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_GET

from apps.form_widgets import style_form
from apps.identity.permissions import can_create_project, can_manage_project, visible_projects

from .planning_io import export_plan, import_plan, planning_template, read_plan


class PlanImportForm(forms.Form):
    file = forms.FileField(
        label="File JSON dari AI",
        widget=forms.ClearableFileInput(attrs={"accept": ".json,application/json"}),
    )
    baseline = forms.BooleanField(
        required=False,
        label="Jadikan jadwal ini baseline",
        help_text="Perlu tanggal mulai dan selesai pada semua task utama.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self, primary=["file"])


def permitted_project(request, pk):
    project = get_object_or_404(visible_projects(request.user), pk=pk) if pk else None
    if not (
        can_manage_project(request.user, project) if project else can_create_project(request.user)
    ):
        raise PermissionDenied
    return project


@login_required
def plan_import(request, pk=None):
    project = permitted_project(request, pk)
    form = PlanImportForm(request.POST if request.method == "POST" else None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            payload = read_plan(form.cleaned_data["file"])
            result = import_plan(payload, request.user, project, form.cleaned_data["baseline"])
        except ValidationError as error:
            form.add_error(None, error)
        except IntegrityError:
            form.add_error(
                None,
                "Kode project sudah dipakai atau file sedang diimpor. "
                "Periksa kode, lalu coba lagi.",
            )
        else:
            message = (
                "File ini sudah diimpor. Data tidak ditambahkan dua kali."
                if result["already_imported"]
                else (
                    f"Rencana siap: {result['tasks']} task, {result['phases']} tahap, "
                    f"{result['milestones']} milestone."
                )
            )
            messages.success(request, message)
            return redirect(
                "projects:project_tasks" if result["tasks"] else "projects:project_detail",
                pk=result["project"].pk,
            )
    return render(request, "projects/plan_import.html", {"form": form, "project": project})


def json_download(payload, filename):
    response = HttpResponse(
        json.dumps(payload, indent=2, ensure_ascii=False),
        content_type="application/json; charset=utf-8",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_GET
def plan_template(request, pk=None):
    project = permitted_project(request, pk)
    return json_download(planning_template(request.user, project), "pcc-plan-template.json")


@login_required
@require_GET
def plan_export(request, pk):
    project = get_object_or_404(visible_projects(request.user), pk=pk)
    return json_download(export_plan(project), f"pcc-{slugify(project.code)}-plan.json")
