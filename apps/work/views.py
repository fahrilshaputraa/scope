"""Views aplikasi work: task, kanban status, gantt dates, issue, comments."""

from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods

from apps.identity.permissions import (
    can_edit_task,
    can_manage_project,
    can_report_issue,
    is_management,
    visible_projects,
)
from apps.notifications.models import SubscriptionTarget
from apps.notifications.services import notify, user_display
from apps.notifications.subscriptions import watch_state
from apps.projects.models import ActivityAction, Project
from apps.projects.pagination import paginate
from apps.projects.services import record_activity

from .forms import AttachmentForm, IssueForm, TaskCommentForm, TaskForm
from .mentions import suggestion_payload
from .models import (
    OPEN_ISSUE_STATUSES,
    Issue,
    IssueStatus,
    Task,
    TaskAttachment,
    TaskStatus,
)


def _task_or_404(request, pk):
    return get_object_or_404(
        Task.objects.select_related(
            "project", "assignee", "phase", "milestone", "parent_task"
        ).prefetch_related("subtasks"),
        pk=pk,
        project__in=visible_projects(request.user),
    )


def _project_from_request(request) -> Project | None:
    pid = request.GET.get("project") or request.POST.get("project")
    if pid:
        return get_object_or_404(visible_projects(request.user), pk=pid)
    return None


@login_required
def mention_suggest(request: HttpRequest) -> JsonResponse:
    """Autocomplete ``@username`` inside a project the requester can see."""
    try:
        project_id = int(request.GET.get("project", ""))
    except (TypeError, ValueError):
        raise Http404 from None
    project = get_object_or_404(visible_projects(request.user), pk=project_id)
    return JsonResponse(suggestion_payload(project, request.GET.get("q", "")), safe=False)


# ================================================================ MY TASKS ===


@login_required
def my_tasks(request: HttpRequest) -> HttpResponse:
    qs = (
        Task.objects.filter(
            Q(assignee=request.user) | Q(collaborators=request.user),
            project__in=visible_projects(request.user),
        )
        .distinct()
        .select_related("project", "phase")
        .prefetch_related("issues", "collaborators")
    )
    current = list(qs.filter(status=TaskStatus.IN_PROGRESS).order_by("due_date"))
    review = list(qs.filter(status=TaskStatus.REVIEW).order_by("due_date"))
    next_up = list(
        qs.filter(status__in=[TaskStatus.TODO, TaskStatus.BACKLOG]).order_by("order", "due_date")[
            :10
        ]
    )
    blocked = list(qs.filter(status=TaskStatus.BLOCKED).order_by("due_date"))
    done = list(qs.filter(status=TaskStatus.DONE).order_by("-updated_at")[:10])
    for task in current + review + next_up + done + blocked:
        task.can_edit = can_edit_task(request.user, task)
    return render(
        request,
        "work/my_tasks.html",
        {
            "current": current,
            "review": review,
            "next_up": next_up,
            "done": done,
            "blocked": blocked,
        },
    )


# ================================================================== ISSUES ===


@login_required
def issue_list(request: HttpRequest) -> HttpResponse:
    qs = Issue.objects.select_related("project", "owner", "task").filter(
        project__in=visible_projects(request.user)
    )
    status = request.GET.get("status", "open")
    if status == "open":
        qs = qs.filter(status__in=OPEN_ISSUE_STATUSES)
    elif status == "resolved":
        qs = qs.filter(status__in=[IssueStatus.RESOLVED, IssueStatus.CLOSED])
    page_obj = paginate(request, qs, 25)
    return render(
        request,
        "work/issue_list.html",
        {
            "issues": page_obj,
            "page_obj": page_obj,
            "filter": status,
            "can_report": can_report_issue(request.user),
            "open_count": Issue.objects.filter(
                status__in=OPEN_ISSUE_STATUSES, project__in=visible_projects(request.user)
            ).count(),
        },
    )


