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

from apps.identity.models import Role
from apps.identity.permissions import (
    can_comment,
    can_control_projects,
    can_create_project,
    can_execute_task,
    can_manage_project,
    can_report_issue,
    can_view_internal,
    is_pm,
    require_internal,
    role_of,
    visible_projects,
)
from apps.identity.roles import has_perm
from apps.notifications.models import SubscriptionTarget
from apps.notifications.subscriptions import watch_state
from apps.work.comments import THREAD_PAGE_SIZE, attach_threads, thread
from apps.work.models import (
    TASK_STATUS_LABELS,
    CommentTarget,
    Issue,
    Task,
    TaskStatus,
)

from .forms import BaselinePointForm, DecisionForm, MilestoneForm, NoteForm, PhaseForm, ProjectForm
from .models import (
    CLOSED_LIFECYCLE,
    ActivityAction,
    Decision,
    HealthStatus,
    LifecycleStatus,
    Milestone,
    MilestoneStatus,
    Note,
    Phase,
    ProgressBaselinePoint,
    Revision,
)
from .pagination import paginate
from .project_templates import custom_field_rows
from .revisions import RestoreError, decorate_revisions, restore_revision
from .search import search_workspace
from .services import (
    actual_progress,
    planned_progress_on,
    project_health,
    record_activity,
    record_snapshot,
    variance,
    variance_level,
    with_project_metrics,
)

# Arsitektur informasi project (U6): tujuh tab; setiap tab punya satu atau lebih
# bagian yang tampil sebagai pilihan tampilan (segmented control). URL lama tetap
# berlaku: setiap bagian memakai URL-nya sendiri.
# group -> (label tab, [(bagian, label tampilan)])
PROJECT_GROUPS = [
    ("overview", "Ringkasan", [("overview", "Ringkasan")]),
    (
        "work",
        "Pekerjaan",
        [
            ("tasks_list", "Daftar"),
            ("tasks", "Board"),
            ("timeline", "Jadwal"),
            ("structure", "Struktur"),
        ],
    ),
    ("progress", "Progress", [("progress", "Progress")]),
    ("issues", "Masalah & risiko", [("issues", "Masalah & risiko")]),
    (
        "milestones",
        "Milestone & deliverable",
        [("milestones", "Milestone"), ("deliverables", "Deliverable")],
    ),
    ("notes", "Catatan & keputusan", [("notes", "Catatan & keputusan")]),
    (
        "activity",
        "Aktivitas",
        [
            ("activity", "Log aktivitas"),
            ("history", "Riwayat perubahan"),
            ("approvals", "Persetujuan & perubahan"),
            ("control", "Kontrol"),
        ],
    ),
]
# Bagian di luar tab: dibuka dari menu Lainnya → Pengaturan project.
SETTINGS_SECTIONS = [
    ("settings", "Umum"),
    ("members", "Anggota"),
    ("share", "Tautan publik"),
]
# Kompatibilitas: daftar datar (key, label) dari semua bagian bertab.
PROJECT_TABS = [section for _, _, sections in PROJECT_GROUPS for section in sections]
SECTION_URLS = {
    "overview": ("projects:project_detail", ""),
    "tasks_list": ("projects:project_tasks", "?view=list"),
    "tasks": ("projects:project_tasks", ""),
    "timeline": ("projects:project_timeline", ""),
    "structure": ("projects:project_structure", ""),
    "progress": ("projects:project_progress", ""),
    "issues": ("projects:project_issues", ""),
    "milestones": ("projects:project_milestones", ""),
    "deliverables": ("governance:project_deliverables", ""),
    "notes": ("projects:project_notes", ""),
    "activity": ("projects:project_activity", ""),
    "history": ("projects:project_history", ""),
    "approvals": ("governance:project_approvals", ""),
    "control": ("projects:project_control", ""),
    "settings": ("projects:project_settings", ""),
    "members": ("projects:project_members", ""),
    "share": ("projects:project_share", ""),
}

STATUS_CHOICES = LifecycleStatus.choices
HEALTH_CHOICES = HealthStatus.choices


def _project_qs(user, *, include_archived=False):
    return with_project_metrics(visible_projects(user, include_archived=include_archived))


