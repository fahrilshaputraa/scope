"""Dashboard per role (PRD §21): PM, Member, Owner, Management, Client."""

from django.shortcuts import render
from django.utils import timezone

from apps.work.models import OPEN_ISSUE_STATUSES, Issue

from .models import ASSESSED_LIFECYCLE, Milestone, MilestoneStatus, Project
from .services import actual_progress, planned_progress_on, variance, with_project_metrics

MAJOR_SEVERITIES = ("critical", "high")
LIST_LIMIT = 8


def owned_projects(user):
    return with_project_metrics(Project.objects.filter(owner=user)).order_by("name")


def owner_dashboard_context(user):
    projects = list(owned_projects(user))
    today = timezone.localdate()
    rows = []
    for project in projects:
        milestones = list(project.milestones.all())
        done = sum(1 for m in milestones if m.status == MilestoneStatus.COMPLETED)
        rows.append(
            {
                "project": project,
                "planned": planned_progress_on(project),
                "actual": actual_progress(project),
                "variance": variance(project),
                "milestones_done": done,
                "milestones_total": len(milestones),
                "next_milestone": project.next_milestone,
            }
        )
    health = {}
    for project in projects:
        if project.lifecycle_status in ASSESSED_LIFECYCLE:
            key = project.health_status
            health[key] = health.get(key, 0) + 1
    ids = [p.pk for p in projects]
    issues = list(
        Issue.objects.filter(
            project_id__in=ids, status__in=OPEN_ISSUE_STATUSES, severity__in=MAJOR_SEVERITIES
        )
        .select_related("project")
        .order_by("severity", "due_date")[:LIST_LIMIT]
    )
    from .models import Risk

    risks = list(
        Risk.objects.filter(project_id__in=ids, status="open", severity__in=("critical", "high"))
        .select_related("project")
        .order_by("-score", "review_date")[:LIST_LIMIT]
    )
    upcoming = list(
        Milestone.objects.filter(project_id__in=ids, date__gte=today)
        .exclude(status=MilestoneStatus.COMPLETED)
        .select_related("project")
        .order_by("date")[:LIST_LIMIT]
    )
    from apps.governance.models import ApprovalType
    from apps.governance.services import actionable_steps

    decisions = [
        step for step in actionable_steps(user) if step.request.approval_type != ApprovalType.TASK
    ][:LIST_LIMIT]
    return {
        "rows": rows,
        "decisions": decisions,
        "health": health,
        "late": health.get("delayed", 0) + health.get("critical", 0),
        "issues": issues,
        "risks": risks,
        "upcoming": upcoming,
        "today": today,
    }


def owner_dashboard(request):
    return render(
        request, "projects/portfolio/dashboard_owner.html", owner_dashboard_context(request.user)
    )


# ------------------------------------------------------------ shared pieces


def portfolio_health(projects) -> dict:
    """Distribusi health dan project yang butuh perhatian, dihitung dari data (R8.2)."""
    from .models import HealthStatus
    from .services import project_health

    distribution = {value: 0 for value in HealthStatus.values}
    unassessed = 0
    attention = []
    for project in projects:
        health = project_health(project)
        status = health["health_status"]
        if status is None:
            unassessed += 1
            continue
        distribution[status] += 1
        reasons = []
        if status != HealthStatus.ON_TRACK:
            reasons.append(HealthStatus(status).label)
        if health["critical_issues"]:
            reasons.append(f"{health['critical_issues']} masalah kritis")
        if health["risk_top_severity"] == "critical":
            reasons.append("risiko kritis")
        if reasons:
            attention.append({"project": project, "health": health, "reasons": reasons})
    assessed = sum(distribution.values())
    order = [HealthStatus.CRITICAL, HealthStatus.DELAYED, HealthStatus.AT_RISK]
    attention.sort(
        key=lambda row: (
            order.index(row["health"]["health_status"])
            if row["health"]["health_status"] in order
            else len(order),
            row["project"].target_end_date,
        )
    )
    return {
        "rows": [
            {
                "status": value,
                "label": label,
                "count": distribution[value],
                "share": round(distribution[value] / assessed * 100) if assessed else 0,
            }
            for value, label in HealthStatus.choices
        ],
        "assessed": assessed,
        "unassessed": unassessed,
        "attention": attention,
    }


