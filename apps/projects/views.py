from collections import Counter

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.identity.permissions import (
    can_create_project,
    can_edit_task,
    can_manage_project,
    can_report_issue,
    is_pm,
    visible_projects,
)
from apps.work.models import TASK_STATUS_LABELS, Issue, Task, TaskStatus

from .forms import BaselinePointForm, DecisionForm, MilestoneForm, NoteForm, PhaseForm, ProjectForm
from .models import (
    ActivityAction,
    Decision,
    Milestone,
    MilestoneStatus,
    Note,
    Phase,
    ProgressBaselinePoint,
    ProjectStatus,
)
from .pagination import paginate
from .search import search_workspace
from .services import (
    actual_progress,
    planned_progress_on,
    record_activity,
    record_snapshot,
    timeline_data,
    variance,
    variance_level,
)

PROJECT_TABS = [
    ("overview", "Ringkasan"),
    ("progress", "Progress"),
    ("timeline", "Jadwal"),
    ("tasks", "Pekerjaan"),
    ("issues", "Masalah"),
    ("milestones", "Milestone"),
    ("notes", "Catatan"),
    ("activity", "Aktivitas"),
]

STATUS_CHOICES = ProjectStatus.choices


def _project_qs(user, *, include_archived=False):
    return (
        visible_projects(user, include_archived=include_archived)
        .select_related("manager")
        .prefetch_related("baseline_points", "tasks__subtasks", "milestones", "phases")
    )


def project_context(request, project, active_tab):
    return {
        "project": project,
        "tabs": PROJECT_TABS,
        "active_tab": active_tab,
        "can_manage": can_manage_project(request.user, project),
        "can_report": can_report_issue(request.user),
    }


def _project_or_404(request, pk, *, rich=False):
    return get_object_or_404(_project_qs(request.user), pk=pk)


# ============================================================== DASHBOARD ===


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    projects = list(_project_qs(request.user))
    by_status = Counter(p.status for p in projects)
    rows = [
        {
            "project": p,
            "planned": planned_progress_on(p),
            "actual": actual_progress(p),
            "variance": variance(p),
            "level": p.variance_level,
            "next_milestone": p.next_milestone,
        }
        for p in projects
    ]
    from .services import project_health

    attention = []
    for row in rows:
        project = row["project"]
        health = project_health(project)
        blocked = project.tasks.filter(status=TaskStatus.BLOCKED).count()
        milestone = row["next_milestone"]
        reasons = []
        if project.status in (ProjectStatus.COMPLETED, ProjectStatus.CANCELLED):
            continue
        if health["schedule"] in ("delayed", "at_risk"):
            reasons.append(
                "Progress tertinggal" if not project.is_overdue else "Target project terlewat"
            )
        if project.status in (ProjectStatus.DELAYED, ProjectStatus.AT_RISK):
            reasons.append(project.get_status_display())
        if health["critical_issues"]:
            reasons.append(f"{health['critical_issues']} issue kritis")
        if blocked:
            reasons.append(f"{blocked} task terhambat")
        if milestone and milestone.date <= timezone.localdate() + timezone.timedelta(days=7):
            reasons.append(f"Milestone: {milestone.name}")
        if reasons:
            attention.append(
                {
                    **row,
                    "reasons": reasons,
                    "blocked": blocked,
                    "priority": health["critical_issues"] * 10
                    + blocked * 2
                    + int(health["schedule"] == "delayed") * 5,
                }
            )
    attention.sort(key=lambda row: (-row["priority"], row["project"].target_end_date))
    return render(
        request,
        "projects/portfolio/dashboard.html",
        {
            "rows": rows,
            "can_create": can_create_project(request.user),
            "attention": attention,
            "portfolio_actual": sum(row["actual"] for row in rows) / len(rows) if rows else 0,
            "chart_rows": rows[:6],
            "today": timezone.localdate(),
            "counts": {
                "total": len(projects),
                "on_track": by_status.get(ProjectStatus.ON_TRACK, 0),
                "at_risk": by_status.get(ProjectStatus.AT_RISK, 0),
                "delayed": by_status.get(ProjectStatus.DELAYED, 0),
            },
        },
    )


# =========================================================== PROJECT LIST ===