def _task_counts(project) -> dict:
    """Jumlah task per kelompok dari task yang sudah di-prefetch (tanpa query)."""
    tasks = list(project.tasks.all())
    return {
        "total": len(tasks),
        "blocked": sum(1 for t in tasks if t.status == TaskStatus.BLOCKED),
        "done": sum(1 for t in tasks if t.status == TaskStatus.DONE),
    }


INTERNAL_TABS = {"issues", "notes", "activity", "history", "approvals"}
CONTROL_TABS = {"control"}


def can_submit_change(user, project):
    from apps.governance.changes import can_submit_change as allowed

    return allowed(user, project)


def _section_url(key, project):
    name, suffix = SECTION_URLS[key]
    return reverse(name, args=[project.pk]) + suffix


# Aksi utama header per bagian. Bagian yang punya tombol utama di toolbar-nya
# sendiri (board, masalah, milestone, deliverable, catatan, persetujuan, jadwal)
# tidak mendapat tombol kedua di header (U3: satu aksi utama per layar).
HEADER_PRIMARY_SECTIONS = {"overview", "progress", "tasks_list", "activity", "history", "control"}


def project_context(request, project, active_tab):
    internal = can_view_internal(request.user)
    control = can_control_projects(request.user)

    def allowed(key):
        return (internal or key not in INTERNAL_TABS) and (key not in CONTROL_TABS or control)

    tabs, groups, active_group, subtabs = [], [], None, []
    for group_key, group_label, sections in PROJECT_GROUPS:
        visible = [(key, label) for key, label in sections if allowed(key)]
        if not visible:
            continue
        is_active = any(key == active_tab for key, _ in sections) or (
            active_tab == "tasks" and group_key == "work"
        )
        tabs.append((group_key, group_label))
        groups.append(
            {
                "key": group_key,
                "label": group_label,
                "url": _section_url(visible[0][0], project),
                "active": is_active,
            }
        )
        if is_active:
            active_group = group_key
            if len(visible) > 1:
                subtabs = [
                    {"key": key, "label": label, "url": _section_url(key, project)}
                    for key, label in visible
                ]
    manage = can_manage_project(request.user, project)
    if active_tab in {key for key, _ in SETTINGS_SECTIONS}:
        active_group = "settings"
        subtabs = [
            {"key": key, "label": label, "url": _section_url(key, project)}
            for key, label in SETTINGS_SECTIONS
        ]
    return {
        "project": project,
        # Tab utama (maksimal tujuh) dan semua bagian yang boleh dibuka.
        "tabs": tabs,
        "tab_groups": groups,
        "project_sections": [key for key, _ in PROJECT_TABS if allowed(key)],
        "subtabs": subtabs,
        "active_group": active_group,
        "header_primary": manage and active_tab in HEADER_PRIMARY_SECTIONS,
        "can_view_internal": internal,
        "active_tab": active_tab,
        "can_manage": manage,
        "can_report": can_report_issue(request.user),
        "can_comment": can_comment(request.user),
        "can_manage_templates": has_perm(request.user, "template.manage"),
        "can_submit_change": can_submit_change(request.user, project),
        "custom_rows": custom_field_rows(project),
        **watch_state(request.user, SubscriptionTarget.PROJECT, project.pk),
    }


def _project_or_404(request, pk, *, rich=False):
    return get_object_or_404(_project_qs(request.user), pk=pk)


