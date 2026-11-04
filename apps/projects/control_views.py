"""Progress Task dan Project Control untuk PM (PRD §6.2, §10.2, R4.1-R4.3)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Case, F, IntegerField, When
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.identity.permissions import (
    can_control_projects,
    can_manage_project,
    can_monitor_tasks,
    controlled_projects,
)
from apps.identity.roles import assignment_problem, has_perm
from apps.notifications.services import notify, user_display
from apps.work.assignment import assignable_users
from apps.work.models import Task, TaskComment, TaskStatus

from .control import (
    EXCEPTION_FLAGS,
    FLAG_LABELS,
    FLAGS,
    exception_total,
    flag_counts,
    flag_filter,
    project_tasks,
    task_flags,
)
from .models import ActivityAction
from .pagination import paginate
from .services import record_activity
from .views import project_context

PER_PAGE = 25
FOLLOW_UP_MAX = 500


def _require(allowed: bool) -> None:
    if not allowed:
        raise PermissionDenied


def _safe_next(request, fallback: str) -> str:
    target = request.POST.get("next") or ""
    if url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return fallback


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _row(task, today):
    deviation = None
    if task.due_date and task.baseline_end_date:
        deviation = (task.due_date - task.baseline_end_date).days
    return {"task": task, "flags": task_flags(task, today), "deviation": deviation}


# ============================================================ PROGRESS TASK ===


@login_required
def progress_task(request):
    """Monitoring seluruh task di project yang dikelola PM (hanya baca, PRD §10.2)."""
    _require(can_monitor_tasks(request.user))
    projects = controlled_projects(request.user)
    base = Task.objects.filter(project__in=projects).select_related(
        "project", "phase", "assignee", "parent_task"
    )
    params = request.GET
    project_id, phase_id = _int(params.get("project")), _int(params.get("phase"))
    assignee = params.get("assignee", "")
    status = params.get("status", "")
    flag = params.get("flag", "")
    due_from, due_to = parse_date(params.get("from", "")), parse_date(params.get("to", ""))

    if project_id:
        base = base.filter(project_id=project_id)
    if phase_id:
        base = base.filter(phase_id=phase_id)
    if assignee == "none":
        base = base.filter(assignee__isnull=True)
    elif _int(assignee):
        base = base.filter(assignee_id=_int(assignee))

    counts = flag_counts(base)
    tasks = base
    if status in TaskStatus.values:
        tasks = tasks.filter(status=status)
    if flag in FLAGS:
        tasks = tasks.filter(flag_filter(flag))
    if due_from:
        tasks = tasks.filter(due_date__gte=due_from)
    if due_to:
        tasks = tasks.filter(due_date__lte=due_to)
    done_last = Case(When(status=TaskStatus.DONE, then=1), default=0, output_field=IntegerField())
    tasks = tasks.order_by(done_last, F("due_date").asc(nulls_last=True), "project__code", "pk")

    today = timezone.localdate()
    page = paginate(request, tasks, PER_PAGE)
    rows = [_row(task, today) for task in page.object_list]
    people = User.objects.filter(assigned_tasks__project__in=projects).distinct().order_by(
        "first_name", "username"
    )
    query = params.copy()
    query.pop("page", None)
    query.pop("flag", None)
    return render(
        request,
        "projects/control/progress_task.html",
        {
            "rows": rows,
            "page_obj": page,
            "total": page.paginator.count,
            "counts": counts,
            "flag_labels": FLAG_LABELS,
            "flags": FLAGS,
            "active_flag": flag if flag in FLAGS else "",
            "projects": projects.order_by("code"),
            "people": people,
            "phases": _phases(projects, project_id),
            "status_choices": TaskStatus.choices,
            "filters": {
                "project": project_id or "",
                "phase": phase_id or "",
                "assignee": assignee,
                "status": status,
                "from": params.get("from", ""),
                "to": params.get("to", ""),
            },
            "query": query.urlencode(),
        },
    )


def _phases(projects, project_id):
    from .models import Phase

    phases = Phase.objects.filter(project__in=projects)
    if project_id:
        phases = phases.filter(project_id=project_id)
    return phases.select_related("project").order_by("project__code", "sequence")


# ============================================================ PROJECT CONTROL ===


@login_required
def control_index(request):
    """Ringkasan pengecualian per project yang dikontrol PM."""
    _require(can_control_projects(request.user))
    rows = []
    for project in controlled_projects(request.user).order_by("code"):
        counts = flag_counts(Task.objects.filter(project=project), EXCEPTION_FLAGS)
        rows.append({"project": project, "counts": counts, "total": exception_total(counts)})
    rows.sort(key=lambda row: (-row["total"], row["project"].code))
    return render(
        request,
        "projects/control/index.html",
        {"rows": rows, "flag_labels": FLAG_LABELS, "flags": EXCEPTION_FLAGS},
    )


SECTION_LIMIT = 50


@login_required
def project_control(request, pk):
    """Kontrol satu project: pengecualian, reassign, dan tindak lanjut."""
    _require(can_control_projects(request.user))
    project = get_object_or_404(controlled_projects(request.user), pk=pk)
    today = timezone.localdate()
    tasks = project_tasks(project)
    shown = set()
    sections = []
    for flag in EXCEPTION_FLAGS:
        queryset = tasks.filter(flag_filter(flag, today)).order_by(
            F("due_date").asc(nulls_last=True), "pk"
        )
        items = [task for task in queryset[:SECTION_LIMIT] if task.pk not in shown]
        # Task yang sudah muncul di bagian sebelumnya tidak diulang.
        shown.update(task.pk for task in items)
        sections.append(
            {
                "flag": flag,
                "label": FLAG_LABELS[flag],
                "count": tasks.filter(flag_filter(flag, today)).count(),
                "rows": [_row(task, today) for task in items],
            }
        )
    people = list(assignable_users(project).order_by("first_name", "username"))
    return render(
        request,
        "projects/control/project.html",
        {
            **project_context(request, project, "control"),
            "sections": sections,
            "people": people,
            "can_reassign": has_perm(request.user, "task.reassign"),
            "followup_max": FOLLOW_UP_MAX,
        },
    )


# ================================================================== ACTIONS ===


def _task_for_control(request, pk):
    _require(can_control_projects(request.user))
    task = get_object_or_404(
        Task.objects.select_related("project", "assignee"),
        pk=pk,
        project__in=controlled_projects(request.user),
    )
    if not can_manage_project(request.user, task.project):
        raise PermissionDenied
    return task


@login_required
@require_POST
def task_reassign(request, pk):
    """Pindahkan penugasan task (permission ``task.reassign``, R3.5)."""
    task = _task_for_control(request, pk)
    _require(has_perm(request.user, "task.reassign"))
    fallback = reverse("projects:project_control", args=[task.project_id])
    candidates = assignable_users(task.project, task.assignee_id)
    new = candidates.filter(pk=_int(request.POST.get("assignee"))).first()
    if new is None:
        messages.error(request, "Pilih pelaksana dari daftar.")
        return redirect(_safe_next(request, fallback))
    problem = assignment_problem(new, task.project)
    if problem and new.pk != task.assignee_id:
        messages.error(request, problem)
        return redirect(_safe_next(request, fallback))
    if new.pk == task.assignee_id:
        messages.info(request, "Pelaksana tidak berubah.")
        return redirect(_safe_next(request, fallback))
    old_name = user_display(task.assignee) if task.assignee_id else "belum ditugaskan"
    task.assignee = new
    task.save(update_fields=["assignee", "updated_at"])
    record_activity(
        task.project,
        request.user,
        ActivityAction.TASK_ASSIGNED,
        f'Task "{task.title}" dipindahkan dari {old_name} ke {user_display(new)}.',
        target=task,
    )
    messages.success(request, f"Task dipindahkan ke {user_display(new)}.")
    return redirect(_safe_next(request, fallback))


@login_required
@require_POST
def task_follow_up(request, pk):
    """Kirim tindak lanjut ke pelaksana: komentar pada task plus notifikasi (R4.3)."""
    task = _task_for_control(request, pk)
    fallback = reverse("projects:project_control", args=[task.project_id])
    message = (request.POST.get("message") or "").strip()[:FOLLOW_UP_MAX]
    if not message:
        messages.error(request, "Tulis pesan tindak lanjut.")
        return redirect(_safe_next(request, fallback))
    recipients = [task.assignee] if task.assignee_id else []
    recipients += list(task.collaborators.all())
    if not recipients:
        messages.error(request, "Task ini belum punya pelaksana. Tugaskan seseorang dulu.")
        return redirect(_safe_next(request, fallback))
    comment = TaskComment.objects.create(
        task=task, author=request.user, content=f"Tindak lanjut: {message}"
    )
    record_activity(
        task.project,
        request.user,
        ActivityAction.COMMENT_ADDED,
        f'Tindak lanjut dikirim untuk task "{task.title}".',
    )
    notify(
        request.user,
        "task.follow_up",
        task,
        recipients=recipients,
        title=f"Tindak lanjut: {task.title}",
        body=f"{user_display(request.user)}: {message}",
        url=reverse("work:task_detail", args=[task.pk]),
        dedupe_suffix=f"followup:{comment.pk}",
        project=task.project,
        allow_management=False,
    )
    messages.success(request, "Tindak lanjut terkirim.")
    return redirect(_safe_next(request, fallback))

