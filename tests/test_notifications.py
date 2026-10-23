from datetime import date
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from apps.identity.models import Role
from apps.notifications.models import Notification, NotificationPreference
from apps.notifications.services import notify
from apps.projects.models import ActivityAction, Milestone, Project
from apps.projects.services import record_activity
from apps.work.models import Issue, Task

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup_notifications(db):
    pm = User.objects.create_user("owner", password="valid-password")
    pm.pcc_profile.role = Role.PROJECT_MANAGER
    pm.pcc_profile.save()
    member = User.objects.create_user("member", password="valid-password")
    stranger = User.objects.create_user("stranger", password="valid-password")
    management = User.objects.create_user("management", password="valid-password")
    management.pcc_profile.role = Role.MANAGEMENT
    management.pcc_profile.save()
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
    issue = Issue.objects.create(project=project, title="Bug", owner=member)
    milestone = Milestone.objects.create(
        project=project, name="Beta", date=date(2026, 10, 20), owner=member
    )
    return SimpleNamespace(
        pm=pm,
        member=member,
        stranger=stranger,
        management=management,
        project=project,
        task=task,
        issue=issue,
        milestone=milestone,
    )


@pytest.mark.parametrize(
    "action,target_name",
    [
        (ActivityAction.TASK_CREATED, "task"),
        (ActivityAction.TASK_ASSIGNED, "task"),
        (ActivityAction.TASK_STATUS, "task"),
        (ActivityAction.TIMELINE_CHANGED, "task"),
        (ActivityAction.COMMENT_ADDED, "task"),
        (ActivityAction.ISSUE_CREATED, "issue"),
        (ActivityAction.ISSUE_ASSIGNED, "issue"),
        (ActivityAction.ISSUE_UPDATED, "issue"),
        (ActivityAction.MILESTONE_COMPLETED, "milestone"),
    ],
)
def test_required_events_create_one_notification(setup_notifications, action, target_name):
    data = setup_notifications
    target = getattr(data, target_name)
    record_activity(data.project, data.pm, action, "Perubahan.", target=target)
    notifications = Notification.objects.filter(recipient=data.member)
    assert notifications.count() == 1
    notification = notifications.get()
    assert notification.title
    assert notification.url.startswith("/")


def test_one_notification_per_event(setup_notifications):
    data = setup_notifications
    record_activity(
        data.project,
        data.pm,
        ActivityAction.TASK_STATUS,
        "Status changed.",
        target=data.task,
    )
    record_activity(
        data.project,
        data.pm,
        ActivityAction.TASK_STATUS,
        "Status changed again on a repeated save.",
        target=data.task,
    )
    assert Notification.objects.filter(recipient=data.member).count() == 1


def test_self_action_suppressed(setup_notifications):
    data = setup_notifications
    data.task.assignee = data.pm
    data.task.save(update_fields=["assignee"])
    record_activity(
        data.project,
        data.pm,
        ActivityAction.TASK_CREATED,
        "Task created.",
        target=data.task,
    )
    assert Notification.objects.filter(recipient=data.pm).count() == 0


def test_recipients_filtered_by_project_access(setup_notifications):
    data = setup_notifications
    notify(
        data.pm,
        "task.assigned",
        data.task,
        recipients=[data.stranger],
        title="Penugasan",
    )
    assert Notification.objects.filter(recipient=data.stranger).count() == 0
    assert Notification.objects.filter(recipient=data.member).count() == 1


def test_in_app_preference_off_suppresses(setup_notifications):
    data = setup_notifications
    NotificationPreference.objects.create(user=data.member, in_app=False)
    record_activity(
        data.project,
        data.pm,
        ActivityAction.TASK_STATUS,
        "Status changed.",
        target=data.task,
    )
    assert Notification.objects.filter(recipient=data.member).count() == 0


def test_bell_unread_count(client, setup_notifications):
    data = setup_notifications
    record_activity(
        data.project,
        data.pm,
        ActivityAction.TASK_STATUS,
        "Status changed.",
        target=data.task,
    )
    client.force_login(data.member)
    response = client.get(reverse("projects:dashboard"))
    assert response.status_code == 200
    assert response.context["unread_notification_count"] == 1
    assert b"notification-badge" in response.content


def _create_notifications(user, task, count):
    for index in range(count):
        Notification.objects.create(
            recipient=user,
            verb="task.status",
            target_type="task",
            target_id=task.pk,
            title=f"Notifikasi {index}",
            dedupe_key=f"test:{user.pk}:{index}",
        )


def test_center_filter_and_pagination(client, setup_notifications):
    data = setup_notifications
    _create_notifications(data.member, data.task, 30)
    Notification.objects.filter(recipient=data.member).first().mark_read()
    client.force_login(data.member)

    response = client.get(reverse("notifications:center"))
    assert response.status_code == 200
    assert response.context["page_obj"].paginator.count == 30
    assert len(response.context["notifications"]) == 25

    response = client.get(reverse("notifications:center"), {"filter": "unread"})
    assert response.context["page_obj"].paginator.count == 29
    assert response.context["unread_count"] == 29

    response = client.get(reverse("notifications:center"), {"filter": "all", "page": 2})
    assert len(response.context["notifications"]) == 5


def test_center_empty_state(client, setup_notifications):
    client.force_login(setup_notifications.member)
    response = client.get(reverse("notifications:center"))
    assert response.status_code == 200
    assert b"Belum ada notifikasi" in response.content


def test_mark_one_read_and_mark_all_read(client, setup_notifications):
    data = setup_notifications
    _create_notifications(data.member, data.task, 2)
    first, second = Notification.objects.filter(recipient=data.member)
    client.force_login(data.member)

    response = client.post(reverse("notifications:mark_read", args=[first.pk]))
    assert response.status_code == 302
    first.refresh_from_db()
    assert first.read_at is not None
    second.refresh_from_db()
    assert second.read_at is None

    assert client.get(reverse("notifications:mark_read", args=[second.pk])).status_code == 405

    response = client.post(reverse("notifications:mark_all_read"))
    assert response.status_code == 302
    assert Notification.objects.filter(
        recipient=data.member, read_at__isnull=True
    ).count() == 0


def test_non_recipient_access_denied(client, setup_notifications):
    data = setup_notifications
    notification = Notification.objects.create(
        recipient=data.member,
        verb="task.status",
        target_type="task",
        target_id=data.task.pk,
        title="Milik member",
        dedupe_key="test:denied",
    )
    client.force_login(data.stranger)
    response = client.post(reverse("notifications:mark_read", args=[notification.pk]))
    assert response.status_code == 404

    client.post(reverse("notifications:mark_all_read"))
    notification.refresh_from_db()
    assert notification.read_at is None


def test_mark_unread_restores_unread_state(client, setup_notifications):
    data = setup_notifications
    notification = Notification.objects.create(
        recipient=data.member,
        verb="task.status",
        target_type="task",
        target_id=data.task.pk,
        title="Sudah dibaca",
        dedupe_key="test:unread",
        read_at=timezone.now(),
    )
    client.force_login(data.member)
    response = client.post(reverse("notifications:mark_unread", args=[notification.pk]))
    assert response.status_code == 302
    notification.refresh_from_db()
    assert notification.read_at is None
