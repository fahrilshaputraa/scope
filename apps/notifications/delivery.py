"""Queued email delivery for notifications (B2).

Nothing here runs inside a web request. The management commands and the opt-in
internal scheduler call these functions, so a slow or failing SMTP server never
blocks a page load. ``Notification.emailed_at`` is the queue marker: once set,
the same notification is never emailed again.
"""

import logging
from collections import OrderedDict
from datetime import timedelta
from urllib.parse import urljoin

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

from apps.projects.models import Milestone, Project
from apps.work.models import Issue, Task

from .models import DigestFrequency, Notification, NotificationPreference
from .services import user_display

logger = logging.getLogger(__name__)

VERB_LABELS = {
    "project.updated": "project diperbarui",
    "task.created": "tugas baru",
    "task.assigned": "penugasan tugas",
    "task.status": "perubahan status tugas",
    "task.dates": "perubahan jadwal tugas",
    "comment.added": "komentar baru",
    "issue.created": "issue baru",
    "issue.assigned": "penugasan issue",
    "issue.updated": "perubahan jadwal issue",
    "milestone.completed": "milestone selesai",
}

FREQUENCY_LABELS = {
    DigestFrequency.DAILY: "harian",
    DigestFrequency.WEEKLY: "mingguan",
}


def absolute_url(path: str) -> str:
    """Build an absolute link from the request-independent site URL."""
    base = getattr(settings, "SITE_URL", "").rstrip("/")
    if not path:
        return base
    return urljoin(f"{base}/", path.lstrip("/"))


def relative_time(value) -> str:
    """Short Indonesian relative time, falling back to an absolute date."""
    if value is None:
        return "waktu tidak diketahui"
    seconds = int((timezone.now() - value).total_seconds())
    if seconds < 60:
        return "baru saja"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} menit lalu"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} jam lalu"
    days = hours // 24
    if days < 7:
        return f"{days} hari lalu"
    return timezone.localtime(value).strftime("%d-%m-%Y")


def _action_label(notification: Notification) -> str:
    return VERB_LABELS.get(notification.verb, notification.verb)


def _item_line(notification: Notification) -> str:
    actor = user_display(notification.actor)
    parts = [
        actor,
        _action_label(notification),
        notification.title,
        relative_time(notification.created_at),
    ]
    return " · ".join(part for part in parts if part)


def _notification_body(notification: Notification, recipient) -> str:
    lines = [
        f"Halo {user_display(recipient)},",
        "",
        f"{user_display(notification.actor)} — {_action_label(notification)}",
        notification.title,
    ]
    if notification.body:
        lines.extend(["", notification.body])
    lines.extend(
        [
            "",
            f"Waktu: {relative_time(notification.created_at)}",
            f"Buka: {absolute_url(notification.url)}",
            "",
            "Anda menerima email ini karena notifikasi email aktif di Pengaturan akun.",
        ]
    )
    return "\n".join(lines)