@login_required
def project_list(request: HttpRequest) -> HttpResponse:
    can_view_archived = request.user.is_staff or is_pm(request.user)
    show_archived = request.GET.get("archived") == "1" and can_view_archived
    qs = _project_qs(request.user, include_archived=show_archived)
    if show_archived:
        qs = qs.filter(archived_at__isnull=False)
    search = (request.GET.get("q") or "").strip()
    status = request.GET.get("status") or ""
    pm = request.GET.get("pm") or ""
    team = request.GET.get("team") or ""

    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(code__icontains=search))
    if status in ProjectStatus.values:
        qs = qs.filter(status=status)
    if pm:
        qs = qs.filter(manager__username=pm)
    if team:
        qs = qs.filter(team__iexact=team)

    from decimal import Decimal, InvalidOperation

    from django.utils.dateparse import parse_date

    date_from, date_to = request.GET.get("from", ""), request.GET.get("to", "")
    phase = request.GET.get("phase", "")
    progress_min = request.GET.get("progress_min", "")
    progress_max = request.GET.get("progress_max", "")
    try:
        first, last = parse_date(date_from), parse_date(date_to)
        if (date_from and not first) or (date_to and not last) or (first and last and first > last):
            raise ValueError
    except ValueError:
        first = last = None
        messages.error(request, "Rentang tanggal tidak valid. Periksa tanggal mulai dan akhir.")
    if first:
        qs = qs.filter(target_end_date__gte=first)
    if last:
        qs = qs.filter(start_date__lte=last)
    projects = list(qs)
    if phase:
        projects = [
            p
            for p in projects
            if p.effective_current_phase and p.effective_current_phase.name == phase
        ]
    try:
        minimum = Decimal(progress_min) if progress_min else Decimal(0)
        maximum = Decimal(progress_max) if progress_max else Decimal(100)
        if not minimum.is_finite() or not maximum.is_finite() or not 0 <= minimum <= maximum <= 100:
            raise ValueError
        if progress_min or progress_max:
            projects = [p for p in projects if minimum <= actual_progress(p) <= maximum]
    except (InvalidOperation, ValueError):
        messages.error(
            request,
            (
                "Rentang progress harus berupa angka 0–100; "
                "minimum tidak boleh lebih besar dari maksimum."
            ),
        )
    rows = [
        {
            "project": p,
            "planned": planned_progress_on(p),
            "actual": actual_progress(p),
            "variance": variance(p),
            "level": p.variance_level,
            "next_milestone": p.next_milestone,
            "can_restore": can_manage_project(request.user, p),
        }
        for p in projects
    ]
    page_obj = paginate(request, rows, 20)
    view = request.GET.get("view") or "list"
    if show_archived:
        view = "list"
    elif view not in {"list", "card"}:
        view = "list"
    archived_count = (
        visible_projects(request.user, include_archived=True)
        .filter(archived_at__isnull=False)
        .count()
        if can_view_archived
        else 0
    )

    # opsi filter
    teams = [
        t
        for t in visible_projects(request.user)
        .exclude(team="")
        .values_list("team", flat=True)
        .distinct()
        .order_by("team")
        if t
    ]
    pms = list(
        User.objects.filter(Q(managed_projects__in=visible_projects(request.user)))
        .distinct()
        .order_by("first_name", "username")
    )
    return render(
        request,
        "projects/portfolio/list.html",
        {
            "rows": page_obj,
            "page_obj": page_obj,
            "total_rows": page_obj.paginator.count,
            "show_archived": show_archived,
            "can_view_archived": can_view_archived,
            "archived_count": archived_count,
            "view": view,
            "filters": {
                "q": search,
                "status": status,
                "pm": pm,
                "team": team,
                "from": date_from,
                "to": date_to,
                "phase": phase,
                "progress_min": progress_min,
                "progress_max": progress_max,
            },
            "status_choices": STATUS_CHOICES,
            "teams": teams,
            "phases": sorted(
                set(
                    p.effective_current_phase.name
                    for p in visible_projects(request.user)
                    if p.effective_current_phase
                )
            ),
            "pms": pms,
            "can_create": can_create_project(request.user),
        },
    )


# ========================================================== PROJECT DETAIL ===


