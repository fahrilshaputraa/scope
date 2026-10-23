"""Parsing and validation for ``@username`` mentions in task comments (B3)."""

import re

from django.contrib.auth.models import User
from django.db.models import Q

from apps.identity.models import Role
from apps.identity.permissions import visible_projects

#: Usernames as accepted by Django's default User model: letters, digits and @/./+/-/_.
#: The lookbehind keeps e-mail addresses (``name@example.com``) from becoming mentions.
MENTION_RE = re.compile(r"(?<![A-Za-z0-9_.@+\-])@([A-Za-z0-9_.@+\-]+)")

MAX_SUGGESTIONS = 8


def extract_mentions(content: str) -> list[str]:
    """Return unique handles in the order they first appear."""
    return list(dict.fromkeys(MENTION_RE.findall(content or "")))


def resolve_mentions(content: str, project) -> tuple[list[User], list[str]]:
    """Validate every handle in ``content`` against the comment's project.

    Returns the resolved users (deduplicated) and Indonesian error messages for
    handles that do not exist, are inactive, or cannot see the project.
    """
    users: list[User] = []
    errors: list[str] = []
    for handle in extract_mentions(content):
        user = User.objects.filter(username=handle).first()
        if user is None:
            errors.append(f'Mention "@{handle}" tidak ditemukan.')
            continue
        if not user.is_active:
            errors.append(f'Pengguna "@{handle}" tidak aktif.')
            continue
        if project is None or not visible_projects(user).filter(pk=project.pk).exists():
            errors.append(f'Pengguna "@{handle}" tidak punya akses ke project ini.')
            continue
        users.append(user)
    return users, errors


def project_audience(project, query: str = ""):
    """Active users who can see ``project``, mirroring ``visible_projects``."""
    audience = (
        User.objects.filter(is_active=True)
        .filter(
            Q(is_staff=True)
            | Q(pcc_profile__role=Role.MANAGEMENT)
            | Q(managed_projects=project)
            | Q(member_projects=project)
            | Q(assigned_tasks__project=project, assigned_tasks__archived_at__isnull=True)
            | Q(
                collaborating_tasks__project=project,
                collaborating_tasks__archived_at__isnull=True,
            )
        )
        .distinct()
    )
    query = (query or "").strip().lstrip("@")
    if query:
        audience = audience.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(pcc_profile__display_name__icontains=query)
        )
    return audience.select_related("pcc_profile").order_by("username")


def suggestion_payload(project, query: str = "") -> list[dict]:
    rows = []
    for user in project_audience(project, query)[:MAX_SUGGESTIONS]:
        profile = getattr(user, "pcc_profile", None)
        name = profile.name if profile is not None else user.get_full_name() or user.username
        rows.append({"username": user.username, "name": name})
    return rows


__all__ = [
    "MAX_SUGGESTIONS",
    "MENTION_RE",
    "extract_mentions",
    "project_audience",
    "resolve_mentions",
    "suggestion_payload",
]