@login_required
def issue_create(request: HttpRequest) -> HttpResponse:
    project = _project_from_request(request)
    if is_management(request.user) and not request.user.is_staff:
        raise PermissionDenied
    form = IssueForm(request.POST or None, project=project, user=request.user)
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
            target=issue,
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
        Issue.objects.select_related("project", "task").filter(
            project__in=visible_projects(request.user)
        ),
        pk=pk,
    )
    if not can_manage_project(request.user, issue.project):
        if request.method != "GET":
            raise PermissionDenied
        return render(
            request,
            "work/issue_detail.html",
            {"issue": issue, "can_manage": False},
        )
    form = IssueForm(request.POST or None, instance=issue, project=issue.project)
    if request.method == "POST" and form.is_valid():
        old_due_date = issue.due_date
        old_owner_id = issue.owner_id
        issue = form.save()
        if issue.owner_id != old_owner_id:
            record_activity(
                issue.project,
                request.user,
                ActivityAction.ISSUE_ASSIGNED,
                f'Penugasan issue "{issue.title}" diperbarui.',
                target=issue,
            )
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
            if not was_resolved and issue.resolved_at:
                issue.resolved_at = None
                issue.save(update_fields=["resolved_at"])
            record_activity(
                issue.project,
                request.user,
                ActivityAction.ISSUE_UPDATED,
                f'Issue "{issue.title}" updated.',
                target=issue if issue.due_date != old_due_date else None,
            )
        messages.success(request, "Issue disimpan.")
        return redirect("projects:project_issues", pk=issue.project_id)
    return render(
        request,
        "work/issue_form.html",
        {"form": form, "project": issue.project, "title": issue.title},
    )


@login_required
@require_http_methods(["POST"])
def issue_archive(request, pk):
    issue = get_object_or_404(
        Issue.all_objects.select_related("project"),
        pk=pk,
        project__in=visible_projects(request.user, include_archived=True),
    )
    if not can_manage_project(request.user, issue.project):
        raise PermissionDenied
    if issue.archive(request.user):
        record_activity(
            issue.project,
            request.user,
            ActivityAction.ISSUE_ARCHIVED,
            f'Issue "{issue.title}" diarsipkan.',
        )
        messages.success(request, "Issue diarsipkan.")
    else:
        messages.info(request, "Issue sudah diarsipkan.")
    return redirect("projects:project_issues", pk=issue.project_id)


@login_required
@require_http_methods(["POST"])
def issue_restore(request, pk):
    issue = get_object_or_404(
        Issue.all_objects.select_related("project"),
        pk=pk,
        project__in=visible_projects(request.user, include_archived=True),
    )
    if not can_manage_project(request.user, issue.project):
        raise PermissionDenied
    if issue.restore():
        record_activity(
            issue.project,
            request.user,
            ActivityAction.ISSUE_RESTORED,
            f'Issue "{issue.title}" dipulihkan dari arsip.',
        )
        messages.success(request, "Issue dipulihkan.")
    else:
        messages.info(request, "Issue tidak sedang diarsipkan.")
    return redirect("projects:project_issues", pk=issue.project_id)


# =================================================================== TASKS ===


@login_required
@transaction.atomic
def task_create(request: HttpRequest) -> HttpResponse:
    project = _project_from_request(request)
    if project is None:
        messages.error(request, "Pilih project terlebih dahulu untuk membuat task.")
        return redirect("projects:project_list")
    if not can_manage_project(request.user, project):
        messages.error(request, "Hanya Project Manager yang bisa membuat task.")
        return redirect("projects:project_tasks", pk=project.pk)
    parent_id = request.GET.get("parent_task")
    parent = None
    if parent_id:
        parent = get_object_or_404(
            project.tasks.select_related("phase"), pk=parent_id, parent_task__isnull=True
        )
    form = TaskForm(request.POST or None, project=project, parent=parent)
    if request.method == "POST" and form.is_valid():
        task = form.save(commit=False)
        task.project = project
        task.save()
        form.save_m2m()
        record_activity(
            task.project,
            request.user,
            ActivityAction.TASK_CREATED,
            f'Task "{task.title}" dibuat. Status: {task.get_status_display()}.',
            target=task,
        )
        messages.success(request, f"Task {task.title} dibuat.")
        if task.parent_task_id:
            return redirect("work:task_detail", pk=task.parent_task_id)
        return redirect("projects:project_tasks", pk=task.project_id)
    return render(
        request,
        "work/task_form.html",
        {
            "form": form,
            "project": project,
            "parent": parent,
            "title": "Tambah detail activity" if parent else "Tambah activity",
        },
    )


