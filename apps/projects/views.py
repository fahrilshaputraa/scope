from collections import Counter

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.identity.permissions import can_create_project, can_manage_project
from apps.work.models import TaskStatus

from .forms import BaselinePointForm, DecisionForm, MilestoneForm, NoteForm, PhaseForm, ProjectForm
from .models import (
    ActivityAction,
    Decision,
    Milestone,
    MilestoneStatus,
    Note,
    ProgressBaselinePoint,
    Project,
    ProjectStatus,
)
from .services import (
    actual_progress,
    planned_progress_on,
    record_activity,
    record_snapshot,
    variance,
    variance_level,
)

PROJECT_TABS = [
    ("overview", "Overview"),
    ("progress", "Progress"),
    ("timeline", "Timeline"),
    ("tasks", "Tasks"),
    ("issues", "Issues"),
    ("milestones", "Milestones"),
    ("notes", "Notes"),
    ("activity", "Activity"),
]

STATUS_CHOICES = ProjectStatus.choices


def _project_qs():
    return Project.objects.select_related("manager").prefetch_related(
        "baseline_points", "tasks", "milestones", "phases"
    )


def project_context(request, project, active_tab):
    return {
        "project": project,
        "tabs": PROJECT_TABS,
        "active_tab": active_tab,
        "can_manage": can_manage_project(request.user, project),
    }


def _project_or_404(pk, *, rich=False):
    qs = Project.objects.select_related("manager").prefetch_related(
        "baseline_points", "tasks", "milestones", "phases"
    )
    return get_object_or_404(qs, pk=pk)