@login_required
def project_detail(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(request, pk)
    health = project.health()
    data = timeline_data(project)
    current_work = list(
        project.tasks.filter(status=TaskStatus.IN_PROGRESS)
        .select_related("assignee")
        .order_by("due_date")
    )
    next_up = list(
        project.tasks.filter(status__in=[TaskStatus.TODO, TaskStatus.BACKLOG])
        .select_related("assignee")
        .exclude(
            dependencies__isnull=False,
            dependencies__status__in=[s for s in TaskStatus.values if s != TaskStatus.DONE],
        )
        .distinct()
        .order_by("order", "start_date", "due_date")[:8]
    )
    open_issues = list(
        project.issues.filter(status__in=["open", "in_progress", "blocked"]).select_related(
            "owner", "task"
        )[:6]
    )
    activities = project.activities.select_related("actor")[:8]
    milestones = list(project.milestones.all()) if project.next_milestone else []
    baseline = list(project.baseline_points.all())
    snapshots = list(project.snapshots.all())

    return render(
        request,
        "projects/project/overview.html",
        {
            **project_context(request, project, "overview"),
            "health": health,
            "blocked_work": project.tasks.filter(status=TaskStatus.BLOCKED).select_related(
                "assignee"
            ),
            **data,
            "blocked_timeline_rows": [
                row for row in data["timeline_rows"] if row["task"].is_blocked
            ],
            "current_work": current_work,
            "next_up": next_up,
            "completed_work": project.tasks.filter(status=TaskStatus.DONE).select_related(
                "assignee"
            ),
            "open_issues": open_issues,
            "activities": activities,
            "milestones": milestones,
            "chart": progress_chart_data(baseline, snapshots, actual_progress(project)),
            "chart_has_plan": bool(baseline),
        },
    )


def progress_chart_data(baseline, snapshots, live_actual):
    """Daily axis with interpolated plan and gaps spanning observed snapshots."""
    today = timezone.localdate()
    planned = {p.date: float(p.planned_percent) for p in baseline}
    actual = {
        s.date: float(s.actual_progress)
        for s in snapshots
        if s.actual_progress is not None and s.date <= today
    }
    actual[today] = float(live_actual)
    dates = sorted(set(planned) | set(actual))
    first, last = dates[0], dates[-1]
    labels = [first + timezone.timedelta(days=i) for i in range((last - first).days + 1)]
    points = sorted(planned)

    def plan(day):
        if not points:
            return None
        if day <= points[0]:
            return planned[points[0]]
        if day >= points[-1]:
            return planned[points[-1]]
        for left, right in zip(points, points[1:], strict=False):
            if left <= day <= right:
                return (
                    planned[left]
                    + (planned[right] - planned[left]) * (day - left).days / (right - left).days
                )

    return {
        "labels": [d.strftime("%d %b %Y") for d in labels],
        "iso": [d.isoformat() for d in labels],
        "planned": [plan(d) for d in labels],
        "actual": [actual.get(d) for d in labels],
        "today_index": labels.index(today),
    }


# ------------------------------------------------------------- create/edit ---


@login_required
def project_create(request: HttpRequest) -> HttpResponse:
    if not can_create_project(request.user):
        return redirect("projects:project_list")
    form = ProjectForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        project = form.save()
        record_activity(
            project,
            request.user,
            ActivityAction.PROJECT_CREATED,
            f'Project "{project.name}" created ({project.code}).',
        )
        messages.success(request, f"Project {project.code} dibuat.")
        return redirect("projects:project_detail", pk=project.pk)
    return render(
        request,
        "projects/forms/project_form.html",
        {"form": form, "project": None, "title": "Buat project"},
    )


@login_required
def project_edit(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(request, pk)
    if not can_manage_project(request.user, project):
        messages.error(request, "Anda tidak berhak mengedit project ini.")
        return redirect("projects:project_detail", pk=pk)
    form = ProjectForm(request.POST or None, instance=project, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        record_activity(
            project,
            request.user,
            ActivityAction.PROJECT_UPDATED,
            f'Project details updated ("{project.name}").',
        )
        messages.success(request, "Project disimpan.")
        return redirect("projects:project_detail", pk=pk)
    return render(
        request,
        "projects/forms/project_form.html",
        {"form": form, "project": project, "title": f"Edit {project.code}"},
    )


# ------------------------------------------------------------------- tabs ---


def _open_issues(project):
    return (
        project.issues.filter(status__in=["open", "in_progress", "blocked"])
        .select_related("owner", "task")
        .order_by("-severity", "-priority", "-created_at")
    )


@login_required
def project_progress(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(request, pk)
    baseline = list(project.baseline_points.all())
    snapshots = list(project.snapshots.all())
    recent_snapshots = snapshots[-14:]
    return render(
        request,
        "projects/project/progress.html",
        {
            **project_context(request, project, "progress"),
            "baseline": baseline,
            "snapshots": recent_snapshots,
            "chart": progress_chart_data(baseline, snapshots, actual_progress(project)),
            "chart_has_plan": bool(baseline),
            "variance": variance(project),
            "variance_level": variance_level(project),
            "planned": planned_progress_on(project),
            "actual": actual_progress(project),
            "baseline_form": BaselinePointForm(initial={"date": timezone.localdate().isoformat()}),
            "status_choices": STATUS_CHOICES,
        },
    )


@login_required
def project_timeline(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(request, pk)
    data = timeline_data(project)
    for row in data["timeline_rows"]:
        row["can_edit"] = can_edit_task(request.user, row["task"])
    archived_phases = []
    if can_manage_project(request.user, project):
        archived_phases = list(
            Phase.all_objects.filter(project=project, archived_at__isnull=False).order_by(
                "sequence"
            )
        )
    return render(
        request,
        "projects/project/timeline.html",
        {
            **project_context(request, project, "timeline"),
            **data,
            "phases": project.phases.all(),
            "archived_phases": archived_phases,
        },
    )


@login_required
def project_tasks(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(request, pk)
    by_status = {status: [] for status in TaskStatus.values}
    custom_columns = list(
        project.board_columns.prefetch_related(
            "feedback_cards__owner", "feedback_cards__linked_task"
        )
    )
    by_column = {column.pk: [] for column in custom_columns}
    tasks = (
        project.tasks.select_related("assignee", "phase", "parent_task")
        .prefetch_related("issues", "collaborators", "subtasks__assignee")
        .order_by("order", "due_date")
    )
    for task in tasks:
        task.can_edit = can_edit_task(request.user, task)
        if task.board_column_id in by_column:
            by_column[task.board_column_id].append(task)
        else:
            by_status[task.status].append(task)
    for column in custom_columns:
        column.board_tasks = by_column[column.pk]
    columns = [(status, by_status[status]) for status in TaskStatus.values]
    archived_tasks = []
    if can_manage_project(request.user, project):
        archived_tasks = list(
            Task.all_objects.filter(
                project=project, archived_at__isnull=False, parent_task__isnull=True
            )
            .select_related("assignee", "phase")
            .order_by("-archived_at")[:100]
        )
    return render(
        request,
        "projects/project/tasks.html",
        {
            **project_context(request, project, "tasks"),
            "columns": columns,
            "custom_columns": custom_columns,
            "status_labels": TASK_STATUS_LABELS,
            "archived_tasks": archived_tasks,
        },
    )


@login_required
def project_issues(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(request, pk)
    open_issues = list(_open_issues(project))
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    open_issues.sort(key=lambda issue: severity_order.get(issue.severity, 4))
    issue_counts = Counter(issue.severity for issue in open_issues)
    selected_severity = request.GET.get("severity", "all")
    if selected_severity in severity_order:
        open_issues = [issue for issue in open_issues if issue.severity == selected_severity]
    page_obj = paginate(request, open_issues, 20)
    resolved = list(
        project.issues.filter(status__in=["resolved", "closed"])
        .select_related("owner", "task")
        .order_by("-resolved_at", "-updated_at")[:10]
    )
    archived_issues = []
    if can_manage_project(request.user, project):
        archived_issues = list(
            Issue.all_objects.filter(project=project, archived_at__isnull=False)
            .select_related("owner", "task")
            .order_by("-archived_at")[:100]
        )
    return render(
        request,
        "projects/project/issues.html",
        {
            **project_context(request, project, "issues"),
            "open_issues": page_obj,
            "page_obj": page_obj,
            "resolved_issues": resolved,
            "archived_issues": archived_issues,
            "issue_counts": issue_counts,
            "selected_severity": selected_severity,
            "risks": project.risks.select_related("owner").all(),
        },
    )


@login_required
def project_milestones(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(request, pk)
    milestones = project.milestones.select_related("owner").all()
    return render(
        request,
        "projects/project/milestones.html",
        {
            **project_context(request, project, "milestones"),
            "milestones": milestones,
            "milestone_form": MilestoneForm(initial={"status": MilestoneStatus.UPCOMING}),
        },
    )


@login_required
def project_notes(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(request, pk)
    notes = project.notes.select_related("author").all()
    decisions = project.decisions.select_related("decision_maker").all()
    entries = [{"kind": "note", "item": n, "date": n.created_at} for n in notes] + [
        {"kind": "decision", "item": d, "date": d.created_at} for d in decisions
    ]
    entries.sort(key=lambda entry: entry["date"], reverse=True)
    selected = request.GET.get("type", "all")
    if selected in {"note", "decision"}:
        entries = [entry for entry in entries if entry["kind"] == selected]
    page_obj = paginate(request, entries, 20)
    return render(
        request,
        "projects/project/notes.html",
        {
            **project_context(request, project, "notes"),
            "notes": notes,
            "decisions": decisions,
            "entries": page_obj,
            "page_obj": page_obj,
            "entry_type": selected,
        },
    )


@login_required
def project_activity(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(request, pk)
    activities = project.activities.select_related("actor").all()
    page_obj = paginate(request, activities, 30)
    return render(
        request,
        "projects/project/activity.html",
        {
            **project_context(request, project, "activity"),
            "activities": page_obj,
            "page_obj": page_obj,
        },
    )


# ---------------------------------------------------------- global pages ---


@login_required
def note_list(request: HttpRequest) -> HttpResponse:
    notes = Note.objects.select_related("project", "author").filter(
        project__in=visible_projects(request.user)
    )
    q = (request.GET.get("q") or "").strip()
    if q:
        notes = notes.filter(Q(title__icontains=q) | Q(content__icontains=q) | Q(tags__icontains=q))
    page_obj = paginate(request, notes, 24)
    return render(
        request,
        "projects/portfolio/notes.html",
        {"notes": page_obj, "page_obj": page_obj, "q": q},
    )


@login_required
def timeline_global(request: HttpRequest) -> HttpResponse:
    projects = list(_project_qs(request.user))
    rows = [
        {"project": p, "actual": actual_progress(p), "planned": planned_progress_on(p)}
        for p in projects
    ]
    return render(request, "projects/portfolio/timeline.html", {"rows": rows})


@login_required
def reports(request: HttpRequest) -> HttpResponse:
    projects = list(_project_qs(request.user))
    rows = []
    for p in projects:
        health = p.health()
        rows.append(
            {
                "project": p,
                "health": health,
                "planned": planned_progress_on(p),
                "actual": actual_progress(p),
                "variance": variance(p),
                "level": p.variance_level,
                "next_milestone": p.next_milestone,
            }
        )
    start = min((p.start_date for p in projects), default=timezone.localdate())
    end = max((p.target_end_date for p in projects), default=start)
    span = max((end - start).days + 1, 1)
    for row in rows:
        p = row["project"]
        row["left"] = round((p.start_date - start).days / span * 100, 3)
        row["width"] = round(((p.target_end_date - p.start_date).days + 1) / span * 100, 3)
        row["blocked"] = p.tasks.filter(status=TaskStatus.BLOCKED).count()
        row["done"] = p.tasks.filter(status=TaskStatus.DONE).count()
        row["task_count"] = p.tasks.count()
    totals = {
        "projects": len(rows),
        "completed": sum(row["project"].status == ProjectStatus.COMPLETED for row in rows),
        "attention": sum(
            row["project"].status in [ProjectStatus.AT_RISK, ProjectStatus.DELAYED]
            or row["level"] in ["at_risk", "delayed"]
            for row in rows
        ),
        "issues": sum(row["health"]["open_issues"] for row in rows),
        "blocked": sum(row["blocked"] for row in rows),
    }
    return render(
        request,
        "projects/portfolio/reports.html",
        {
            "rows": rows,
            "today": timezone.localdate(),
            "totals": totals,
            "portfolio_start": start,
            "portfolio_end": end,
        },
    )


# ============================================================== CRUD (PM) ===

PT = timezone.timedelta(days=1)


def _pm_check(request, project):
    if not can_manage_project(request.user, project):
        messages.error(request, "Aksi ini hanya untuk Project Manager.")
        return False
    return True


TAB_URL_NAMES = {
    "overview": "project_detail",
    "progress": "project_progress",
    "timeline": "project_timeline",
    "tasks": "project_tasks",
    "issues": "project_issues",
    "milestones": "project_milestones",
    "notes": "project_notes",
    "activity": "project_activity",
}


def _tab_redirect(pk, tab):
    return redirect("projects:" + TAB_URL_NAMES.get(tab, "project_detail"), pk=pk)


# --- phase ---


@login_required
def phase_create(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(request, pk)
    if not _pm_check(request, project):
        return redirect("projects:project_detail", pk=pk)
    form = PhaseForm(request.POST or None, project=project)
    if request.method == "POST" and form.is_valid():
        phase = form.save(commit=False)
        phase.project = project
        phase.save()
        record_activity(
            project,
            request.user,
            ActivityAction.PHASE_ADDED,
            f'Phase "{phase.name}" ditambahkan.',
        )
        messages.success(request, f"Phase {phase.name} ditambahkan.")
        return _tab_redirect(pk, "timeline")
    return render(
        request,
        "projects/forms/phase_form.html",
        {"form": form, "project": project, "title": "Tambah tahap"},
    )


# --- milestone ---


@login_required
def milestone_create(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(request, pk)
    if not _pm_check(request, project):
        return redirect("projects:project_detail", pk=pk)
    form = MilestoneForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        milestone = form.save(commit=False)
        milestone.project = project
        milestone.save()
        record_activity(
            project,
            request.user,
            ActivityAction.MILESTONE_ADDED,
            f'Milestone "{milestone.name}" ditambahkan ({milestone.date}).',
        )
        messages.success(request, f"Milestone {milestone.name} dibuat.")
        return _tab_redirect(pk, "milestones")
    return render(
        request,
        "projects/forms/milestone_form.html",
        {"form": form, "project": project, "title": "Tambah milestone"},
    )


@login_required
def milestone_update(request: HttpRequest, pk: int, mid: int) -> HttpResponse:
    project = _project_or_404(request, pk)
    if not _pm_check(request, project):
        return redirect("projects:project_detail", pk=pk)
    milestone = get_object_or_404(Milestone, pk=mid, project=project)
    form = MilestoneForm(request.POST or None, instance=milestone)
    if request.method == "POST" and form.is_valid():
        form.save()
        if milestone.status == MilestoneStatus.COMPLETED:
            record_activity(
                project,
                request.user,
                ActivityAction.MILESTONE_COMPLETED,
                f'Milestone "{milestone.name}" completed.',
                milestone.name,
            )
        else:
            record_activity(
                project,
                request.user,
                ActivityAction.MILESTONE_UPDATED,
                f'Milestone "{milestone.name}" dirubah.',
                milestone.name,
            )
        messages.success(request, "Milestone disimpan.")
        return _tab_redirect(pk, "milestones")
    return render(
        request,
        "projects/forms/milestone_form.html",
        {"form": form, "project": project, "title": milestone.name},
    )


@login_required
def milestone_delete(request: HttpRequest, pk: int, mid: int) -> HttpResponse:
    project = _project_or_404(request, pk)
    milestone = get_object_or_404(Milestone, pk=mid, project=project)
    if request.method == "POST" and _pm_check(request, project):
        name = milestone.name
        milestone.delete()
        record_activity(
            project,
            request.user,
            ActivityAction.MILESTONE_UPDATED,
            f'Milestone "{name}" dihapus.',
        )
    return _tab_redirect(pk, "milestones")


# --- baseline (planned progress) ---


@login_required
def baseline_add(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(request, pk)
    if not _pm_check(request, project):
        return _tab_redirect(pk, "progress")
    form = BaselinePointForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        point = form.save(commit=False)
        point.project = project
        existing = project.baseline_points.filter(date=point.date).exclude(pk=point.pk)
        previous = project.baseline_points.filter(date__lt=point.date).order_by("-date").first()
        following = project.baseline_points.filter(date__gt=point.date).order_by("date").first()
        if (
            existing.exists()
            or (previous and previous.planned_percent > point.planned_percent)
            or (following and following.planned_percent < point.planned_percent)
        ):
            messages.error(
                request, "Baseline harus unik per tanggal dan progress tidak boleh menurun."
            )
            return _tab_redirect(pk, "progress")
        point.save()
        record_activity(
            project,
            request.user,
            ActivityAction.BASELINE_UPDATED,
            f"Baseline point {point.date} → {point.planned_percent}% ditambahkan.",
        )
        messages.success(request, "Baseline point ditambahkan.")
    if request.method == "POST" and form.errors:
        messages.error(request, "Baseline tidak valid. Periksa tanggal dan progress 0–100%.")
    return _tab_redirect(pk, "progress")


@login_required
def baseline_delete(request: HttpRequest, pk: int, bpid: int) -> HttpResponse:
    project = _project_or_404(request, pk)
    point = get_object_or_404(ProgressBaselinePoint, pk=bpid, project=project)
    if request.method == "POST" and _pm_check(request, project):
        record_activity(
            project,
            request.user,
            ActivityAction.BASELINE_UPDATED,
            f"Baseline point {point.date} dihapus.",
        )
        point.delete()
    return _tab_redirect(pk, "progress")


@login_required
def snapshot_now(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(request, pk)
    if request.method == "POST" and _pm_check(request, project):
        record_snapshot(project)
        record_activity(
            project,
            request.user,
            ActivityAction.PROGRESS_UPDATED,
            "Snapshot progress hari ini disimpan.",
        )
        messages.success(request, "Snapshot progress disimpan.")
    return _tab_redirect(pk, "progress")


# --- notes & decisions ---


@login_required
def note_create(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(request, pk)
    if not _pm_check(request, project):
        return _tab_redirect(pk, "notes")
    form = NoteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        note = form.save(commit=False)
        note.project = project
        note.author = request.user
        note.save()
        record_activity(
            project, request.user, ActivityAction.NOTE_ADDED, f'Note "{note.title}" added.'
        )
        messages.success(request, "Note disimpan.")
        return _tab_redirect(pk, "notes")
    return render(
        request,
        "projects/forms/note_form.html",
        {"form": form, "project": project, "title": "Tambah catatan"},
    )


@login_required
def note_edit(request: HttpRequest, pk: int, nid: int) -> HttpResponse:
    project = _project_or_404(request, pk)
    if not _pm_check(request, project):
        return _tab_redirect(pk, "notes")
    note = get_object_or_404(Note, pk=nid, project=project)
    form = NoteForm(request.POST or None, instance=note)
    if request.method == "POST" and form.is_valid():
        note = form.save()
        record_activity(
            project, request.user, ActivityAction.NOTE_UPDATED, f'Note "{note.title}" updated.'
        )
        messages.success(request, "Note disimpan.")
        return _tab_redirect(pk, "notes")
    return render(
        request,
        "projects/forms/note_form.html",
        {"form": form, "project": project, "title": note.title},
    )


@login_required
def note_delete(request: HttpRequest, pk: int, nid: int) -> HttpResponse:
    project = _project_or_404(request, pk)
    note = get_object_or_404(Note, pk=nid, project=project)
    if request.method == "POST" and _pm_check(request, project):
        note.delete()
        messages.success(request, "Note dihapus.")
    return _tab_redirect(pk, "notes")


@login_required
def decision_create(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(request, pk)
    if not _pm_check(request, project):
        return _tab_redirect(pk, "notes")
    form = DecisionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        decision = form.save(commit=False)
        decision.project = project
        decision.save()
        record_activity(
            project,
            request.user,
            ActivityAction.DECISION_ADDED,
            f'Decision "{decision.title}" dicatat.',
        )
        messages.success(request, "Decision dicatat.")
        return _tab_redirect(pk, "notes")
    return render(
        request,
        "projects/forms/decision_form.html",
        {"form": form, "project": project, "title": "Catat keputusan"},
    )


@login_required
def decision_delete(request: HttpRequest, pk: int, did: int) -> HttpResponse:
    project = _project_or_404(request, pk)
    decision = get_object_or_404(Decision, pk=did, project=project)
    if request.method == "POST" and _pm_check(request, project):
        decision.delete()
        messages.success(request, "Decision dihapus.")
    return _tab_redirect(pk, "notes")


@login_required
def project_members(request, pk):
    from .forms import MembersForm

    project = _project_or_404(request, pk)
    if not can_manage_project(request.user, project):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied
    form = MembersForm(request.POST if request.method == "POST" else None, instance=project)
    if request.method == "POST" and form.is_valid():
        form.save()
        record_activity(
            project, request.user, ActivityAction.PROJECT_UPDATED, "Anggota project diperbarui."
        )
        messages.success(request, "Anggota project disimpan.")
        return redirect("projects:project_members", pk=pk)
    return render(
        request,
        "projects/project/members.html",
        {**project_context(request, project, "members"), "form": form},
    )


@login_required
def risk_edit(request, pk, rid=None):
    from .forms import RiskForm
    from .models import Risk

    project = _project_or_404(request, pk)
    risk = get_object_or_404(Risk, pk=rid, project=project) if rid else None
    if not can_manage_project(request.user, project):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied
    form = RiskForm(request.POST or None, instance=risk)
    if request.method == "POST" and form.is_valid():
        risk = form.save(commit=False)
        risk.project = project
        risk.save()
        record_activity(
            project,
            request.user,
            ActivityAction.PROJECT_UPDATED,
            f'Risiko "{risk.title}" diperbarui.',
        )
        messages.success(request, "Risiko disimpan.")
        return redirect("projects:project_issues", pk=pk)
    return render(
        request,
        "projects/forms/risk_form.html",
        {"project": project, "form": form, "title": "Risiko project"},
    )


@login_required
def capture_timeline_baseline(request, pk):
    from .services import capture_baseline

    project = _project_or_404(request, pk)
    if request.method != "POST":
        return HttpResponse(status=405)
    if not _pm_check(request, project):
        return _tab_redirect(pk, "timeline")
    from django.core.exceptions import ValidationError

    try:
        capture_baseline(project, request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return _tab_redirect(pk, "timeline")
    messages.success(request, "Baseline timeline dan kurva planned progress disimpan.")
    return _tab_redirect(pk, "timeline")


@login_required
def phase_edit(request, pk, phase_id):
    project = _project_or_404(request, pk)
    phase = get_object_or_404(Phase, project=project, pk=phase_id)
    if not _pm_check(request, project):
        return _tab_redirect(pk, "timeline")
    form = PhaseForm(request.POST or None, instance=phase, project=project)
    if request.method == "POST" and form.is_valid():
        phase = form.save()
        record_activity(
            project, request.user, ActivityAction.PHASE_UPDATED, f'Phase "{phase.name}" diperbarui.'
        )
        messages.success(request, "Phase disimpan.")
        return _tab_redirect(pk, "timeline")
    return render(
        request,
        "projects/forms/phase_form.html",
        {"project": project, "form": form, "title": "Edit tahap"},
    )


@login_required
def nav_search(request: HttpRequest) -> HttpResponse:
    """Live suggestions for the workspace navbar search."""
    query = request.GET.get("q", "").strip()
    results = search_workspace(request.user, query, limit=5)
    return render(
        request,
        "projects/partials/_nav_search_results.html",
        {"query": query, **results},
    )


@login_required
def search(request: HttpRequest) -> HttpResponse:
    query = request.GET.get("q", "").strip()
    results = search_workspace(request.user, query, limit=50)
    return render(
        request,
        "projects/portfolio/search.html",
        {"query": query, **results},
    )


@login_required
@require_POST
def project_archive(request: HttpRequest, pk: int) -> HttpResponse:
    project = get_object_or_404(visible_projects(request.user, include_archived=True), pk=pk)
    if not can_manage_project(request.user, project):
        raise PermissionDenied
    if project.archive(request.user):
        record_activity(
            project,
            request.user,
            ActivityAction.PROJECT_ARCHIVED,
            f'Project "{project.name}" diarsipkan.',
        )
        messages.success(request, "Project diarsipkan. Pulihkan dari daftar arsip.")
    else:
        messages.info(request, "Project sudah diarsipkan.")
    return redirect("projects:project_list")


@login_required
@require_POST
def project_restore(request: HttpRequest, pk: int) -> HttpResponse:
    project = get_object_or_404(visible_projects(request.user, include_archived=True), pk=pk)
    if not can_manage_project(request.user, project):
        raise PermissionDenied
    if project.restore():
        record_activity(
            project,
            request.user,
            ActivityAction.PROJECT_RESTORED,
            f'Project "{project.name}" dipulihkan dari arsip.',
        )
        messages.success(request, "Project dipulihkan.")
    else:
        messages.info(request, "Project tidak sedang diarsipkan.")
    return redirect(f"{reverse('projects:project_list')}?archived=1")


@login_required
@require_POST
def phase_archive(request: HttpRequest, pk: int, phase_id: int) -> HttpResponse:
    project = _project_or_404(request, pk)
    if not _pm_check(request, project):
        return _tab_redirect(pk, "timeline")
    phase = get_object_or_404(Phase.all_objects, project=project, pk=phase_id)
    if phase.archive(request.user):
        record_activity(
            project,
            request.user,
            ActivityAction.PHASE_ARCHIVED,
            f'Phase "{phase.name}" diarsipkan bersama task di dalamnya.',
        )
        messages.success(request, "Phase diarsipkan.")
    else:
        messages.info(request, "Phase sudah diarsipkan.")
    return _tab_redirect(pk, "timeline")


@login_required
@require_POST
def phase_restore(request: HttpRequest, pk: int, phase_id: int) -> HttpResponse:
    project = _project_or_404(request, pk)
    if not _pm_check(request, project):
        return _tab_redirect(pk, "timeline")
    phase = get_object_or_404(Phase.all_objects, project=project, pk=phase_id)
    if Phase.objects.filter(project=project, sequence=phase.sequence).exists():
        messages.error(
            request,
            "Urutan phase ini sudah dipakai phase aktif lain. Ubah urutan phase tersebut dulu.",
        )
        return _tab_redirect(pk, "timeline")
    if phase.restore():
        record_activity(
            project,
            request.user,
            ActivityAction.PHASE_RESTORED,
            f'Phase "{phase.name}" dipulihkan dari arsip.',
        )
        messages.success(request, "Phase dipulihkan.")
    else:
        messages.info(request, "Phase tidak sedang diarsipkan.")
    return _tab_redirect(pk, "timeline")
