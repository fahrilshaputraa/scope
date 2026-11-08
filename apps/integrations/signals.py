"""Queue Teams messages from the existing notification fan-out.

Receivers only write queue rows, and only after the surrounding transaction
commits, so a page save never waits on (or fails because of) Teams. Several
``Notification`` rows for one change (one per recipient) map to the same
dedupe key, so the channel gets a single message.
"""

import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.notifications.models import Notification
from apps.work.models import CommentMention, Issue, Mention, Priority, Task, TaskStatus

logger = logging.getLogger(__name__)


def _later(func, *args):
    def run():
        try:
            func(*args)
        except Exception:  # integrations must never break the user's action
            logger.exception("Queueing Teams message failed.")

    transaction.on_commit(run)


def _change_suffix(notification) -> str:
    """Notification dedupe key without the trailing recipient id."""
    key = notification.dedupe_key or ""
    return key.rsplit(":", 1)[0] if ":" in key else key


def _from_notification(notification_id):
    from .events import queue_blocked_task, queue_critical_issue

    notification = Notification.objects.filter(pk=notification_id).select_related("actor").first()
    if notification is None or notification.target_id is None:
        return
    if notification.verb == "task.status":
        task = Task.objects.filter(pk=notification.target_id).select_related("project").first()
        if task is not None and task.status == TaskStatus.BLOCKED:
            queue_blocked_task(task, _change_suffix(notification), notification.actor)
    elif notification.verb == "issue.created":
        issue = Issue.objects.filter(pk=notification.target_id).select_related("project").first()
        if issue is not None and issue.severity == Priority.CRITICAL:
            queue_critical_issue(issue)


@receiver(post_save, sender=Notification)
def teams_from_notification(sender, instance, created, raw=False, **kwargs):
    if raw or not created or instance.verb not in ("task.status", "issue.created"):
        return
    _later(_from_notification, instance.pk)


def _from_task_mention(mention_id):
    from .events import queue_task_mention

    mention = (
        Mention.objects.filter(pk=mention_id)
        .select_related("user", "task_comment__author", "task_comment__task__project")
        .first()
    )
    if mention is not None:
        queue_task_mention(mention)


def _from_comment_mention(mention_id):
    from .events import queue_comment_mention

    mention = (
        CommentMention.objects.filter(pk=mention_id)
        .select_related("user", "comment__author", "comment__project")
        .first()
    )
    if mention is not None:
        queue_comment_mention(mention)


@receiver(post_save, sender=Mention)
def teams_from_task_mention(sender, instance, created, raw=False, **kwargs):
    if raw or not created:
        return
    _later(_from_task_mention, instance.pk)


@receiver(post_save, sender=CommentMention)
def teams_from_comment_mention(sender, instance, created, raw=False, **kwargs):
    if raw or not created:
        return
    _later(_from_comment_mention, instance.pk)
