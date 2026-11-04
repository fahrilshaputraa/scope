"""Dashboard per role (PRD §21). Saat ini: Project Owner."""

from django.shortcuts import render
from django.utils import timezone

from apps.work.models import OPEN_ISSUE_STATUSES, Issue

from .models import ASSESSED_LIFECYCLE, Milestone, MilestoneStatus, Project
from .services import actual_progress, planned_progress_on, variance

MAJOR_SEVERITIES = ("critical", "high")
LIST_LIMIT = 8


def owned_projects(user):
    return (
        Project.objects.filter(owner=user)
        .select_related("manager")
        .prefetch_related("baseline_points", "tasks__subtasks", "milestones")
        .order_by("name")
    )


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
        Risk.objects.filter(
            project_id__in=ids, status="open", severity__in=("critical", "high")
        )
        .select_related("project")
        .order_by("severity", "due_date")[:LIST_LIMIT]
    )
    upcoming = list(
        Milestone.objects.filter(project_id__in=ids, date__gte=today)
        .exclude(status=MilestoneStatus.COMPLETED)
        .select_related("project")
        .order_by("date")[:LIST_LIMIT]
    )
    return {
        "rows": rows,
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