def _recent_activity(project_ids, limit=LIST_LIMIT):
    from .models import ActivityEvent

    return list(
        ActivityEvent.objects.filter(project_id__in=project_ids)
        .select_related("project", "actor__pcc_profile")
        .order_by("-created_at")[:limit]
    )


# ----------------------------------------------------------------- PM / Admin


def pm_dashboard_extras(user, projects) -> dict:
    """Bagian PM dashboard yang butuh tindakan (PRD §21.1). Jumlah query tetap."""
    from apps.governance.models import ApprovalType
    from apps.governance.services import actionable_steps
    from apps.work.models import Task, TaskStatus

    today = timezone.localdate()
    ids = [p.pk for p in projects]
    tasks = Task.objects.filter(project_id__in=ids).select_related(
        "project", "assignee__pcc_profile"
    )
    overdue = tasks.filter(due_date__lt=today).exclude(status=TaskStatus.DONE)
    blocked = tasks.filter(status=TaskStatus.BLOCKED)
    in_review = tasks.filter(status=TaskStatus.REVIEW)
    steps = list(actionable_steps(user))
    return {
        "pm": {
            "overdue": list(overdue.order_by("due_date")[:LIST_LIMIT]),
            "overdue_count": overdue.count(),
            "blocked": list(blocked.order_by("due_date")[:LIST_LIMIT]),
            "blocked_count": blocked.count(),
            "in_review": list(in_review.order_by("updated_at")[:LIST_LIMIT]),
            "in_review_count": in_review.count(),
            "pending_approvals": [s for s in steps if s.request.approval_type != ApprovalType.TASK],
            "pending_reviews": [s for s in steps if s.request.approval_type == ApprovalType.TASK],
            "open_issues": Issue.objects.filter(
                project_id__in=ids, status__in=OPEN_ISSUE_STATUSES
            ).count(),
            "milestones": list(
                Milestone.objects.filter(project_id__in=ids, date__gte=today)
                .exclude(status=MilestoneStatus.COMPLETED)
                .select_related("project")
                .order_by("date")[:LIST_LIMIT]
            ),
            "activity": _recent_activity(ids),
        }
    }


# ---------------------------------------------------------------- Member


def member_dashboard(request):
    """Pekerjaan yang perlu dilaksanakan Member (PRD §21.2)."""
    from datetime import timedelta

    from django.db.models import Q

    from apps.identity.permissions import visible_projects
    from apps.work.models import Task, TaskStatus

    today = timezone.localdate()
    user = request.user
    mine = (
        Task.objects.filter(
            Q(assignee=user) | Q(collaborators=user), project__in=visible_projects(user)
        )
        .distinct()
        .select_related("project")
        .prefetch_related("subtasks")
    )
    open_tasks = mine.exclude(status=TaskStatus.DONE)
    # Setiap task tampil di satu bagian saja (U5): terhambat, lalu terlambat, lalu berjalan.
    late = Q(due_date__lt=today)
    sections = [
        ("blocked", "Terhambat", open_tasks.filter(status=TaskStatus.BLOCKED)),
        ("overdue", "Terlambat", open_tasks.filter(late).exclude(status=TaskStatus.BLOCKED)),
        (
            "in_progress",
            "Sedang dikerjakan",
            open_tasks.filter(status=TaskStatus.IN_PROGRESS).exclude(late),
        ),
        ("review", "Menunggu pemeriksaan", open_tasks.filter(status=TaskStatus.REVIEW)),
        (
            "upcoming",
            "Akan datang (14 hari)",
            open_tasks.filter(
                status__in=[TaskStatus.TODO, TaskStatus.BACKLOG],
                due_date__gte=today,
                due_date__lte=today + timedelta(days=14),
            ),
        ),
    ]
    ids = list(mine.values_list("project_id", flat=True).distinct())
    from apps.governance.models import ApprovalType
    from apps.governance.services import actionable_steps

    return render(
        request,
        "projects/portfolio/dashboard_member.html",
        {
            "assigned_count": open_tasks.count(),
            "sections": [
                {
                    "key": key,
                    "label": label,
                    "tasks": list(qs.order_by("due_date", "pk")[:LIST_LIMIT]),
                    "count": qs.count(),
                }
                for key, label, qs in sections
            ],
            "reviews": list(actionable_steps(user, [ApprovalType.TASK])),
            "activity": _recent_activity(ids),
            "today": today,
        },
    )


