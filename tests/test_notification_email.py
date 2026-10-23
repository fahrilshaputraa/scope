from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.identity.models import Role
from apps.notifications.models import (
    DigestFrequency,
    Notification,
    NotificationPreference,
)
from apps.projects.models import Project
from apps.projects.scheduler import tick
from apps.work.models import Task

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup_email(db):
    pm = User.objects.create_user(
        "owner", password="valid-password", email="owner@example.com"
    )
    pm.pcc_profile.role = Role.PROJECT_MANAGER
    pm.pcc_profile.save()
    member = User.objects.create_user(
        "member", password="valid-password", email="member@example.com"
    )
    project = Project.objects.create(
        name="Private project",
        code="PRIVATE",
        manager=pm,
        start_date=date(2026, 10, 1),
        target_end_date=date(2026, 11, 1),
    )
    project.members.add(member)
    task = Task.objects.create(
        project=project,
        title="Build",
        assignee=member,
        start_date=date(2026, 10, 2),
        due_date=date(2026, 10, 10),
    )
    return SimpleNamespace(pm=pm, member=member, project=project, task=task)


def make_notification(user, task, suffix, title=None):
    return Notification.objects.create(
        recipient=user,
        verb="task.status",
        target_type="task",
        target_id=task.pk,
        title=title or f"Status tugas berubah: {task.title}",
        body="Status sekarang in_progress.",
        url=reverse("work:task_detail", args=[task.pk]),
        dedupe_key=f"test:{user.pk}:{suffix}",
    )


def test_email_disabled_sends_nothing(setup_email):
    data = setup_email
    NotificationPreference.objects.create(user=data.member, email=False)
    notification = make_notification(data.member, data.task, "disabled")

    call_command("send_notification_emails")

    assert len(mail.outbox) == 0
    notification.refresh_from_db()
    assert notification.emailed_at is None


def test_email_enabled_sends_one_email_per_notification(setup_email):
    data = setup_email
    NotificationPreference.objects.create(user=data.member, email=True)
    first = make_notification(data.member, data.task, "one")
    second = make_notification(data.member, data.task, "two")

    call_command("send_notification_emails")

    assert len(mail.outbox) == 2
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.emailed_at is not None
    assert second.emailed_at is not None
    message = mail.outbox[0]
    assert message.subject.startswith("[Scope]")
    assert "Status sekarang in_progress." in message.body
    assert reverse("work:task_detail", args=[data.task.pk]) in message.body
    assert "http://testserver" in message.body
    assert "Waktu:" in message.body


def test_repeated_command_does_not_duplicate(setup_email):
    data = setup_email
    NotificationPreference.objects.create(user=data.member, email=True)
    make_notification(data.member, data.task, "repeat")

    call_command("send_notification_emails")
    call_command("send_notification_emails")

    assert len(mail.outbox) == 1


def test_daily_digest_groups_notifications_and_marks_them(setup_email):
    data = setup_email
    preference = NotificationPreference.objects.create(
        user=data.member, email=True, digest=DigestFrequency.DAILY
    )
    other_project = Project.objects.create(
        name="Other project",
        code="OTHER",
        manager=data.pm,
        start_date=date(2026, 10, 1),
        target_end_date=date(2026, 11, 1),
    )
    other_project.members.add(data.member)
    other_task = Task.objects.create(
        project=other_project,
        title="Ship",
        assignee=data.member,
        start_date=date(2026, 10, 2),
        due_date=date(2026, 10, 10),
    )
    first = make_notification(data.member, data.task, "d1")
    second = make_notification(data.member, data.task, "d2", title="Komentar baru: Build")
    third = make_notification(data.member, other_task, "d3")

    call_command("send_notification_digest", "--frequency", "daily")

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert "Ringkasan notifikasi harian" in message.subject
    assert "Private project (PRIVATE) — 2 notifikasi" in message.body
    assert "Other project (OTHER) — 1 notifikasi" in message.body
    assert "3 pembaruan" in message.body
    for notification in (first, second, third):
        notification.refresh_from_db()
        assert notification.emailed_at is not None
    preference.refresh_from_db()
    assert preference.digest_sent_at is not None

    call_command("send_notification_digest", "--frequency", "daily")
    assert len(mail.outbox) == 1


def test_weekly_digest_respects_its_window(setup_email):
    data = setup_email
    preference = NotificationPreference.objects.create(
        user=data.member, email=True, digest=DigestFrequency.WEEKLY
    )
    make_notification(data.member, data.task, "w1")

    call_command("send_notification_digest", "--frequency", "daily")
    assert len(mail.outbox) == 0

    call_command("send_notification_digest", "--frequency", "weekly")
    assert len(mail.outbox) == 1
    preference.refresh_from_db()
    assert preference.digest_sent_at is not None

    make_notification(data.member, data.task, "w2")
    call_command("send_notification_digest", "--frequency", "weekly")
    assert len(mail.outbox) == 1

    preference.digest_sent_at = timezone.now() - timedelta(days=8)
    preference.save(update_fields=["digest_sent_at"])
    call_command("send_notification_digest", "--frequency", "weekly")
    assert len(mail.outbox) == 2
    assert "Ringkasan notifikasi mingguan" in mail.outbox[1].subject


def test_digest_off_sends_no_digest(setup_email):
    data = setup_email
    NotificationPreference.objects.create(
        user=data.member, email=True, digest=DigestFrequency.OFF
    )
    notification = make_notification(data.member, data.task, "off")

    call_command("send_notification_digest", "--frequency", "daily")
    call_command("send_notification_digest", "--frequency", "weekly")

    assert len(mail.outbox) == 0
    notification.refresh_from_db()
    assert notification.emailed_at is None


def test_preference_form_saves_only_current_user(client, setup_email):
    data = setup_email
    own = NotificationPreference.objects.create(
        user=data.member, in_app=True, email=False, digest=DigestFrequency.OFF
    )
    other = NotificationPreference.objects.create(user=data.pm, email=False)

    client.force_login(data.member)
    response = client.post(
        reverse("identity:settings"),
        {"action": "notifications", "email": "on", "digest": "weekly"},
    )

    assert response.status_code == 302
    own.refresh_from_db()
    other.refresh_from_db()
    assert own.in_app is False
    assert own.email is True
    assert own.digest == DigestFrequency.WEEKLY
    assert other.email is False
    assert other.digest == DigestFrequency.OFF

    response = client.get(reverse("identity:settings"))
    assert response.status_code == 200
    assert b"Frekuensi digest" in response.content


def test_settings_get_does_not_create_preference(client, setup_email):
    data = setup_email
    NotificationPreference.objects.filter(user=data.member).delete()
    client.force_login(data.member)

    assert client.get(reverse("identity:settings")).status_code == 200

    assert not NotificationPreference.objects.filter(user=data.member).exists()


def test_scheduler_tick_survives_without_pending_email(db):
    assert tick() == 0
    assert len(mail.outbox) == 0
