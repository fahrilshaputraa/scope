"""Siapa yang boleh ditugaskan pada task sebuah project (PRD §9.2, BR-TASK-004)."""

from django.contrib.auth.models import User
from django.db.models import Q

from apps.identity.roles import executor_role_codes


def assignable_users(project, current_id=None):
    """Pelaksana yang terlibat di project, tanpa PM project.

    ``current_id`` tetap disertakan supaya data lama (assignee yang kini tidak
    memenuhi syarat) tidak membuat form tidak valid.
    """
    candidates = User.objects.filter(is_active=True).filter(
        Q(member_projects=project)
        | Q(assigned_tasks__project=project)
        | Q(collaborating_tasks__project=project)
    )
    executors = Q(memberships__role__code__in=executor_role_codes()) | Q(is_staff=True)
    allowed = candidates.filter(executors).exclude(pk=project.manager_id)
    if current_id:
        allowed = allowed | candidates.filter(pk=current_id)
    return allowed.distinct()
