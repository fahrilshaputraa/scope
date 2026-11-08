"""Who may configure Teams webhooks.

* Project webhook: ``project.update`` on a project the user manages (same rule
  as editing the project: ``can_manage_project``).
* Global webhook: ``user.manage`` (workspace administrators).
"""

from apps.identity.permissions import can_manage_project, is_admin, visible_projects
from apps.identity.roles import has_perm


def can_manage_global(user) -> bool:
    return user.is_authenticated and has_perm(user, "user.manage")


def manageable_projects(user):
    projects = visible_projects(user)
    if not user.is_authenticated or not has_perm(user, "project.update"):
        return projects.none()
    if is_admin(user):
        return projects
    return projects.filter(manager=user)


def can_configure_teams(user) -> bool:
    return can_manage_global(user) or manageable_projects(user).exists()


def can_manage_webhook(user, webhook) -> bool:
    if webhook.project_id is None:
        return can_manage_global(user)
    project = webhook.project
    return (
        can_manage_project(user, project) and visible_projects(user).filter(pk=project.pk).exists()
    )