# ------------------------------------------------------------ Management


def management_dashboard(request):
    """Portfolio tanpa detail task teknis (PRD §21.4)."""
    from apps.identity.permissions import visible_projects

    from .models import Risk

    today = timezone.localdate()
    projects = list(with_project_metrics(visible_projects(request.user)).order_by("name"))
    health = portfolio_health(projects)
    rows = [
        {
            "project": p,
            "planned": planned_progress_on(p),
            "actual": actual_progress(p),
            "variance": variance(p),
        }
        for p in projects
    ]
    actuals = [row["actual"] for row in rows]
    planned = [row["planned"] for row in rows if row["planned"] is not None]
    ids = [p.pk for p in projects]
    return render(
        request,
        "projects/portfolio/dashboard_management.html",
        {
            "rows": rows,
            "health": health,
            "portfolio_actual": sum(actuals) / len(actuals) if actuals else 0,
            "portfolio_planned": sum(planned) / len(planned) if planned else None,
            "issues": list(
                Issue.objects.filter(
                    project_id__in=ids,
                    status__in=OPEN_ISSUE_STATUSES,
                    severity__in=MAJOR_SEVERITIES,
                )
                .select_related("project")
                .order_by("severity", "due_date")[:LIST_LIMIT]
            ),
            "risks": list(
                Risk.objects.filter(project_id__in=ids, status="open", severity="critical")
                .select_related("project")
                .order_by("-score")[:LIST_LIMIT]
            ),
            "milestones": list(
                Milestone.objects.filter(project_id__in=ids, date__gte=today)
                .exclude(status=MilestoneStatus.COMPLETED)
                .select_related("project")
                .order_by("date")[:LIST_LIMIT]
            ),
        },
    )


# ----------------------------------------------------------------- Client


def client_dashboard(request):
    """Transparansi project yang dibagikan (PRD §21.5)."""
    from apps.governance.changes import pending_acceptance
    from apps.governance.models import Deliverable, DeliverableStatus
    from apps.identity.permissions import visible_projects

    today = timezone.localdate()
    projects = list(with_project_metrics(visible_projects(request.user)).order_by("name"))
    ids = [p.pk for p in projects]
    deliverables = (
        Deliverable.objects.filter(project_id__in=ids)
        .select_related("project")
        .order_by("due_date")
    )
    return render(
        request,
        "projects/portfolio/dashboard_client.html",
        {
            "rows": [
                {"project": p, "planned": planned_progress_on(p), "actual": actual_progress(p)}
                for p in projects
            ],
            "milestones": list(
                Milestone.objects.filter(project_id__in=ids, date__gte=today)
                .exclude(status=MilestoneStatus.COMPLETED)
                .select_related("project")
                .order_by("date")[:LIST_LIMIT]
            ),
            "deliverables": list(deliverables[: LIST_LIMIT * 2]),
            "pending": pending_acceptance(request.user),
            "updates": list(
                Milestone.objects.filter(project_id__in=ids, status=MilestoneStatus.COMPLETED)
                .select_related("project")
                .order_by("-date")[:5]
            ),
            "accepted": list(
                deliverables.filter(status=DeliverableStatus.ACCEPTED).order_by("-updated_at")[:5]
            ),
        },
    )