def _send(subject: str, body: str, recipient) -> bool:
    if not getattr(recipient, "email", ""):
        return False
    try:
        send_mail(
            subject,
            body,
            getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@localhost"),
            [recipient.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Notification email to user %s failed.", recipient.pk)
        return False
    return True


def _pending_for(preference: NotificationPreference):
    pending = Notification.objects.filter(
        recipient=preference.user,
        emailed_at__isnull=True,
    ).select_related("recipient", "actor")
    if preference.digest_sent_at is not None:
        pending = pending.filter(created_at__gt=preference.digest_sent_at)
    return pending.order_by("created_at", "id")


def deliver_pending_emails() -> int:
    """Send one email per pending notification for immediate-email users.

    Users who chose a daily or weekly digest are skipped here; their batching is
    handled by ``deliver_digest`` so they never receive both formats.
    """
    preferences = NotificationPreference.objects.filter(
        email=True,
        digest=DigestFrequency.OFF,
    ).select_related("user")
    sent_ids = []
    sent_count = 0
    for preference in preferences:
        recipient = preference.user
        if not recipient.is_active:
            continue
        notifications = list(_pending_for(preference))
        for notification in notifications:
            if not _send(
                f"[Scope] {notification.title}",
                _notification_body(notification, recipient),
                recipient,
            ):
                continue
            sent_ids.append(notification.pk)
            sent_count += 1
    if sent_ids:
        Notification.objects.filter(pk__in=sent_ids, emailed_at__isnull=True).update(
            emailed_at=timezone.now()
        )
    return sent_count


def _digest_due(preference: NotificationPreference, frequency: str) -> bool:
    if preference.digest_sent_at is None:
        return True
    now = timezone.now()
    if frequency == DigestFrequency.DAILY:
        return timezone.localtime(preference.digest_sent_at).date() < timezone.localdate()
    return now - preference.digest_sent_at >= timedelta(days=7)


def _resolve_project(notification: Notification):
    if notification.target_type == "project":
        return Project.objects.filter(pk=notification.target_id).first()
    if notification.target_type == "task":
        task = Task.objects.filter(pk=notification.target_id).select_related("project").first()
        return task.project if task is not None else None
    if notification.target_type == "issue":
        issue = Issue.objects.filter(pk=notification.target_id).select_related("project").first()
        return issue.project if issue is not None else None
    if notification.target_type == "milestone":
        milestone = (
            Milestone.objects.filter(pk=notification.target_id)
            .select_related("project")
            .first()
        )
        return milestone.project if milestone is not None else None
    return None


def _group_notifications(notifications):
    groups = OrderedDict()
    for notification in notifications:
        project = _resolve_project(notification)
        if project is not None:
            key = f"project:{project.pk}"
            label = f"{project.name} ({project.code})"
        else:
            key = f"type:{notification.target_type or 'lainnya'}"
            label = (
                notification.get_target_type_display()
                if notification.target_type
                else "Lainnya"
            )
        groups.setdefault(key, {"label": label, "items": []})["items"].append(notification)
    return groups.values()


def _digest_body(notifications, recipient, frequency: str) -> str:
    label = FREQUENCY_LABELS.get(frequency, frequency)
    lines = [
        f"Halo {user_display(recipient)},",
        "",
        f"Berikut ringkasan notifikasi {label} Anda ({len(notifications)} pembaruan).",
    ]
    for group in _group_notifications(notifications):
        lines.extend(["", f"{group['label']} — {len(group['items'])} notifikasi"])
        for notification in group["items"]:
            lines.append(f"- {_item_line(notification)}")
            if notification.url:
                lines.append(f"  {absolute_url(notification.url)}")
    lines.extend(
        [
            "",
            f"Pusat notifikasi: {absolute_url(reverse('notifications:center'))}",
            f"Preferensi: {absolute_url(reverse('identity:settings'))}",
            "",
            "Anda menerima ringkasan ini karena preferensi digest aktif di Pengaturan akun.",
        ]
    )
    return "\n".join(lines)


def deliver_digest(frequency: str) -> int:
    """Send one grouped digest per eligible user for the given frequency."""
    if frequency not in (DigestFrequency.DAILY, DigestFrequency.WEEKLY):
        return 0
    preferences = NotificationPreference.objects.filter(
        email=True,
        digest=frequency,
    ).select_related("user")
    sent_count = 0
    for preference in preferences:
        recipient = preference.user
        if not recipient.is_active or not _digest_due(preference, frequency):
            continue
        notifications = list(_pending_for(preference))
        if not notifications:
            continue
        total = len(notifications)
        subject = f"[Scope] Ringkasan notifikasi {FREQUENCY_LABELS[frequency]} — {total} pembaruan"
        if not _send(subject, _digest_body(notifications, recipient, frequency), recipient):
            continue
        Notification.objects.filter(
            pk__in=[notification.pk for notification in notifications],
            emailed_at__isnull=True,
        ).update(emailed_at=timezone.now())
        preference.digest_sent_at = timezone.now()
        preference.save(update_fields=["digest_sent_at", "updated_at"])
        sent_count += 1
    return sent_count


def deliver_due_digests() -> int:
    """Run both digest windows; used by the internal scheduler tick."""
    return deliver_digest(DigestFrequency.DAILY) + deliver_digest(DigestFrequency.WEEKLY)


__all__ = [
    "absolute_url",
    "deliver_digest",
    "deliver_due_digests",
    "deliver_pending_emails",
    "relative_time",
]