# ============================================================== DASHBOARD ===


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    from . import dashboards

    role = role_of(request.user)
    if role == Role.OWNER:
        return dashboards.owner_dashboard(request)
    if role == Role.MEMBER:
        return dashboards.member_dashboard(request)
    if role == Role.MANAGEMENT:
        return dashboards.management_dashboard(request)
    if role == Role.CLIENT:
        return dashboards.client_dashboard(request)
    projects = list(_project_qs(request.user))
    healths = {p.pk: project_health(p) for p in projects}  # sekali per project
    by_health = Counter(healths[p.pk]["health_status"] for p in projects)
    rows = [
        {
            "project": p,
            "planned": healths[p.pk]["planned"],
            "actual": healths[p.pk]["progress"],
            "variance": healths[p.pk]["variance"],
            "level": healths[p.pk]["variance_level"],
            "next_milestone": p.next_milestone,
        }
        for p in projects
    ]

    attention = []
    for row in rows:
        project = row["project"]
        health = healths[project.pk]
        blocked = _task_counts(project)["blocked"]
        milestone = row["next_milestone"]
        reasons = []
        if project.lifecycle_status in CLOSED_LIFECYCLE:
            continue
        if health["health_status"] in (
            HealthStatus.AT_RISK,
            HealthStatus.DELAYED,
            HealthStatus.CRITICAL,
        ):
            reasons.append(
                "Progress tertinggal" if not project.is_overdue else "Target project terlewat"
            )
            reasons.append(HealthStatus(health["health_status"]).label)
        if health["critical_issues"]:
            reasons.append(f"{health['critical_issues']} masalah kritis")
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
                    + {HealthStatus.DELAYED: 5, HealthStatus.CRITICAL: 8}.get(
                        health["health_status"], 0
                    ),
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
            **dashboards.pm_dashboard_extras(request.user, projects),
            "today": timezone.localdate(),
            "counts": {
                "total": len(projects),
                "on_track": by_health.get(HealthStatus.ON_TRACK, 0),
                "at_risk": by_health.get(HealthStatus.AT_RISK, 0),
                "delayed": by_health.get(HealthStatus.DELAYED, 0)
                + by_health.get(HealthStatus.CRITICAL, 0),
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
    health = request.GET.get("health") or ""
    pm = request.GET.get("pm") or ""
    team = request.GET.get("team") or ""

    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(code__icontains=search))
    if status in LifecycleStatus.values:
        qs = qs.filter(lifecycle_status=status)
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
    if health in HealthStatus.values:
        projects = [p for p in projects if p.health_status == health]
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
    phase_names = sorted(
        {
            p.effective_current_phase.name
            for p in visible_projects(request.user)
            .select_related("current_phase")
            .prefetch_related("phases")
            if p.effective_current_phase
        }
    )
    pms = list(
        User.objects.filter(Q(managed_projects__in=visible_projects(request.user)))
        .select_related("pcc_profile")
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
                "health": health,
                "pm": pm,
                "team": team,
                "from": date_from,
                "to": date_to,
                "phase": phase,
                "progress_min": progress_min,
                "progress_max": progress_max,
            },
            "status_choices": STATUS_CHOICES,
            "health_choices": HEALTH_CHOICES,
            "teams": teams,
            "phases": phase_names,
            "pms": pms,
            "can_create": can_create_project(request.user),
        },
    )


# ========================================================== PROJECT DETAIL ===


