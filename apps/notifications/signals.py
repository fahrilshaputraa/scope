"""Auto-subscribe the people naturally attached to a project or task."""

from django.contrib.auth import get_user_model
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from apps.projects.models import Project
from apps.work.models import Task, TaskComment

from .subscriptions import (
    subscribe_project_manager,
    subscribe_task_assignee,
    subscribe_task_collaborators,
    subscribe_task_comment,
)


@receiver(post_save, sender=Project)
def auto_subscribe_project_manager(sender, instance, raw=False, **kwargs):
    if raw:
        return
    subscribe_project_manager(instance)


@receiver(post_save, sender=Task)
def auto_subscribe_task_assignee(sender, instance, raw=False, **kwargs):
    if raw:
        return
    subscribe_task_assignee(instance)


@receiver(m2m_changed, sender=Task.collaborators.through)
def auto_subscribe_task_collaborators(sender, instance, action, pk_set, reverse, **kwargs):
    if action != "post_add" or reverse or not pk_set:
        return
    if not isinstance(instance, Task):
        return
    users = get_user_model().objects.filter(pk__in=pk_set)
    subscribe_task_collaborators(instance, users)


@receiver(post_save, sender=TaskComment)
def auto_subscribe_comment_author(sender, instance, raw=False, **kwargs):
    if raw:
        return
    subscribe_task_comment(instance)