@login_required
def task_detail(request: HttpRequest, pk: int) -> HttpResponse:
    task = get_object_or_404(
        Task.objects.select_related(
            "project", "assignee", "phase", "milestone", "parent_task"
        ).prefetch_related(
            "comments__author", "issues", "subtasks__assignee", "subtasks__collaborators"
        ),
        pk=pk,
        project__in=visible_projects(request.user),
    )
    comment_form = TaskCommentForm(project=task.project, user=request.user)
    comments_page = paginate(
        request, task.comments.select_related("author").order_by("created_at"), 20
    )
    details = list(task.subtasks.all())
    if request.method == "POST":
        if is_management(request.user) and not request.user.is_staff:
            raise PermissionDenied
        comment_form = TaskCommentForm(request.POST, project=task.project, user=request.user)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.task = task
            comment.author = request.user
            comment.save()
            comment_form.save_mentions(comment)
            record_activity(
                task.project,
                request.user,
                ActivityAction.COMMENT_ADDED,
                f'Komentar ditambahkan di task "{task.title}".',
                target=task,
                dedupe_token=str(comment.pk),
            )
            if comment_form.mentioned_users:
                notify(
                    request.user,
                    "comment.added",
                    task,
                    recipients=comment_form.mentioned_users,
                    title=f"Anda disebut di komentar: {task.title}",
                    body=(
                        f'{user_display(request.user)} menyebut Anda dalam komentar '
                        f'di task "{task.title}".'
                    ),
                    url=reverse("work:task_detail", args=[task.pk]),
                    dedupe_suffix=f"comment:{comment.pk}",
                )
            messages.success(request, "Komentar ditambahkan.")
            return redirect("work:task_detail", pk=task.pk)
    return render(
        request,
        "work/task_detail.html",
        {
            "task": task,
            "details": details,
            "can_edit": can_edit_task(request.user, task),
            "can_manage": can_manage_project(request.user, task.project),
            "comment_form": comment_form,
            "comments": comments_page,
            "comments_page": comments_page,
            "can_comment": not is_management(request.user) or request.user.is_staff,
            "attachment_form": AttachmentForm(),
            **watch_state(request.user, SubscriptionTarget.TASK, task.pk),
        },
    )


@login_required
@transaction.atomic
def task_update(request: HttpRequest, pk: int) -> HttpResponse:
    task = _task_or_404(request, pk)
    if not can_edit_task(request.user, task):
        messages.error(request, "Anda tidak berhak mengubah task ini.")
        return redirect("work:task_detail", pk=task.pk)
    old_status = task.status
    old_assignee_id = task.assignee_id
    work_update = request.GET.get("mode") == "update"
    board_status = request.GET.get("board_status") if work_update else None
    form = TaskForm(
        request.POST or None,
        instance=task,
        project=task.project,
        can_plan=can_manage_project(request.user, task.project) and not work_update,
        initial={"status": board_status} if board_status in TaskStatus.values else None,
    )
    if request.method == "POST" and form.is_valid():
        task = form.save()
        if work_update and request.GET.get("clear_column") == "true":
            task.board_column = None
            task.save(update_fields=["board_column", "updated_at"])
        if task.assignee_id != old_assignee_id:
            record_activity(
                task.project,
                request.user,
                ActivityAction.TASK_ASSIGNED,
                f'Penugasan task "{task.title}" diperbarui.',
                target=task,
            )
        if task.status != old_status:
            record_activity(
                task.project,
                request.user,
                ActivityAction.TASK_STATUS,
                f'Status task "{task.title}": '
                f"{dict(TaskStatus.choices)[old_status]} → {task.get_status_display()}.",
                target=task,
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
        {
            "form": form,
            "project": task.project,
            "title": f"Update pekerjaan — {task.title}" if work_update else f"Edit — {task.title}",
        },
    )


