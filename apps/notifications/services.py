"""Central notification fan-out: recipient resolver, preferences, and dedupe."""

from django.utils import timezone

from .models import (
    Notification,
    NotificationPreference,
    NotificationTarget,
    SubscriptionTarget,
)
from .subscriptions import watcher_users


def get_preference(user) -> NotificationPreference:
    preference, _ = NotificationPreference.objects.get_or_create(user=user)
    return preference


def _target_project(target):
    from apps.projects.models import Project

    if target is None:
        return None
    if isinstance(target, Project):
        return target
    return getattr(target, "project", None)


def _target_ref(target):
    from apps.projects.models import Milestone, Project
    from apps.work.models import Issue, Task

    if isinstance(target, Task):
        return NotificationTarget.TASK, target.pk
    if isinstance(target, Issue):
        return NotificationTarget.ISSUE, target.pk
    if isinstance(target, Milestone):
        return NotificationTarget.MILESTONE, target.pk
    if isinstance(target, Project):
        return NotificationTarget.PROJECT, target.pk
    return "", getattr(target, "pk", None)


def _target_users(target):
    """Users naturally attached to the target: assignee, collaborators, manager, owner."""
    from apps.projects.models import Milestone
    from apps.work.models import Issue, Task

    users = []
    project = _target_project(target)
    if project is not None and project.manager_id:
        users.append(project.manager)
    if isinstance(target, Task):
        if target.assignee_id:
            users.append(target.assignee)
        users.extend(target.collaborators.all())
    elif isinstance(target, Issue):
        if target.owner_id:
            users.append(target.owner)
    elif isinstance(target, Milestone):
        if target.owner_id:
            users.append(target.owner)
    return users


def _target_watchers(target):
    """Watchers of the target itself plus watchers of its project."""
    from apps.work.models import Task

    users = []
    if isinstance(target, Task):
        users.extend(watcher_users(SubscriptionTarget.TASK, target.pk))
    project = _target_project(target)
    if project is not None:
        users.extend(watcher_users(SubscriptionTarget.PROJECT, project.pk))
    return users


def resolve_recipients(actor, target, recipients=None, project=None):
    """Active users who may see the project, excluding the actor."""
    from apps.identity.permissions import visible_projects

    project = project or _target_project(target)
    candidates = list(recipients or []) + _target_users(target) + _target_watchers(target)
    resolved = []
    seen = set()
    for user in candidates:
        if user is None or not getattr(user, "is_active", False):
            continue
        if not getattr(user, "is_authenticated", False):
            continue
        if actor is not None and actor.pk == user.pk:
            continue
        if user.pk in seen:
            continue
        if project is not None and not visible_projects(user).filter(pk=project.pk).exists():
            continue
        seen.add(user.pk)
        resolved.append(user)
    return resolved


def notify(
    actor,
    verb,
    target,
    recipients=None,
    *,
    title,
    body="",
    url="",
    dedupe_suffix="",
    project=None,
):
    """Create one in-app notification per eligible recipient.

    ``dedupe_key`` is stable for the same verb, target, change signature, and
    recipient, so repeated saves or retried requests never duplicate a row.
    """
    project = project or _target_project(target)
    target_type, target_id = _target_ref(target)
    if not target_type:
        return []
    recipients = resolve_recipients(actor, target, recipients=recipients, project=project)
    if not recipients:
        return []
    preferences = {
        pref.user_id: pref
        for pref in NotificationPreference.objects.filter(user__in=recipients)
    }
    created = []
    for user in recipients:
        preference = preferences.get(user.pk)
        if preference is not None and not preference.in_app:
            continue
        key = f"{verb}:{target_type}:{target_id}:{dedupe_suffix}:{user.pk}"[:255]
        notification, was_created = Notification.objects.get_or_create(
            dedupe_key=key,
            defaults={
                "recipient": user,
                "actor": actor,
                "verb": verb,
                "target_type": target_type,
                "target_id": target_id,
                "title": title[:200],
                "body": body,
                "url": url[:500],
            },
        )
        if was_created:
            created.append(notification)
    return created


def unread_count(user):
    if not user.is_authenticated:
        return 0
    return Notification.objects.filter(recipient=user, read_at__isnull=True).count()


def today_token():
    return timezone.localdate().isoformat()


def user_display(user):
    if user is None:
        return "Sistem"
    profile = getattr(user, "pcc_profile", None)
    if profile is not None:
        return profile.name
    return user.get_full_name() or user.username


__all__ = [
    "get_preference",
    "notify",
    "resolve_recipients",
    "today_token",
    "unread_count",
    "user_display",
]
