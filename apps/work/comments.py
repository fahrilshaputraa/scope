"""Helpers for comments on issues, notes, milestones, and projects (B4)."""

from django.http import Http404
from django.urls import reverse

from .models import Comment, CommentTarget

THREAD_PAGE_SIZE = 20


def _model_for(target_type):
    from apps.projects.models import Milestone, Note, Project

    from .models import Issue

    return {
        CommentTarget.ISSUE: Issue,
        CommentTarget.NOTE: Note,
        CommentTarget.MILESTONE: Milestone,
        CommentTarget.PROJECT: Project,
    }.get(target_type)


def resolve_target(target_type: str, target_id: int):
    """Return the concrete object for ``target_type``/``target_id`` or raise 404."""
    model = _model_for(target_type)
    if model is None:
        raise Http404("Jenis komentar tidak dikenal.")
    try:
        target_id = int(target_id)
    except (TypeError, ValueError):
        raise Http404("Target komentar tidak valid.") from None
    target = model.objects.filter(pk=target_id).first()
    if target is None:
        raise Http404("Target komentar tidak ditemukan.")
    return target


def target_project(target):
    from apps.projects.models import Project

    if isinstance(target, Project):
        return target
    project = getattr(target, "project", None)
    if project is None:
        raise Http404("Target komentar tidak memiliki project.")
    return project


def target_label(target_type: str) -> str:
    return {
        CommentTarget.ISSUE: "issue",
        CommentTarget.NOTE: "catatan",
        CommentTarget.MILESTONE: "milestone",
        CommentTarget.PROJECT: "project",
    }.get(target_type, "data")


def target_title(target_type: str, target) -> str:
    if target_type == CommentTarget.PROJECT:
        return target.name
    return getattr(target, "title", None) or getattr(target, "name", "")


def target_url(target_type: str, target) -> str:
    """Page URL with the comment thread anchor, used for notifications."""
    project = target_project(target)
    if target_type == CommentTarget.ISSUE:
        base = reverse("work:issue_update", args=[target.pk])
    elif target_type == CommentTarget.NOTE:
        base = reverse("projects:project_notes", args=[project.pk])
    elif target_type == CommentTarget.MILESTONE:
        base = reverse("projects:project_milestones", args=[project.pk])
    else:
        base = reverse("projects:project_detail", args=[project.pk])
    return f"{base}#comments-{target_type}-{target.pk}"


def thread(project, target_type: str, target_id: int, limit: int | None = THREAD_PAGE_SIZE):
    """Comments for one target, oldest first, optionally the latest ``limit``."""
    queryset = Comment.objects.filter(
        project=project, target_type=target_type, target_id=target_id
    ).select_related("author")
    if limit is None:
        return queryset
    ids = list(queryset.order_by("-created_at").values_list("pk", flat=True)[:limit])
    if not ids:
        return queryset.none()
    return queryset.filter(pk__in=ids).order_by("created_at")


def attach_threads(items, target_type: str, limit: int = THREAD_PAGE_SIZE):
    """Attach ``comment_thread`` and ``comment_count`` to a list of objects."""
    ids = [item.pk for item in items]
    counts: dict[int, int] = {}
    grouped: dict[int, list[Comment]] = {}
    if ids:
        queryset = (
            Comment.objects.filter(target_type=target_type, target_id__in=ids)
            .select_related("author")
            .order_by("created_at")
        )
        for comment in queryset:
            counts[comment.target_id] = counts.get(comment.target_id, 0) + 1
            grouped.setdefault(comment.target_id, []).append(comment)
    for item in items:
        rows = grouped.get(item.pk, [])
        item.comment_thread = rows[-limit:]
        item.comment_count = counts.get(item.pk, 0)
    return items


__all__ = [
    "THREAD_PAGE_SIZE",
    "attach_threads",
    "resolve_target",
    "target_label",
    "target_project",
    "target_title",
    "target_url",
    "thread",
]