@login_required
@require_http_methods(["POST"])
def task_archive(request, pk):
    task = get_object_or_404(
        Task.all_objects.select_related("project"),
        pk=pk,
        project__in=visible_projects(request.user, include_archived=True),
    )
    if not can_manage_project(request.user, task.project):
        raise PermissionDenied
    if task.archive(request.user):
        record_activity(
            task.project,
            request.user,
            ActivityAction.TASK_ARCHIVED,
            f'Task "{task.title}" diarsipkan.',
        )
        messages.success(request, "Task diarsipkan.")
    else:
        messages.info(request, "Task sudah diarsipkan.")
    return redirect("projects:project_tasks", pk=task.project_id)


@login_required
@require_http_methods(["POST"])
def task_restore(request, pk):
    task = get_object_or_404(
        Task.all_objects.select_related("project"),
        pk=pk,
        project__in=visible_projects(request.user, include_archived=True),
    )
    if not can_manage_project(request.user, task.project):
        raise PermissionDenied
    if task.parent_task_id and Task.all_objects.filter(
        pk=task.parent_task_id, archived_at__isnull=False
    ).exists():
        messages.error(request, "Pulihkan activity induk terlebih dahulu.")
        return redirect("projects:project_tasks", pk=task.project_id)
    if task.restore():
        record_activity(
            task.project,
            request.user,
            ActivityAction.TASK_RESTORED,
            f'Task "{task.title}" dipulihkan dari arsip.',
        )
        messages.success(request, "Task dipulihkan.")
    else:
        messages.info(request, "Task tidak sedang diarsipkan.")
    return redirect("work:task_detail", pk=task.pk)


def _params(request):
    if request.method == "POST":
        return request.POST
    return {k: v[0] for k, v in parse_qs(request.body.decode("utf-8")).items()}


@login_required
@require_http_methods(["PATCH", "POST"])
@transaction.atomic
def task_status(request, pk):
    task = _task_or_404(request, pk)
    if not can_edit_task(request.user, task):
        return JsonResponse(
            {"ok": False, "error": "Anda tidak dapat mengubah task ini."}, status=403
        )
    params = _params(request)
    status = params.get("status", "")
    if status not in TaskStatus.values:
        return JsonResponse({"ok": False, "error": "Pilih status task yang valid."}, status=400)
    old_status = task.status
    # Status updates preserve grouping; only an explicit board move clears it.
    if params.get("clear_column") == "true":
        task.board_column = None
    task.status = status
    if status == TaskStatus.BLOCKED:
        task.blocked_reason = params.get("blocked_reason", task.blocked_reason).strip()
    if (
        status in (TaskStatus.IN_PROGRESS, TaskStatus.DONE)
        and task.dependencies.exclude(status=TaskStatus.DONE).exists()
    ):
        return JsonResponse(
            {"ok": False, "error": "Selesaikan dependency task terlebih dahulu."}, status=400
        )
    try:
        task.full_clean(exclude=["dependencies"])
    except ValidationError as exc:
        return JsonResponse({"ok": False, "error": " ".join(exc.messages)}, status=400)
    task.save()
    record_activity(
        task.project,
        request.user,
        ActivityAction.TASK_STATUS,
        f'Status task "{task.title}": '
        f"{dict(TaskStatus.choices)[old_status]} → {task.get_status_display()}.",
        target=task,
    )
    return JsonResponse(
        {"ok": True, "id": task.pk, "status": task.status, "progress": float(task.display_progress)}
    )


