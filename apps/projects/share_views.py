"""Public, read-only project progress page and its PM controls."""

from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.identity.permissions import can_manage_project, visible_projects

from .models import ActivityAction, Project
from .services import (
    actual_progress,
    planned_progress_on,
    record_activity,
    timeline_data,
    variance,
    variance_level,
)
from .views import progress_chart_data, project_context


def _last_updated(project, snapshots):
    dates = [project.updated_at]
    if snapshots:
        dates.append(snapshots[-1].created_at)
    task_update = project.tasks.order_by("-updated_at").values_list("updated_at", flat=True).first()
    if task_update:
        dates.append(task_update)
    return max(dates)


@never_cache
@require_GET
def public_project(request, token):
    project = get_object_or_404(
        Project,
        public_token=token,
        is_public=True,
    )
    baseline = list(project.baseline_points.all())
    snapshots = list(project.snapshots.all())
    actual = actual_progress(project)
    timeline = timeline_data(project)
    tasks_by_phase = {}
    for task in timeline["tasks"]:
        tasks_by_phase.setdefault(task.phase_id, []).append(task)
    phase_groups = [
        {"phase": phase, "tasks": tasks_by_phase.get(phase.pk, [])}
        for phase in project.phases.all()
    ]
    if tasks_by_phase.get(None):
        phase_groups.append({"phase": None, "tasks": tasks_by_phase[None]})
    response = render(
        request,
        "public/project.html",
        {
            "project": project,
            "milestones": list(project.milestones.all()),
            "planned": planned_progress_on(project),
            "actual": actual,
            "variance": variance(project),
            "level": variance_level(project),
            "chart": progress_chart_data(baseline, snapshots, actual),
            "chart_has_plan": bool(baseline),
            "last_updated": _last_updated(project, snapshots),
            "phase_groups": phase_groups,
            "timeline_rows": timeline["timeline_rows"],
            "timeline_ticks": timeline["timeline_ticks"],
            "timeline_today": timeline["timeline_today"],
            "timeline_start": timeline["timeline_start"],
            "timeline_end": timeline["timeline_end"],
            "timeline_milestones": timeline["timeline_milestones"],
        },
    )
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


def _manageable_project(request, pk):
    project = get_object_or_404(visible_projects(request.user).select_related("manager"), pk=pk)
    if not can_manage_project(request.user, project):
        raise PermissionDenied
    return project


@login_required
@require_http_methods(["GET", "POST"])
def project_share(request, pk):
    project = _manageable_project(request, pk)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "publish":
            project.is_public = True
            project.published_at = timezone.now()
            project.save(update_fields=["is_public", "published_at"])
            record_activity(
                project,
                request.user,
                ActivityAction.PROJECT_UPDATED,
                "Project dipublikasikan.",
            )
            messages.success(
                request,
                "Project dipublikasikan. Siapa pun yang memiliki tautan dapat melihat progress.",
            )
        elif action == "unpublish":
            project.is_public = False
            project.save(update_fields=["is_public"])
            record_activity(
                project,
                request.user,
                ActivityAction.PROJECT_UPDATED,
                "Publikasi project dimatikan.",
            )
            messages.success(
                request,
                "Publikasi dimatikan. Tautan publik tidak lagi dapat diakses.",
            )
        else:
            messages.error(request, "Aksi publikasi tidak dikenal.")
        return redirect("projects:project_share", pk=project.pk)

    public_url = request.build_absolute_uri(
        reverse("projects:public_project", args=[project.public_token])
    )
    return render(
        request,
        "projects/share/settings.html",
        {
            **project_context(request, project, None),
            "public_url": public_url,
        },
    )


@login_required
@require_POST
def project_share_reset(request, pk):
    project = _manageable_project(request, pk)
    project.public_token = uuid4()
    project.save(update_fields=["public_token"])
    record_activity(
        project,
        request.user,
        ActivityAction.PROJECT_UPDATED,
        "Tautan publik dibuat ulang.",
    )
    messages.success(request, "Tautan publik baru dibuat. Tautan lama sudah tidak berlaku.")
    return redirect("projects:project_share", pk=project.pk)
