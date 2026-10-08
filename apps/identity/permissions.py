"""Authorization sederhana berdasarkan role (PRD §30)."""

from django.db.models import Q

from .models import Role


def role_of(user) -> str:
    if not user.is_authenticated:
        return ""
    profile = getattr(user, "pcc_profile", None)
    if profile is None:
        return Role.MEMBER
    return profile.role


def is_management(user) -> bool:
    return role_of(user) == Role.MANAGEMENT


def is_pm(user) -> bool:
    return role_of(user) == Role.PROJECT_MANAGER


def can_create_project(user) -> bool:
    """PM boleh membuat project; management & member tidak (PRD §30)."""
    return user.is_authenticated and (is_pm(user) or user.is_staff)


def can_manage_project(user, project) -> bool:
    """Edit project/timeline/task/milestone/issue/notes: PM atau manager project."""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    if not is_pm(user):
        return False
    return project.manager_id == user.id or project.manager is None


def can_edit_task(user, task) -> bool:
    """Member boleh update task-nya sendiri; PM bebas (PRD §30)."""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    if can_manage_project(user, task.project):
        return True
    return not is_management(user) and (
        task.assignee_id == user.id or task.collaborators.filter(pk=user.pk).exists()
    )


def can_report_issue(user) -> bool:
    """Member boleh melaporkan issue (PRD §30)."""
    return user.is_authenticated and (user.is_staff or not is_management(user))


def visible_projects(user):
    """The single read scope for pages, exports, comments, and downloads."""
    from apps.projects.models import Project

    qs = Project.objects.all()
    if not user.is_authenticated:
        return qs.none()
    if user.is_staff or is_management(user):
        return qs
    return qs.filter(
        Q(manager=user) | Q(members=user) | Q(tasks__assignee=user) | Q(tasks__collaborators=user)
    ).distinct()


def can_view_project(user, project):
    return visible_projects(user).filter(pk=project.pk).exists()
