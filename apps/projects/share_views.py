"""Public, read-only project progress page and its PM controls."""

from datetime import datetime, time
from uuid import uuid4

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from apps.identity.permissions import can_manage_project, visible_projects
from apps.work.gantt import project_payload

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


def _session_key(project):
    return f"public-unlocked:{project.public_token}"


def _public_password_fingerprint(project):
    return project.public_password_hash[-24:]


def _unlock_throttle_key(request, project):
    return f"public-unlock:{project.pk}:{request.META.get('REMOTE_ADDR', '')}"


def _render_unlock(request, project, error=None, status=200):
    response = render(
        request,
        "public/unlock.html",
        {"project": project, "error": error},
        status=status,
    )
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


@never_cache
@require_http_methods(["GET", "POST"])
def public_project(request, token):
    project = get_object_or_404(
        Project,
        public_token=token,
        is_public=True,
    )
    if project.public_expires_at and project.public_expires_at <= timezone.now():
        response = render(request, "public/expired.html", {"project": project}, status=410)
        response["X-Robots-Tag"] = "noindex, nofollow"
        return response
    if project.public_password_hash:
        fingerprint = _public_password_fingerprint(project)
        if request.session.get(_session_key(project)) != fingerprint:
            if request.method == "POST":
                throttle = _unlock_throttle_key(request, project)
                attempts = cache.get(throttle, 0)
                if attempts >= 10:
                    return _render_unlock(
                        request,
                        project,
                        "Terlalu banyak percobaan. Coba lagi beberapa menit lagi.",
                        status=429,
                    )
                if check_password(request.POST.get("password", ""), project.public_password_hash):
                    cache.delete(throttle)
                    request.session[_session_key(project)] = fingerprint
                    return redirect("projects:public_project", token=project.public_token)
                cache.set(throttle, attempts + 1, 600)
                return _render_unlock(request, project, "Kata sandi salah.", status=403)
            return _render_unlock(request, project)
    if request.method == "POST":
        return HttpResponseNotAllowed(["GET"])
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
    if project.public_hide_task_titles:
        # Hanya objek in-memory; tidak pernah disimpan.
        for index, task in enumerate(timeline["tasks"], start=1):
            task.title = f"Task {index}"
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
            "gantt": project_payload(
                project,
                public=True,
                titles={task.pk: task.title for task in timeline["tasks"]},
            ),
        },
    )
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


class ShareOptionsForm(forms.Form):
    expires_on = forms.DateField(required=False)
    password = forms.CharField(required=False, max_length=128)
    clear_password = forms.BooleanField(required=False)
    hide_task_titles = forms.BooleanField(required=False)

    def clean_password(self):
        password = self.cleaned_data.get("password", "")
        if password and len(password) < 6:
            raise forms.ValidationError("Kata sandi tautan minimal 6 karakter.")
        return password

    def clean(self):
        data = super().clean()
        day = data.get("expires_on")
        if day:
            if day < timezone.localdate():
                self.add_error("expires_on", "Tanggal berakhir tidak boleh di masa lalu.")
            else:
                data["expires_at"] = timezone.make_aware(datetime.combine(day, time.max))
        else:
            data["expires_at"] = None
        return data


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
        if action == "options":
            form = ShareOptionsForm(request.POST)
            if form.is_valid():
                data = form.cleaned_data
                project.public_expires_at = data["expires_at"]
                project.public_hide_task_titles = data["hide_task_titles"]
                if data["clear_password"]:
                    project.public_password_hash = ""
                elif data["password"]:
                    project.public_password_hash = make_password(data["password"])
                project.save(
                    update_fields=[
                        "public_expires_at",
                        "public_hide_task_titles",
                        "public_password_hash",
                    ]
                )
                record_activity(
                    project,
                    request.user,
                    ActivityAction.PROJECT_UPDATED,
                    "Opsi tautan publik diperbarui.",
                )
                messages.success(request, "Opsi tautan publik disimpan.")
            else:
                for errors in form.errors.values():
                    for error in errors:
                        messages.error(request, error)
        elif action == "publish":
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
            **project_context(request, project, "share"),
            "public_url": public_url,
            "expires_on": (
                timezone.localtime(project.public_expires_at).date().isoformat()
                if project.public_expires_at
                else ""
            ),
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
