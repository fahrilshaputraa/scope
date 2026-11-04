"""Authorization berbasis permission dan role aktif (PRD §25).

Fungsi ``can_*`` dan ``visible_projects`` mempertahankan nama lama supaya view
tidak perlu berubah; semuanya sekarang membaca ``RoleDefinition.permissions``
lewat role aktif user.
"""

from django.db.models import Q

from .models import Role
from .roles import active_role, has_perm


def role_of(user) -> str:
    """Kode role aktif user, atau string kosong bila belum login."""
    return active_role(user)


def is_admin(user) -> bool:
    return role_of(user) == Role.ADMIN


def is_management(user) -> bool:
    return role_of(user) == Role.MANAGEMENT


def is_pm(user) -> bool:
    return role_of(user) == Role.PROJECT_MANAGER


def can_create_project(user) -> bool:
    return user.is_authenticated and has_perm(user, "project.create")


def can_manage_project(user, project) -> bool:
    """Edit project/timeline/task/milestone/issue/notes: admin, atau PM project."""
    if not user.is_authenticated or not has_perm(user, "project.update"):
        return False
    if is_admin(user):
        return True
    return project.manager_id == user.id or project.manager is None


def can_execute_task(user, task) -> bool:
    """Memperbarui status dan progress: pelaksana task, atau Admin (PRD §10.3, BR-TASK-008).

    PM mengontrol dan merencanakan (``can_manage_project``) tetapi tidak memperbarui
    actual progress sebagai pelaksana.
    """
    if not user.is_authenticated:
        return False
    if is_admin(user):
        return True
    return has_perm(user, "task.update_progress") and (
        task.assignee_id == user.id or task.collaborators.filter(pk=user.pk).exists()
    )


def can_report_issue(user) -> bool:
    return user.is_authenticated and has_perm(user, "issue.report")


def can_view_internal(user) -> bool:
    """Catatan, issue, dan aktivitas internal tidak untuk Client (PRD §3.5)."""
    return user.is_authenticated and has_perm(user, "project.view_internal")


def require_internal(user) -> None:
    from django.core.exceptions import PermissionDenied

    if not can_view_internal(user):
        raise PermissionDenied


def can_monitor_tasks(user) -> bool:
    return user.is_authenticated and has_perm(user, "task.monitor")


def can_control_projects(user) -> bool:
    return user.is_authenticated and has_perm(user, "project.control")


def controlled_projects(user):
    """Project yang dikontrol user: semuanya untuk Admin, selain itu yang dikelolanya."""
    projects = visible_projects(user)
    if is_admin(user):
        return projects
    return projects.filter(manager=user)


def can_comment(user) -> bool:
    return user.is_authenticated and has_perm(user, "comment.create")


def visible_projects(user, include_archived=False):
    """The single read scope for pages, exports, comments, and downloads."""
    from apps.projects.models import Project

    qs = Project.all_objects.all() if include_archived else Project.objects.all()
    if not user.is_authenticated:
        return qs.none()
    if has_perm(user, "project.view_all"):
        return qs
    return qs.filter(
        Q(manager=user)
        | Q(owner=user)
        | Q(members=user)
        | Q(tasks__assignee=user, tasks__archived_at__isnull=True)
        | Q(tasks__collaborators=user, tasks__archived_at__isnull=True)
    ).distinct()


def can_view_project(user, project):
    return visible_projects(user).filter(pk=project.pk).exists()