@login_required
@require_http_methods(["PATCH", "POST"])
@transaction.atomic
def task_progress(request, pk):
    task = _task_or_404(request, pk)
    if not can_edit_task(request.user, task):
        return JsonResponse(
            {"ok": False, "error": "Anda tidak dapat mengubah progress task ini."}, status=403
        )
    if task.has_details:
        return JsonResponse(
            {"ok": False, "error": "Progress activity dihitung otomatis dari detail activity."},
            status=400,
        )
    try:
        value = Decimal(_params(request).get("progress", ""))
        if not value.is_finite() or not 0 <= value <= 100:
            raise ValueError
    except (InvalidOperation, ValueError):
        return JsonResponse({"ok": False, "error": "Progress harus antara 0 dan 100%."}, status=400)
    if task.is_done and value != 100:
        return JsonResponse(
            {"ok": False, "error": "Ubah status Done sebelum menurunkan progress."}, status=400
        )
    task.progress = value
    task.save(update_fields=["progress", "updated_at"])
    record_activity(
        task.project,
        request.user,
        ActivityAction.PROGRESS_UPDATED,
        f'Progress task "{task.title}" menjadi {value}%.',
    )
    return JsonResponse({"ok": True, "progress": float(task.display_progress)})


@login_required
@require_http_methods(["PATCH", "POST"])
@transaction.atomic
def task_dates(request, pk):
    task = _task_or_404(request, pk)
    if not can_manage_project(request.user, task.project):
        return JsonResponse(
            {"ok": False, "error": "Hanya PM project yang dapat mengubah jadwal."}, status=403
        )
    params = _params(request)
    try:
        start, end = parse_date(params.get("start", "")), parse_date(params.get("end", ""))
    except ValueError:
        start, end = None, None
    if not start or not end or end < start:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Tanggal mulai dan selesai harus valid; selesai tidak boleh sebelum mulai."
                ),
            },
            status=400,
        )
    task.start_date, task.due_date = start, end
    task.save(update_fields=["start_date", "due_date", "updated_at"])
    record_activity(
        task.project,
        request.user,
        ActivityAction.TIMELINE_CHANGED,
        f'Timeline task "{task.title}" diubah.',
        target=task,
    )
    return JsonResponse(
        {"ok": True, "id": task.pk, "start": start.isoformat(), "end": end.isoformat()}
    )


@login_required
@require_http_methods(["POST"])
def attachment_upload(request, pk):
    task = _task_or_404(request, pk)
    if not can_edit_task(request.user, task):
        raise PermissionDenied
    form = AttachmentForm(request.POST, request.FILES)
    if form.is_valid():
        upload = form.cleaned_data["file"]
        TaskAttachment.objects.create(
            task=task, file=upload, name=upload.name, uploaded_by=request.user
        )
        record_activity(
            task.project,
            request.user,
            ActivityAction.TASK_UPDATED,
            f'Lampiran ditambahkan ke "{task.title}".',
        )
        messages.success(request, "Lampiran diunggah.")
    else:
        messages.error(request, " ".join(form.errors.get("file", [])))
    return redirect("work:task_detail", pk=pk)


@login_required
def attachment_download(request, pk):
    attachment = get_object_or_404(
        TaskAttachment, pk=pk, task__project__in=visible_projects(request.user)
    )
    return FileResponse(attachment.file.open("rb"), as_attachment=True, filename=attachment.name)


@login_required
@require_http_methods(["POST"])
def attachment_delete(request, pk):
    attachment = get_object_or_404(
        TaskAttachment, pk=pk, task__project__in=visible_projects(request.user)
    )
    if not can_edit_task(request.user, attachment.task):
        raise PermissionDenied
    task_id = attachment.task_id
    attachment.file.delete(save=False)
    attachment.delete()
    messages.success(request, "Lampiran dihapus.")
    return redirect("work:task_detail", pk=task_id)