@login_required
def project_detail(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_or_404(request, pk)
    health = project_health(project)
    today = timezone.localdate()
    # Satu query untuk semua task yang relevan; dipilah di Python.
    relevant = list(
        Task.objects.filter(project=project)
        .filter(
            Q(status__in=[TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED])
            | (Q(due_date__lt=today) & ~Q(status=TaskStatus.DONE))
        )
        .select_related("assignee")
        .prefetch_related("collaborators", "subtasks")
    )
    by_due = lambda task: (task.due_date is None, task.due_date, task.pk)  # noqa: E731
    current_work = sorted((t for t in relevant if t.status == TaskStatus.IN_PROGRESS), key=by_due)
    blocked_work = [t for t in relevant if t.status == TaskStatus.BLOCKED]
    overdue_work = sorted(
        (
            t
            for t in relevant
            if t.due_date and t.due_date < today and t.status != TaskStatus.BLOCKED
        ),
        key=by_due,
    )
    open_issues = (project.open_issues_cache or [])[:6]
    activities = project.activities.select_related("actor__pcc_profile")[:8]
    baseline = list(project.baseline_points.all())
    snapshots = list(project.snapshots.all())
    comment_thread = thread(project, CommentTarget.PROJECT, project.pk, limit=None)
    context = project_context(request, project, "overview")
    readiness = _readiness(request, project, context["can_manage"])
    actions = _next_actions(
        request, project, blocked_work, overdue_work, open_issues, context["can_view_internal"]
    )

    return render(
        request,
        "projects/project/overview.html",
        {
            **context,
            "readiness": readiness,
            "today": today,
            "next_actions": actions[:5],
            "next_actions_more": max(len(actions) - 5, 0),
            "health": health,
            "blocked_work": blocked_work,
            "overdue_work": overdue_work[:3],
            "overdue_more": max(len(overdue_work) - 3, 0),
            "current_work": current_work,
            "open_issues": open_issues,
            "activities": activities,
            "chart": progress_chart_data(baseline, snapshots, health["progress"]),
            "chart_has_plan": bool(baseline),
            "comments": paginate(request, comment_thread, THREAD_PAGE_SIZE),
            "comment_count": comment_thread.count(),
        },
    )


READY_LIFECYCLE = (LifecycleStatus.DRAFT, LifecycleStatus.PLANNING)


def _readiness(request, project, can_manage):
    """Checklist 'Siap berjalan' (syarat lifecycle PRD §7.3) dengan aksi per syarat.

    None bila project sudah melewati perencanaan.
    """
    if project.lifecycle_status not in READY_LIFECYCLE:
        return None
    from apps.governance.models import ApprovalType
    from apps.governance.services import is_enabled, plan_approved

    from .models import BaselineStatus

    pk = project.pk
    has_tasks = project.tasks.exists()
    has_baseline = project.baseline_points.exists()
    pending_baseline = project.baselines.filter(status=BaselineStatus.PENDING).exists()
    edit = {"label": "Lengkapi info project", "url": reverse("projects:project_edit", args=[pk])}
    steps = [
        {
            "key": "owner",
            "label": "Project Owner ditentukan",
            "done": bool(project.owner_id),
            "action": {**edit, "drawer": True},
        },
        {
            "key": "manager",
            "label": "Project Manager ditentukan",
            "done": bool(project.manager_id),
            "action": {**edit, "drawer": True},
        },
        {
            "key": "tasks",
            "label": "Jadwal berisi task",
            "done": has_tasks,
            "action": {
                "label": "Susun jadwal",
                "url": reverse("projects:project_timeline", args=[pk]),
            },
        },
        {
            "key": "baseline",
            "label": "Baseline dibuat dari jadwal",
            "done": has_baseline,
            "hint": (
                "Baseline menunggu persetujuan."
                if pending_baseline
                else ("" if has_tasks else "Susun jadwal dulu, lalu buat baseline satu klik.")
            ),
            "action": (
                {
                    "label": "Buat baseline dari jadwal",
                    "url": reverse("projects:capture_baseline", args=[pk]),
                    "post": True,
                }
                if has_tasks and not pending_baseline
                else None
            ),
        },
    ]
    if is_enabled(project, ApprovalType.PLAN):
        steps.append(
            {
                "key": "plan",
                "label": "Rencana project disetujui",
                "done": plan_approved(project),
                "action": {
                    "label": "Ajukan rencana",
                    "url": reverse("governance:request_plan", args=[pk]),
                    "post": True,
                }
                if has_tasks
                else None,
            }
        )
    if not can_manage:
        for step in steps:
            step["action"] = None
    done = sum(step["done"] for step in steps)
    return {
        "steps": steps,
        "done": done,
        "total": len(steps),
        "ready": done == len(steps),
        "can_start": can_manage and done == len(steps),
    }


def _next_actions(request, project, blocked, overdue, issues, internal):
    """3–5 hal yang perlu dilakukan sekarang (U2), terpenting lebih dulu."""
    from apps.governance.models import ApprovalRequest, ApprovalStatus

    items = []
    for task in blocked:
        items.append(
            {
                "tone": "danger",
                "badge": "Terhambat",
                "title": task.title,
                "url": reverse("work:task_detail", args=[task.pk]),
                "meta": task.blocked_reason or "Alasan belum dicatat.",
                "who": task.assignee_names,
                "cta": "Tindak lanjuti",
            }
        )
    if internal:
        for issue in issues:
            if issue.severity not in ("critical", "high"):
                continue
            items.append(
                {
                    "tone": "issue",
                    "severity": issue.severity,
                    "badge": "Kritis" if issue.severity == "critical" else "Tinggi",
                    "title": issue.title,
                    "url": reverse("work:issue_update", args=[issue.pk]),
                    "meta": "Masalah terbuka"
                    + (f" · target {issue.due_date:%d %b}" if issue.due_date else ""),
                    "who": person_label(issue.owner) or "Belum ada penanggung jawab",
                    "cta": "Perbarui",
                    "drawer": True,
                }
            )
    for task in overdue:
        items.append(
            {
                "tone": "warning",
                "badge": "Terlambat",
                "title": task.title,
                "url": reverse("work:task_detail", args=[task.pk]),
                "meta": f"Target {task.due_date:%d %b %Y} · progress {task.display_progress:.0f}%",
                "who": task.assignee_names,
                "cta": "Buka task",
            }
        )
    if internal:
        pending = (
            ApprovalRequest.objects.filter(project=project, status=ApprovalStatus.PENDING)
            .order_by("created_at")
            .first()
        )
        if pending:
            items.append(
                {
                    "tone": "info",
                    "badge": "Persetujuan",
                    "title": pending.get_approval_type_display(),
                    "url": reverse("governance:approval_detail", args=[pending.pk]),
                    "meta": "Menunggu keputusan",
                    "who": "",
                    "cta": "Tinjau",
                }
            )
    return items


def person_label(user):
    from .templatetags.pcc_tags import person_name

    return person_name(user) if user else ""


@login_required
@require_POST
def project_start(request: HttpRequest, pk: int) -> HttpResponse:
    """Satu klik 'Mulai project' setelah checklist Siap berjalan terpenuhi."""
    from django.core.exceptions import ValidationError

    project = _project_or_404(request, pk)
    if not _pm_check(request, project):
        return redirect("projects:project_detail", pk=pk)
    project.lifecycle_status = LifecycleStatus.IN_PROGRESS
    try:
        project.full_clean()
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("projects:project_detail", pk=pk)
    project.save()
    record_activity(
        project,
        request.user,
        ActivityAction.PROJECT_UPDATED,
        f'Project "{project.name}" mulai berjalan.',
        target=project,
    )
    messages.success(request, "Project berjalan. Progress dan health kini dipantau harian.")
    return redirect("projects:project_detail", pk=pk)


@login_required
def project_settings(request: HttpRequest, pk: int) -> HttpResponse:
    """Pengaturan project dalam satu halaman (dipindah dari tab dan menu Lainnya)."""
    project = _project_or_404(request, pk)
    if not can_manage_project(request.user, project):
        raise PermissionDenied
    from apps.governance.models import ApprovalPolicy

    return render(
        request,
        "projects/project/settings.html",
        {
            **project_context(request, project, "settings"),
            "approval_count": ApprovalPolicy.objects.filter(project=project, enabled=True).count(),
            "column_count": project.board_columns.count(),
            "custom_field_count": len(project.custom_fields or []),
            "member_count": project.members.count(),
            "can_configure_approvals": has_perm(request.user, "approval.configure"),
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
        if day < points[0] or day > points[-1]:
            return None  # rencana tidak diperpanjang di luar tanggal baseline
        if day == points[-1]:
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
        "planned_marks": [d in planned for d in labels],
        "actual": [actual.get(d) for d in labels],
        "today_index": labels.index(today),
    }


# ------------------------------------------------------------- create/edit ---


@login_required
def project_create(request: HttpRequest) -> HttpResponse:
    """Wizard 'Buat project': data inti → sumber rencana → tinjau (satu POST)."""
    if not can_create_project(request.user):
        return redirect("projects:project_list")
    from .forms import ProjectCreateForm
    from .project_templates import template_spans

    form = ProjectCreateForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        from django.core.exceptions import ValidationError
        from django.db import transaction

        from .models import WeightMode
        from .project_templates import apply_structure, apply_template

        source = form.cleaned_data["source"]
        try:
            with transaction.atomic():
                project = form.save(commit=False)
                # Project baru memakai bobot otomatis sama rata (BR-WGT-001).
                project.weight_mode = WeightMode.AUTO
                project.save()
                form.save_m2m()
                record_activity(
                    project,
                    request.user,
                    ActivityAction.PROJECT_CREATED,
                    f'Project "{project.name}" created ({project.code}).',
                )
                template = form.cleaned_data.get("template")
                counts = None
                if source == "template" and template is not None:
                    counts = apply_template(template, project, request.user)
                elif source == "paste":
                    counts = apply_structure(form.cleaned_data["plan_structure"], project)
                    record_activity(
                        project,
                        request.user,
                        ActivityAction.TASK_CREATED,
                        f"{counts['tasks']} task dibuat dari daftar yang ditempel.",
                    )
                if counts:
                    _extend_end_to_plan(project)
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            messages.success(request, f"Project {project.code} dibuat.")
            if counts:
                messages.info(
                    request,
                    f"Jadwal berisi {counts['phases']} phase, {counts['tasks']} task, "
                    f"{counts['milestones']} milestone. Tetapkan pelaksana, lalu buat baseline.",
                )
            if source == "ai":
                return redirect("projects:plan_import", pk=project.pk)
            if source == "blank":
                return redirect("projects:project_detail", pk=project.pk)
            return redirect("projects:project_timeline", pk=project.pk)
    return render(
        request,
        "projects/forms/project_wizard.html",
        {
            "form": form,
            "project": None,
            "title": "Buat project",
            "template_spans": template_spans(),
        },
    )


def _extend_end_to_plan(project):
    """Tanggal akhir otomatis: mundurkan target bila jadwal yang dibuat lebih panjang."""
    from django.db.models import Max

    last = project.tasks.aggregate(last=Max("due_date"))["last"]
    if last and last > project.target_end_date:
        project.target_end_date = last
        project.save(update_fields=["target_end_date", "updated_at"])


@login_required
def project_apply_template(request: HttpRequest, pk: int) -> HttpResponse:
    """'Mulai dari template' untuk project yang jadwalnya masih kosong."""
    from .forms import ApplyTemplateForm
    from .project_templates import apply_template

    project = _project_or_404(request, pk)
    if not _pm_check(request, project):
        return redirect("projects:project_detail", pk=pk)
    if project.tasks.exists():
        messages.error(request, "Template hanya bisa dipakai saat jadwal project masih kosong.")
        return _tab_redirect(pk, "timeline")
    form = ApplyTemplateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        counts = apply_template(form.cleaned_data["template"], project, request.user)
        _extend_end_to_plan(project)
        messages.success(
            request,
            f"Template dipakai: {counts['phases']} phase, {counts['tasks']} task, "
            f"{counts['milestones']} milestone.",
        )
        return _tab_redirect(pk, "timeline")
    return render(
        request,
        "projects/forms/simple_form.html",
        {
            "form": form,
            "project": project,
            "title": "Mulai dari template",
            "subtitle": "Isi jadwal kosong dengan struktur template.",
            "submit_label": "Pakai template",
            "back_url": reverse("projects:project_timeline", args=[pk]),
        },
    )


@login_required
def project_paste_tasks(request: HttpRequest, pk: int) -> HttpResponse:
    """'Tempel daftar task' berbasis form (cadangan dialog Gantt, juga untuk mobile)."""
    from .forms import PasteTasksForm
    from .project_templates import apply_structure

    project = _project_or_404(request, pk)
    if not _pm_check(request, project):
        return redirect("projects:project_detail", pk=pk)
    from django.db.models import Max

    last = project.tasks.aggregate(last=Max("due_date"))["last"]
    start = last + PT if last else project.start_date
    form = PasteTasksForm(request.POST or None, initial={"start_date": start})
    if request.method == "POST" and form.is_valid():
        from django.core.exceptions import ValidationError
        from django.db import transaction

        anchor = form.cleaned_data["start_date"]
        try:
            with transaction.atomic():
                original = project.start_date
                project.start_date = anchor  # offset dihitung dari tanggal mulai ini
                counts = apply_structure(form.structure, project)
                project.start_date = original
                _extend_end_to_plan(project)
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            record_activity(
                project,
                request.user,
                ActivityAction.TASK_CREATED,
                f"{counts['tasks']} task dibuat dari daftar yang ditempel.",
            )
            messages.success(request, f"{counts['tasks']} task ditambahkan ke jadwal.")
            return _tab_redirect(pk, "timeline")
    return render(
        request,
        "projects/forms/simple_form.html",
        {
            "form": form,
            "project": project,
            "title": "Tempel daftar task",
            "subtitle": "Buat banyak task sekaligus; jadwal disusun berurutan.",
            "submit_label": "Buat task",
            "back_url": reverse("projects:project_timeline", args=[pk]),
        },
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
            target=project,
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
    from apps.work.gantt import project_payload

    project = _project_or_404(request, pk)
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
            "gantt": project_payload(project, request.user),
            "has_tasks": project.tasks.exists(),
            "needs_baseline": not project.baseline_points.exists()
            and not project.baselines.filter(status="pending").exists(),
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
        project.tasks.select_related("assignee__pcc_profile", "phase", "parent_task")
        .prefetch_related(
            "issues",
            "collaborators__pcc_profile",
            "subtasks__assignee__pcc_profile",
            "subtasks__collaborators__pcc_profile",
        )
        .order_by("order", "due_date")
    )
    if request.GET.get("view") == "list":
        return _project_task_list(request, project, tasks)
    for task in tasks:
        task.can_edit = can_execute_task(request.user, task)
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


TASK_LIST_FILTERS = [
    ("all", "Semua"),
    ("open", "Belum selesai"),
    ("overdue", "Terlambat"),
    ("blocked", "Terhambat"),
    ("done", "Selesai"),
]


def _project_task_list(request, project, tasks):
    """Tampilan Daftar: satu baris per task utama, ringkas (U4)."""
    today = timezone.localdate()
    roots = [t for t in tasks if not t.parent_task_id]
    roots.sort(
        key=lambda t: (
            t.phase.sequence if t.phase_id else 10**6,
            t.start_date is None,
            t.start_date or today,
            t.order,
            t.pk,
        )
    )
    for task in roots:
        task.can_edit = can_execute_task(request.user, task)
        task.is_late = bool(
            task.due_date and task.due_date < today and task.status != TaskStatus.DONE
        )
    counts = {
        "all": len(roots),
        "open": sum(t.status != TaskStatus.DONE for t in roots),
        "overdue": sum(t.is_late for t in roots),
        "blocked": sum(t.status == TaskStatus.BLOCKED for t in roots),
        "done": sum(t.status == TaskStatus.DONE for t in roots),
    }
    selected = request.GET.get("filter", "all")
    if selected not in counts:
        selected = "all"
    keep = {
        "all": lambda t: True,
        "open": lambda t: t.status != TaskStatus.DONE,
        "overdue": lambda t: t.is_late,
        "blocked": lambda t: t.status == TaskStatus.BLOCKED,
        "done": lambda t: t.status == TaskStatus.DONE,
    }[selected]
    rows = [t for t in roots if keep(t)]
    return render(
        request,
        "projects/project/task_list.html",
        {
            **project_context(request, project, "tasks_list"),
            "task_rows": rows,
            "filters": [(key, label, counts[key]) for key, label in TASK_LIST_FILTERS],
            "selected_filter": selected,
            "status_labels": TASK_STATUS_LABELS,
        },
    )


@login_required
def project_issues(request: HttpRequest, pk: int) -> HttpResponse:
    require_internal(request.user)
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
    milestones = attach_threads(
        list(project.milestones.select_related("owner").all()), CommentTarget.MILESTONE
    )
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
    require_internal(request.user)
    project = _project_or_404(request, pk)
    notes = attach_threads(list(project.notes.select_related("author").all()), CommentTarget.NOTE)
    decisions = project.decisions.select_related("decision_maker", "related_issue").all()
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
    require_internal(request.user)
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


@login_required
def project_history(request: HttpRequest, pk: int) -> HttpResponse:
    require_internal(request.user)
    project = _project_or_404(request, pk)
    revisions = project.revisions.select_related("actor").all()
    page_obj = paginate(request, revisions, 25)
    return render(
        request,
        "projects/project/history.html",
        {
            **project_context(request, project, "history"),
            "revisions": decorate_revisions(page_obj),
            "page_obj": page_obj,
        },
    )


@login_required
@require_POST
def project_history_restore(request: HttpRequest, pk: int, revision_id: int) -> HttpResponse:
    require_internal(request.user)
    project = _project_or_404(request, pk)
    if not can_manage_project(request.user, project):
        raise PermissionDenied
    revision = get_object_or_404(Revision, pk=revision_id, project=project)
    try:
        restore_revision(revision, request.user)
    except RestoreError as exc:
        messages.error(request, str(exc))
    else:
        record_activity(
            project,
            request.user,
            ActivityAction.HISTORY_RESTORED,
            f"Perubahan {revision.object_repr} dipulihkan dari riwayat.",
        )
        messages.success(request, "Perubahan berhasil dipulihkan.")
    return redirect("projects:project_history", pk=pk)


# ---------------------------------------------------------- global pages ---


@login_required
def note_list(request: HttpRequest) -> HttpResponse:
    require_internal(request.user)
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
    from apps.work.gantt import portfolio_payload

    projects = list(_project_qs(request.user))
    return render(
        request,
        "projects/portfolio/timeline.html",
        {"gantt": portfolio_payload(projects), "project_count": len(projects)},
    )


@login_required
def reports(request: HttpRequest) -> HttpResponse:
    from apps.work.gantt import portfolio_payload

    projects = list(_project_qs(request.user))
    rows = []
    for p in projects:
        health = project_health(p)
        rows.append(
            {
                "project": p,
                "health": health,
                "planned": health["planned"],
                "actual": health["progress"],
                "variance": health["variance"],
                "level": health["variance_level"],
                "next_milestone": p.next_milestone,
            }
        )
    start = min((p.start_date for p in projects), default=timezone.localdate())
    end = max((p.target_end_date for p in projects), default=start)
    for row in rows:
        p = row["project"]
        counts = _task_counts(p)
        row["blocked"], row["done"], row["task_count"] = (
            counts["blocked"],
            counts["done"],
            counts["total"],
        )
    totals = {
        "projects": len(rows),
        "completed": sum(
            row["project"].lifecycle_status == LifecycleStatus.COMPLETED for row in rows
        ),
        "attention": sum(
            row["project"].health_status
            in (HealthStatus.AT_RISK, HealthStatus.DELAYED, HealthStatus.CRITICAL)
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
            "gantt": portfolio_payload(projects),
            "is_management": role_of(request.user) == Role.MANAGEMENT,
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
    "history": "project_history",
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
                target=milestone,
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
    require_internal(request.user)
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
    require_internal(request.user)
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
    require_internal(request.user)
    project = _project_or_404(request, pk)
    if not _pm_check(request, project):
        return _tab_redirect(pk, "notes")
    form = DecisionForm(request.POST or None, project=project)
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
    if not (can_manage_project(request.user, project) and has_perm(request.user, "risk.manage")):
        raise PermissionDenied
    form = RiskForm(request.POST or None, instance=risk, project=project)
    form.instance.project = project
    if request.method == "POST" and form.is_valid():
        risk = form.save()
        record_activity(
            project,
            request.user,
            ActivityAction.RISK_UPDATED,
            f'Risiko "{risk.title}" disimpan (skor {risk.score}, {risk.get_severity_display()}).',
        )
        messages.success(request, "Risiko disimpan.")
        return redirect("projects:project_issues", pk=pk)
    return render(
        request,
        "projects/forms/risk_form.html",
        {"project": project, "form": form, "title": "Risiko project"},
    )


@login_required
@require_POST
def risk_convert(request, pk, rid):
    """Risiko yang benar-benar terjadi dikonversi menjadi issue (PRD §16.2)."""
    from .models import Risk

    project = _project_or_404(request, pk)
    risk = get_object_or_404(Risk, pk=rid, project=project)
    if not (can_manage_project(request.user, project) and has_perm(request.user, "risk.manage")):
        raise PermissionDenied
    if risk.issue_id or risk.status == "converted":
        messages.info(request, "Risiko ini sudah menjadi issue.")
        return redirect("projects:project_issues", pk=pk)
    issue = Issue.objects.create(
        project=project,
        title=risk.title,
        description=risk.description or risk.mitigation,
        severity=risk.severity,
        priority=risk.severity,
        owner=risk.owner,
    )
    risk.status, risk.issue = "converted", issue
    risk.save(update_fields=["status", "issue"])
    record_activity(
        project,
        request.user,
        ActivityAction.RISK_CONVERTED,
        f'Risiko "{risk.title}" terjadi dan dikonversi menjadi issue ISS-{issue.pk}.',
        target=issue,
    )
    messages.success(request, "Risiko dikonversi menjadi issue.")
    return redirect("work:issue_update", pk=issue.pk)


@login_required
def capture_timeline_baseline(request, pk):
    from .services import capture_baseline

    project = _project_or_404(request, pk)
    if request.method != "POST":
        return HttpResponse(status=405)
    if not _pm_check(request, project):
        return _tab_redirect(pk, "timeline")
    from django.core.exceptions import ValidationError
    from django.utils.http import url_has_allowed_host_and_scheme

    target = request.POST.get("next") or ""
    back = (
        redirect(target)
        if url_has_allowed_host_and_scheme(
            target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        )
        else _tab_redirect(pk, "timeline")
    )
    try:
        baseline = capture_baseline(project, request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return back
    from .models import BaselineStatus

    if baseline.status == BaselineStatus.PENDING:
        messages.success(
            request, f"Baseline v{baseline.version} diajukan. Berlaku setelah disetujui."
        )
    else:
        messages.success(request, f"Baseline v{baseline.version} disimpan dan berlaku.")
    return back


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
