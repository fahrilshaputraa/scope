from django.db.models import Q

from apps.identity.permissions import visible_projects
from apps.work.models import Issue, Task

from .models import Decision, Milestone, Note


def search_workspace(user, query, limit=6):
    """Search the entities a user can already see; archived rows stay hidden."""
    query = (query or "").strip()
    empty = {
        "projects": [],
        "tasks": [],
        "issues": [],
        "notes": [],
        "milestones": [],
        "decisions": [],
        "total": 0,
    }
    if not query:
        return empty

    scope = visible_projects(user)
    projects = list(
        scope.filter(
            Q(name__icontains=query) | Q(code__icontains=query) | Q(description__icontains=query)
        ).order_by("name")[:limit]
    )
    tasks = list(
        Task.objects.filter(project__in=scope)
        .filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(labels__icontains=query)
        )
        .select_related("project")
        .order_by("title")[:limit]
    )
    issues = list(
        Issue.objects.filter(project__in=scope)
        .filter(Q(title__icontains=query) | Q(description__icontains=query))
        .select_related("project")
        .order_by("-updated_at")[:limit]
    )
    notes = list(
        Note.objects.filter(project__in=scope)
        .filter(
            Q(title__icontains=query) | Q(content__icontains=query) | Q(tags__icontains=query)
        )
        .select_related("project", "author")
        .order_by("-updated_at")[:limit]
    )
    milestones = list(
        Milestone.objects.filter(project__in=scope)
        .filter(Q(name__icontains=query) | Q(description__icontains=query))
        .select_related("project")
        .order_by("date")[:limit]
    )
    decisions = list(
        Decision.objects.filter(project__in=scope)
        .filter(
            Q(title__icontains=query)
            | Q(decision__icontains=query)
            | Q(context__icontains=query)
            | Q(reason__icontains=query)
        )
        .select_related("project")
        .order_by("-created_at")[:limit]
    )
    return {
        "projects": projects,
        "tasks": tasks,
        "issues": issues,
        "notes": notes,
        "milestones": milestones,
        "decisions": decisions,
        "total": sum(
            len(group)
            for group in (projects, tasks, issues, notes, milestones, decisions)
        ),
    }
