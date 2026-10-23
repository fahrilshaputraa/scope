"""Watch/follow helpers shared by views, signals, and the notify resolver."""

from .models import Subscription, SubscriptionOptOut, SubscriptionTarget


def is_watching(user, target_type: str, target_id: int) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return Subscription.objects.filter(
        user=user, target_type=target_type, target_id=target_id
    ).exists()


def watch(user, target_type: str, target_id: int) -> Subscription:
    """Explicit follow: clears any previous opt-out and forces a manual subscription."""
    SubscriptionOptOut.objects.filter(
        user=user, target_type=target_type, target_id=target_id
    ).delete()
    subscription, _ = Subscription.objects.update_or_create(
        user=user,
        target_type=target_type,
        target_id=target_id,
        defaults={"auto_subscribed": False},
    )
    return subscription


def unwatch(user, target_type: str, target_id: int) -> None:
    """Explicit unfollow: removes the row and remembers the opt-out."""
    Subscription.objects.filter(user=user, target_type=target_type, target_id=target_id).delete()
    SubscriptionOptOut.objects.get_or_create(
        user=user, target_type=target_type, target_id=target_id
    )


def auto_subscribe(user, target_type: str, target_id: int) -> Subscription | None:
    """Follow on assignment or comment, unless the user explicitly unwatched."""
    if user is None or not getattr(user, "pk", None):
        return None
    if not getattr(user, "is_active", False):
        return None
    if SubscriptionOptOut.objects.filter(
        user=user, target_type=target_type, target_id=target_id
    ).exists():
        return None
    subscription, _ = Subscription.objects.get_or_create(
        user=user,
        target_type=target_type,
        target_id=target_id,
        defaults={"auto_subscribed": True},
    )
    return subscription


def watcher_users(target_type: str, target_id: int):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.filter(
        is_active=True,
        subscriptions__target_type=target_type,
        subscriptions__target_id=target_id,
    )


def watch_state(user, target_type: str, target_id: int) -> dict:
    if not getattr(user, "is_authenticated", False):
        return {"is_watching": False, "watch_is_auto": False}
    subscription = Subscription.objects.filter(
        user=user, target_type=target_type, target_id=target_id
    ).first()
    return {
        "is_watching": subscription is not None,
        "watch_is_auto": bool(subscription and subscription.auto_subscribed),
    }


def subscribe_task_assignee(task) -> None:
    auto_subscribe(task.assignee, SubscriptionTarget.TASK, task.pk)


def subscribe_task_collaborators(task, users) -> None:
    for user in users:
        auto_subscribe(user, SubscriptionTarget.TASK, task.pk)


def subscribe_task_comment(comment) -> None:
    auto_subscribe(comment.author, SubscriptionTarget.TASK, comment.task_id)


def subscribe_project_manager(project) -> None:
    auto_subscribe(project.manager, SubscriptionTarget.PROJECT, project.pk)


__all__ = [
    "auto_subscribe",
    "is_watching",
    "subscribe_project_manager",
    "subscribe_task_assignee",
    "subscribe_task_collaborators",
    "subscribe_task_comment",
    "unwatch",
    "watch",
    "watch_state",
    "watcher_users",
]