# ============================================================== DASHBOARD ===


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    projects = list(_project_qs())
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
    return render(
        request,
        "projects/dashboard.html",
        {
            "rows": rows,
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
    qs = _project_qs()
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

    rows = [
        {
            "project": p,
            "planned": planned_progress_on(p),
            "actual": actual_progress(p),
            "variance": variance(p),
            "level": p.variance_level,
            "next_milestone": p.next_milestone,
        }
        for p in qs
    ]
    view = request.GET.get("view") or "list"
    if view not in {"list", "card"}:
        view = "list"

    # opsi filter
    teams = [
        t
        for t in Project.objects
        .exclude(team="")
        .values_list("team", flat=True)
        .distinct()
        .order_by("team")
        if t
    ]
    pms = list(
        User.objects.filter(
            Q(managed_projects__isnull=False)
        )
        .distinct()
        .order_by("first_name", "username")
    )
    return render(
        request,
        "projects/project_list.html",
        {
            "rows": rows,
            "view": view,
            "filters": {"q": search, "status": status, "pm": pm, "team": team},
            "status_choices": STATUS_CHOICES,
            "teams": teams,
            "pms": pms,
            "can_create": can_create_project(request.user),
        },
    )


# ========================================================== PROJECT DETAIL ===


@login_required
def project_detail(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(pk)
    health = project.health()
    current_work = list(
        project.tasks.filter(status=TaskStatus.IN_PROGRESS).select_related("assignee").order_by("due_date")
    )
    next_up = list(
        project.tasks.filter(
            status__in=[TaskStatus.TODO, TaskStatus.BACKLOG, TaskStatus.BLOCKED]
        )
        .select_related("assignee")
        .order_by("order", "due_date")[:8]
    )
    open_issues = list(
        project.issues.filter(status__in=["open", "in_progress", "blocked"])
        .select_related("owner", "task")[:6]
    )
    activities = project.activities.select_related("actor")[:8]
    milestones = list(project.milestones.all()) if project.next_milestone else []
    baseline = list(project.baseline_points.all())
    snapshots = list(project.snapshots.all())

    return render(
        request,
        "projects/overview.html",
        {
            **project_context(request, project, "overview"),
            "health": health,
            "current_work": current_work,
            "next_up": next_up,
            "open_issues": open_issues,
            "activities": activities,
            "milestones": milestones,
            "chart": progress_chart_data(baseline, snapshots, actual_progress(project)),
            "chart_has_plan": bool(baseline),
        },
    )


def progress_chart_data(baseline, snapshots, live_actual):
    """Data chart Plan vs Actual — format label-based (tanpa time adapter)."""
    today = timezone.localdate()
    planned = {p.date: float(p.planned_percent) for p in baseline}
    actual = {s.date: float(s.actual_progress or 0) for s in snapshots}
    if today not in actual:
        actual[today] = float(live_actual)
    labels = sorted(set(planned) | set(actual))
    return {
        "labels": [d.strftime("%d %b") for d in labels],
        "iso": [d.isoformat() for d in labels],
        "planned": [planned.get(d) for d in labels],
        "actual": [actual.get(d) for d in labels],
    }


# ------------------------------------------------------------- create/edit ---


@login_required
def project_create(request: HttpRequest) -> HttpResponse:
    if not can_create_project(request.user):
        return redirect("projects:project_list")
    form = ProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        project = form.save()
        record_activity(
            project, request.user, ActivityAction.PROJECT_CREATED,
            f'Project "{project.name}" created ({project.code}).',
        )
        messages.success(request, f"Project {project.code} dibuat.")
        return redirect("projects:project_detail", pk=project.pk)
    return render(
        request,
        "projects/project_form.html",
        {"form": form, "project": None, "title": "New Project"},
    )


@login_required
def project_edit(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(pk)
    if not can_manage_project(request.user, project):
        messages.error(request, "Anda tidak berhak mengedit project ini.")
        return redirect("projects:project_detail", pk=pk)
    form = ProjectForm(request.POST or None, instance=project)
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
        request, "projects/project_form.html",
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
    project = _project_or_404(pk)
    baseline = list(project.baseline_points.all())
    snapshots = list(project.snapshots.all())
    recent_snapshots = snapshots[-14:]
    return render(
        request,
        "projects/progress.html",
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
            "baseline_form": BaselinePointForm(
                initial={"date": timezone.localdate().isoformat()}
            ),
            "status_choices": STATUS_CHOICES,
        },
    )


@login_required
def project_timeline(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(pk)
    tasks = list(
        project.tasks.select_related("assignee", "phase").order_by("phase__sequence", "start_date")
    )
    phases = list(project.phases.all())
    gantt = [
        {
            "id": str(t.id),
            "name": t.title,
            "start": (t.start_date or project.start_date).isoformat(),
            "end": (
                (t.due_date or t.start_date or project.start_date)
                + timezone.timedelta(days=1)
            ).isoformat(),
            "progress": float(
                t.progress if not t.is_done else 100
            ),
            "project": project.name,
            "phase": t.phase.name if t.phase else "",
        }
        for t in tasks
    ]
    return render(
        request,
        "projects/timeline.html",
        {
            **project_context(request, project, "timeline"),
            "tasks": tasks,
            "phases": phases,
            "gantt_tasks": gantt,
            "phase_form": PhaseForm(),
        },
    )


@login_required
def project_tasks(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(pk)
    by_status = {status: [] for status in TaskStatus.values}
    tasks = (
        project.tasks.select_related("assignee", "phase")
        .prefetch_related("issues")
        .order_by("order", "due_date")
    )
    for task in tasks:
        by_status[task.status].append(task)
    columns = [(status, by_status[status]) for status in TaskStatus.values]
    return render(
        request,
        "projects/tasks.html",
        {
            **project_context(request, project, "tasks"),
            "columns": columns,
            "status_labels": TaskStatus.choices,
        },
    )


@login_required
def project_issues(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(pk)
    open_issues = list(_open_issues(project))
    resolved = list(
        project.issues.filter(status__in=["resolved", "closed"])
        .select_related("owner", "task")
        .order_by("-resolved_at", "-updated_at")[:10]
    )
    return render(
        request,
        "projects/issues.html",
        {
            **project_context(request, project, "issues"),
            "open_issues": open_issues,
            "resolved_issues": resolved,
        },
    )


@login_required
def project_milestones(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(pk)
    milestones = project.milestones.select_related("owner").all()
    return render(
        request,
        "projects/milestones.html",
        {
            **project_context(request, project, "milestones"),
            "milestones": milestones,
            "milestone_form": MilestoneForm(
                initial={"status": MilestoneStatus.UPCOMING}
            ),
        },
    )


@login_required
def project_notes(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(pk)
    notes = project.notes.select_related("author").all()
    decisions = project.decisions.select_related("decision_maker").all()
    return render(
        request,
        "projects/notes.html",
        {
            **project_context(request, project, "notes"),
            "notes": notes,
            "decisions": decisions,
        },
    )


@login_required
def project_activity(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(pk)
    activities = project.activities.select_related("actor").all()
    return render(
        request,
        "projects/activity.html",
        {
            **project_context(request, project, "activity"),
            "activities": activities,
        },
    )


# ---------------------------------------------------------- global pages ---


@login_required
def note_list(request: HttpRequest) -> HttpResponse:
    notes = Note.objects.select_related("project", "author").all()
    q = (request.GET.get("q") or "").strip()
    if q:
        notes = notes.filter(Q(title__icontains=q) | Q(content__icontains=q) | Q(tags__icontains=q))
    notes = notes[:50]
    return render(
        request,
        "projects/notes_global.html",
        {"notes": notes, "q": q},
    )


@login_required
def timeline_global(request: HttpRequest) -> HttpResponse:
    projects = list(_project_qs())
    rows = [
        {"project": p, "actual": actual_progress(p), "planned": planned_progress_on(p)}
        for p in projects
    ]
    return render(request, "projects/timeline_global.html", {"rows": rows})


@login_required
def reports(request: HttpRequest) -> HttpResponse:
    projects = list(_project_qs())
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
    return render(request, "projects/reports.html", {"rows": rows})


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
    project = _project_or_404(pk)
    if not _pm_check(request, project):
        return redirect("projects:project_detail", pk=pk)
    form = PhaseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        phase = form.save(commit=False)
        phase.project = project
        phase.save()
        record_activity(
            project, request.user, ActivityAction.PHASE_ADDED,
            f'Phase "{phase.name}" ditambahkan.',
        )
        messages.success(request, f"Phase {phase.name} ditambahkan.")
        return _tab_redirect(pk, "timeline")
    return render(
        request,
        "projects/phase_form.html",
        {"form": form, "project": project, "title": "New Phase"},
    )


# --- milestone ---


@login_required
def milestone_create(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(pk)
    if not _pm_check(request, project):
        return redirect("projects:project_detail", pk=pk)
    form = MilestoneForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        milestone = form.save(commit=False)
        milestone.project = project
        milestone.save()
        record_activity(
            project, request.user, ActivityAction.MILESTONE_ADDED,
            f'Milestone "{milestone.name}" ditambahkan ({milestone.date}).',
        )
        messages.success(request, f"Milestone {milestone.name} dibuat.")
        return _tab_redirect(pk, "milestones")
    return render(
        request,
        "projects/milestone_form.html",
        {"form": form, "project": project, "title": "New Milestone"},
    )


@login_required
def milestone_update(request: HttpRequest, pk: int, mid: int) -> HttpResponse:
    project = _project_or_404(pk)
    if not _pm_check(request, project):
        return redirect("projects:project_detail", pk=pk)
    milestone = get_object_or_404(Milestone, pk=mid, project=project)
    form = MilestoneForm(request.POST or None, instance=milestone)
    if request.method == "POST" and form.is_valid():
        form.save()
        if milestone.status == MilestoneStatus.COMPLETED:
            record_activity(
                project, request.user, ActivityAction.MILESTONE_COMPLETED,
                f'Milestone "{milestone.name}" completed.', milestone.name,
            )
        else:
            record_activity(
                project, request.user, ActivityAction.MILESTONE_UPDATED,
                f'Milestone "{milestone.name}" dirubah.', milestone.name,
            )
        messages.success(request, "Milestone disimpan.")
        return _tab_redirect(pk, "milestones")
    return render(
        request,
        "projects/milestone_form.html",
        {"form": form, "project": project, "title": milestone.name},
    )


@login_required
def milestone_delete(request: HttpRequest, pk: int, mid: int) -> HttpResponse:
    project = _project_or_404(pk)
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
    project = _project_or_404(pk)
    if not _pm_check(request, project):
        return _tab_redirect(pk, "progress")
    form = BaselinePointForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        point = form.save(commit=False)
        point.project = project
        point.save()
        record_activity(
            project, request.user, ActivityAction.BASELINE_UPDATED,
            f"Baseline point {point.date} → {point.planned_percent}% ditambahkan.",
        )
        messages.success(request, "Baseline point ditambahkan.")
    return _tab_redirect(pk, "progress")


@login_required
def baseline_delete(request: HttpRequest, pk: int, bpid: int) -> HttpResponse:
    project = _project_or_404(pk)
    point = get_object_or_404(ProgressBaselinePoint, pk=bpid, project=project)
    if request.method == "POST" and _pm_check(request, project):
        record_activity(
            project, request.user, ActivityAction.BASELINE_UPDATED,
            f"Baseline point {point.date} dihapus.",
        )
        point.delete()
    return _tab_redirect(pk, "progress")


@login_required
def snapshot_now(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(pk)
    if request.method == "POST" and _pm_check(request, project):
        record_snapshot(project)
        record_activity(
            project, request.user, ActivityAction.PROGRESS_UPDATED,
            "Snapshot progress hari ini disimpan.",
        )
        messages.success(request, "Snapshot progress disimpan.")
    return _tab_redirect(pk, "progress")


# --- notes & decisions ---


@login_required
def note_create(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(pk)
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
        "projects/note_form.html",
        {"form": form, "project": project, "title": "New Note"},
    )


@login_required
def note_edit(request: HttpRequest, pk: int, nid: int) -> HttpResponse:
    project = _project_or_404(pk)
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
        "projects/note_form.html",
        {"form": form, "project": project, "title": note.title},
    )


@login_required
def note_delete(request: HttpRequest, pk: int, nid: int) -> HttpResponse:
    project = _project_or_404(pk)
    note = get_object_or_404(Note, pk=nid, project=project)
    if request.method == "POST" and _pm_check(request, project):
        note.delete()
        messages.success(request, "Note dihapus.")
    return _tab_redirect(pk, "notes")


@login_required
def decision_create(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(pk)
    if not _pm_check(request, project):
        return _tab_redirect(pk, "notes")
    form = DecisionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        decision = form.save(commit=False)
        decision.project = project
        decision.save()
        record_activity(
            project, request.user, ActivityAction.DECISION_ADDED,
            f'Decision "{decision.title}" dicatat.',
        )
        messages.success(request, "Decision dicatat.")
        return _tab_redirect(pk, "notes")
    return render(
        request,
        "projects/decision_form.html",
        {"form": form, "project": project, "title": "Record Decision"},
    )


@login_required
def decision_delete(request: HttpRequest, pk: int, did: int) -> HttpResponse:
    project = _project_or_404(pk)
    decision = get_object_or_404(Decision, pk=did, project=project)
    if request.method == "POST" and _pm_check(request, project):
        decision.delete()
        messages.success(request, "Decision dihapus.")
    return _tab_redirect(pk, "notes")