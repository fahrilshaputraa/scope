"""Views aplikasi work: task, kanban status, gantt dates, issue, comments."""

from datetime import timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Case, F, IntegerField, Q, When
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

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

from .comments import (
    THREAD_PAGE_SIZE,
    resolve_target,
    target_label,
    target_project,
    target_title,
    target_url,
    thread,
)
from .forms import AttachmentForm, IssueForm, ObjectCommentForm, TaskCommentForm, TaskForm
from .mentions import suggestion_payload
from .models import (
    OPEN_ISSUE_STATUSES,
    TASK_STATUS_LABELS,
    CommentTarget,
    Issue,
    IssueStatus,
    Priority,
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


def _safe_next(request: HttpRequest, fallback: str) -> str:
    target = request.POST.get("next") or ""
    if target and url_has_allowed_host_and_scheme(
        target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return target
    return fallback


@login_required
@require_POST
def comment_create(request: HttpRequest) -> HttpResponse:
    """Create a comment on an issue, note, milestone, or project (B4)."""
    target_type = request.POST.get("target_type", "")
    if target_type not in CommentTarget.values:
        raise Http404("Jenis komentar tidak dikenal.")
    target = resolve_target(target_type, request.POST.get("target_id"))
    project = target_project(target)

    if not visible_projects(request.user).filter(pk=project.pk).exists():
        raise Http404("Project tidak ditemukan.")
    posted_project = request.POST.get("project")
    if posted_project and str(posted_project) != str(project.pk):
        raise Http404("Target komentar bukan milik project ini.")
    if is_management(request.user) and not request.user.is_staff:
        raise PermissionDenied

    fallback = target_url(target_type, target)
    form = ObjectCommentForm(request.POST, project=project, user=request.user)
    if not form.is_valid():
        errors = form.errors.get("content") or ["Komentar belum valid."]
        messages.error(request, " ".join(errors))
        return redirect(_safe_next(request, fallback))

    comment = form.save(commit=False)
    comment.project = project
    comment.target_type = target_type
    comment.target_id = target.pk
    comment.author = request.user
    comment.save()
    form.save_mentions(comment)

    label = target_label(target_type)
    title = target_title(target_type, target)
    record_activity(
        project,
        request.user,
        ActivityAction.COMMENT_ADDED,
        f'Komentar ditambahkan di {label} "{title}".',
    )
    notify(
        request.user,
        "comment.added",
        target,
        recipients=form.mentioned_users,
        title=f"Komentar baru: {title}",
        body=f'{user_display(request.user)} mengomentari {label} "{title}".',
        url=target_url(target_type, target),
        dedupe_suffix=f"comment:{comment.pk}",
        project=project,
        allow_management=False,
    )
    messages.success(request, "Komentar ditambahkan.")
    return redirect(_safe_next(request, fallback))


# ================================================================ MY TASKS ===


SOON_DAYS = 7
DUE_FILTERS = ("all", "overdue", "soon", "none")
GROUP_FILTERS = ("status", "project")


def _priority_rank():
    return Case(
        *[When(priority=value, then=index) for index, value in enumerate(Priority.values)],
        default=len(Priority.values),
        output_field=IntegerField(),
    )


@login_required
def my_tasks(request: HttpRequest) -> HttpResponse:
    today = timezone.localdate()
    soon_end = today + timedelta(days=SOON_DAYS)

    query = (request.GET.get("q") or "").strip()
    status_filter = request.GET.get("status", "")
    if status_filter not in TaskStatus.values:
        status_filter = ""
    due_filter = request.GET.get("due", "all")
    if due_filter not in DUE_FILTERS:
        due_filter = "all"
    group = request.GET.get("group", "status")
    if group not in GROUP_FILTERS:
        group = "status"

    projects = visible_projects(request.user).order_by("name", "code")
    selected_project = None
    project_id = request.GET.get("project", "")
    if project_id:
        selected_project = get_object_or_404(visible_projects(request.user), pk=project_id)

    base = (
        Task.objects.filter(
            Q(assignee=request.user) | Q(collaborators=request.user),
            project__in=visible_projects(request.user),
        )
        .distinct()
        .select_related("project", "phase")
        .prefetch_related("issues", "collaborators", "subtasks")
    )
    if query:
        base = base.filter(title__icontains=query)
    if status_filter:
        base = base.filter(status=status_filter)
    if selected_project is not None:
        base = base.filter(project=selected_project)

    open_qs = base.exclude(status=TaskStatus.DONE)
    due_counts = {
        "all": base.count(),
        "overdue": open_qs.filter(due_date__lt=today).count(),
        "soon": open_qs.filter(due_date__gte=today, due_date__lte=soon_end).count(),
        "none": open_qs.filter(due_date__isnull=True).count(),
    }

    filtered = base
    if due_filter == "overdue":
        filtered = filtered.filter(due_date__lt=today).exclude(status=TaskStatus.DONE)
    elif due_filter == "soon":
        filtered = filtered.filter(
            due_date__gte=today, due_date__lte=soon_end
        ).exclude(status=TaskStatus.DONE)
    elif due_filter == "none":
        filtered = filtered.filter(due_date__isnull=True).exclude(status=TaskStatus.DONE)

    tasks = list(
        filtered.annotate(priority_rank=_priority_rank()).order_by(
            F("due_date").asc(nulls_last=True), "priority_rank", "order", "id"
        )
    )
    for task in tasks:
        task.can_edit = can_edit_task(request.user, task)

    # Existing status sections stay intact for callers that read these keys.
    current = [task for task in tasks if task.status == TaskStatus.IN_PROGRESS]
    review = [task for task in tasks if task.status == TaskStatus.REVIEW]
    next_up = [
        task for task in tasks if task.status in (TaskStatus.TODO, TaskStatus.BACKLOG)
    ][:10]
    blocked = [task for task in tasks if task.status == TaskStatus.BLOCKED]
    done = sorted(
        (task for task in tasks if task.status == TaskStatus.DONE),
        key=lambda task: task.updated_at,
        reverse=True,
    )[:10]

    # Attention buckets claim each open task once so nothing renders twice.
    overdue, due_soon, undated, remaining = [], [], [], []
    for task in tasks:
        if task.status == TaskStatus.DONE:
            continue
        if task.is_overdue:
            overdue.append(task)
        elif task.due_date and task.due_date <= soon_end:
            due_soon.append(task)
        elif not task.due_date:
            undated.append(task)
        else:
            remaining.append(task)
    bucket_blocked = [task for task in remaining if task.status == TaskStatus.BLOCKED]
    bucket_current = [task for task in remaining if task.status == TaskStatus.IN_PROGRESS]
    bucket_review = [task for task in remaining if task.status == TaskStatus.REVIEW]
    bucket_next = [
        task for task in remaining if task.status in (TaskStatus.TODO, TaskStatus.BACKLOG)
    ][:10]

    project_groups = []
    if group == "project":
        grouped = {}
        for task in tasks:
            if task.status == TaskStatus.DONE:
                continue
            entry = grouped.setdefault(
                task.project_id, {"project": task.project, "tasks": []}
            )
            entry["tasks"].append(task)
        project_groups = sorted(
            grouped.values(),
            key=lambda entry: (entry["project"].name.lower(), entry["project"].code),
        )
        for entry in project_groups:
            entry["count"] = len(entry["tasks"])

    return render(
        request,
        "work/my_tasks.html",
        {
            "current": current,
            "review": review,
            "next_up": next_up,
            "done": done,
            "blocked": blocked,
            "bucket_overdue": overdue,
            "bucket_soon": due_soon,
            "bucket_undated": undated,
            "bucket_blocked": bucket_blocked,
            "bucket_current": bucket_current,
            "bucket_review": bucket_review,
            "bucket_next": bucket_next,
            "open_count": len(overdue) + len(due_soon) + len(undated) + len(remaining),
            "done_count": len(done),
            "project_groups": project_groups,
            "projects": projects,
            "selected_project": selected_project,
            "status_labels": TASK_STATUS_LABELS,
            "due_counts": due_counts,
            "query": query,
            "status_filter": status_filter,
            "due_filter": due_filter,
            "group": group,
            "has_filters": bool(query or status_filter or selected_project or due_filter != "all"),
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
    comment_context = {
        "comments": paginate(
            request,
            thread(issue.project, CommentTarget.ISSUE, issue.pk, limit=None),
            THREAD_PAGE_SIZE,
        ),
        "comment_count": thread(
            issue.project, CommentTarget.ISSUE, issue.pk, limit=None
        ).count(),
        "can_comment": not is_management(request.user) or request.user.is_staff,
    }
    comment_context["comments_page"] = comment_context["comments"]
    if not can_manage_project(request.user, issue.project):
        if request.method != "GET":
            raise PermissionDenied
        return render(
            request,
            "work/issue_detail.html",
            {"issue": issue, "can_manage": False, **comment_context},
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
        {"form": form, "project": issue.project, "issue": issue, "title": issue.title,
         **comment_context},
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
