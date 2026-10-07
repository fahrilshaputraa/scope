"""Views aplikasi work: task, kanban status, gantt dates, issue, comments."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.identity.permissions import can_edit_task, can_manage_project
from apps.projects.models import ActivityAction, Project
from apps.projects.services import record_activity

from .forms import IssueForm, TaskCommentForm, TaskForm
from .models import (
    OPEN_ISSUE_STATUSES,
    Issue,
    IssueStatus,
    Task,
    TaskStatus,
)


def _task_or_404(pk):
    return get_object_or_404(
        Task.objects.select_related("project", "assignee", "phase", "milestone", "parent_task"),
        pk=pk,
    )


def _project_from_request(request) -> Project | None:
    pid = request.GET.get("project") or request.POST.get("project")
    if pid:
        return get_object_or_404(Project, pk=pid)
    return None


# ================================================================ MY TASKS ===


@login_required
def my_tasks(request: HttpRequest) -> HttpResponse:
    qs = (
        Task.objects.filter(assignee=request.user)
        .select_related("project", "phase")
        .prefetch_related("issues")
    )
    current = list(qs.filter(status=TaskStatus.IN_PROGRESS).order_by("due_date"))
    review = list(qs.filter(status=TaskStatus.REVIEW).order_by("due_date"))
    next_up = list(
        qs.filter(status__in=[TaskStatus.TODO, TaskStatus.BACKLOG, TaskStatus.BLOCKED])
        .order_by("order", "due_date")[:10]
    )
    done = list(qs.filter(status=TaskStatus.DONE).order_by("-updated_at")[:10])
    return render(
        request,
        "work/my_tasks.html",
        {"current": current, "review": review, "next_up": next_up, "done": done},
    )


# ================================================================== ISSUES ===


@login_required
def issue_list(request: HttpRequest) -> HttpResponse:
    qs = Issue.objects.select_related("project", "owner", "task")
    status = request.GET.get("status", "open")
    if status == "open":
        qs = qs.filter(status__in=OPEN_ISSUE_STATUSES)
    elif status == "resolved":
        qs = qs.filter(status__in=[IssueStatus.RESOLVED, IssueStatus.CLOSED])
    issues = qs[:100]
    return render(
        request,
        "work/issue_list.html",
        {
            "issues": issues,
            "filter": status,
            "open_count": Issue.objects.filter(status__in=OPEN_ISSUE_STATUSES).count(),
        },
    )


@login_required
def issue_create(request: HttpRequest) -> HttpResponse:
    project = _project_from_request(request)
    form = IssueForm(request.POST or None, project=project)
    if request.method == "POST" and form.is_valid():
        issue = form.save(commit=False)
        if project is None:
            issue.project = form.cleaned_data["project"]
        else:
            issue.project = project
        if not issue.owner_id:
            issue.owner = request.user
        issue.save()
        record_activity(
            issue.project,
            request.user,
            ActivityAction.ISSUE_CREATED,
            f'Issue "{issue.title}" created ({issue.get_severity_display()}).',
        )
        messages.success(request, f"Issue {issue.title} dibuat.")
        return redirect("projects:project_issues", pk=issue.project_id)
    return render(
        request,
        "work/issue_form.html",
        {"form": form, "project": project, "title": "Report Issue"},
    )


@login_required
def issue_update(request: HttpRequest, pk: int) -> HttpResponse:
    issue = get_object_or_404(
        Issue.objects.select_related("project", "task"), pk=pk
    )
    if not can_manage_project(request.user, issue.project):
        messages.error(request, "Hanya Project Manager yang bisa mengubah issue.")
        return redirect("projects:project_issues", pk=issue.project_id)
    form = IssueForm(request.POST or None, instance=issue, project=issue.project)
    if request.method == "POST" and form.is_valid():
        issue = form.save()
        was_resolved = issue.status in (IssueStatus.RESOLVED, IssueStatus.CLOSED)
        if was_resolved and not issue.resolved_at:
            issue.resolved_at = timezone.now()
            issue.save(update_fields=["resolved_at"])
            record_activity(
                issue.project,
                request.user,
                ActivityAction.ISSUE_RESOLVED,
                f'Issue "{issue.title}" resolved.',
            )
        else:
            record_activity(
                issue.project,
                request.user,
                ActivityAction.ISSUE_UPDATED,
                f'Issue "{issue.title}" updated.',
            )
        messages.success(request, "Issue disimpan.")
        return redirect("projects:project_issues", pk=issue.project_id)
    return render(
        request,
        "work/issue_form.html",
        {"form": form, "project": issue.project, "title": issue.title},
    )


# =================================================================== TASKS ===


@login_required
def task_create(request: HttpRequest) -> HttpResponse:
    project = _project_from_request(request)
    if project is None:
        messages.error(request, "Pilih project terlebih dahulu untuk membuat task.")
        return redirect("projects:project_list")
    if not can_manage_project(request.user, project):
        messages.error(request, "Hanya Project Manager yang bisa membuat task.")
        return redirect("projects:project_tasks", pk=project.pk)
    form = TaskForm(request.POST or None, project=project)
    if request.method == "POST" and form.is_valid():
        task = form.save(commit=False)
        task.project = project
        task.save()
        record_activity(
            task.project,
            request.user,
            ActivityAction.TASK_CREATED,
            f'Task "{task.title}" dibuat. Status: {task.get_status_display()}.',
        )
        messages.success(request, f"Task {task.title} dibuat.")
        return redirect("projects:project_tasks", pk=task.project_id)
    return render(
        request,
        "work/task_form.html",
        {"form": form, "project": project, "title": "New Task"},
    )


@login_required
def task_detail(request: HttpRequest, pk: int) -> HttpResponse:
    task = get_object_or_404(
        Task.objects.select_related(
            "project", "assignee", "phase", "milestone", "parent_task"
        ).prefetch_related("comments__author", "issues"),
        pk=pk,
    )
    comment_form = TaskCommentForm()
    if request.method == "POST":
        comment_form = TaskCommentForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.task = task
            comment.author = request.user
            comment.save()
            record_activity(
                task.project,
                request.user,
                ActivityAction.COMMENT_ADDED,
                f'Komentar ditambahkan di task "{task.title}".',
            )
            messages.success(request, "Komentar ditambahkan.")
            return redirect("work:task_detail", pk=task.pk)
    return render(
        request,
        "work/task_detail.html",
        {
            "task": task,
            "can_edit": can_edit_task(request.user, task),
            "can_manage": can_manage_project(request.user, task.project),
            "comment_form": comment_form,
        },
    )


@login_required
def task_update(request: HttpRequest, pk: int) -> HttpResponse:
    task = _task_or_404(pk)
    if not can_edit_task(request.user, task):
        messages.error(request, "Anda tidak berhak mengubah task ini.")
        return redirect("work:task_detail", pk=task.pk)
    form = TaskForm(request.POST or None, instance=task, project=task.project)
    if request.method == "POST" and form.is_valid():
        old_status = task.status
        task = form.save()
        if task.status != old_status:
            record_activity(
                task.project,
                request.user,
                ActivityAction.TASK_STATUS,
                f'Status task "{task.title}": '
                f"{dict(TaskStatus.choices)[old_status]} → {task.get_status_display()}.",
            )
        else:
            record_activity(
                task.project,
                request.user,
                ActivityAction.TASK_UPDATED,
                f'Task "{task.title}" diperbarui.',
            )
        if task.status == TaskStatus.DONE and not task.completed_at:
            task.completed_at = timezone.now()
            task.save(update_fields=["completed_at"])
        messages.success(request, "Task disimpan.")
        return redirect("work:task_detail", pk=task.pk)
    return render(
        request,
        "work/task_form.html",
        {"form": form, "project": task.project, "title": f"Edit — {task.title}"},
    )


@login_required
@require_http_methods(["PATCH", "POST"])
def task_status(request: HttpRequest, pk: int) -> HttpResponse:
    """Endpoint Kanban drag & drop: ubah status task. Dipanggil via htmx/ajax."""
    task = _task_or_404(pk)
    if not can_edit_task(request.user, task):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
    data = request.POST if request.method == "POST" else request.body
    if isinstance(data, bytes):
        status = data.decode("utf-8")
        try:
            from urllib.parse import parse_qs
            status = parse_qs(data.decode("utf-8")).get("status", [""])[0]
        except Exception:
            status = data.decode("utf-8")
    else:
        status = data.get("status", "")
    if status not in TaskStatus.values:
        return JsonResponse({"ok": False, "error": "invalid status"}, status=400)
    old_status = task.status
    task.status = status
    task.save(update_fields=["status", "updated_at"])
    if task.status == TaskStatus.DONE:
        task.completed_at = timezone.now()
        task.save(update_fields=["completed_at"])
    elif old_status == TaskStatus.DONE:
        task.completed_at = None
        task.save(update_fields=["completed_at"])
    record_activity(
        task.project,
        request.user,
        ActivityAction.TASK_STATUS,
        f'Status task "{task.title}": '
                f"{dict(TaskStatus.choices)[old_status]} → {task.get_status_display()}.",
    )
    return JsonResponse({"ok": True, "id": task.id, "status": task.status})


@login_required
@require_http_methods(["PATCH", "POST"])
def task_dates(request: HttpRequest, pk: int) -> HttpResponse:
    """Endpoint Gantt drag/resize: ubah start/end date task."""
    task = _task_or_404(pk)
    if not can_manage_project(request.user, task.project):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
    params = {}
    if request.method == "POST":
        params = request.POST
    else:
        from urllib.parse import parse_qs

        params = {k: v[0] for k, v in parse_qs(request.body.decode("utf-8")).items()}
    start = params.get("start", "")
    end = params.get("end", "")
    changed = []
    from django.utils.dateparse import parse_date

    if start and parse_date(start):
        task.start_date = parse_date(start)
        changed.append("start_date")
    if end and parse_date(end):
        task.due_date = parse_date(end)
        changed.append("due_date")
    if changed:
        task.save(update_fields=changed + ["updated_at"])
        record_activity(
            task.project,
            request.user,
            ActivityAction.TIMELINE_CHANGED,
            f'Timeline task "{task.title}" diubah.',
        )
    return JsonResponse(
        {
            "ok": True,
            "id": task.id,
            "start": task.start_date.isoformat(),
            "end": task.due_date.isoformat() if task.due_date else None,
        }
    )