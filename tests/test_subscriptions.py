from datetime import date
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from apps.identity.models import Role
from apps.notifications.models import (
    Notification,
    Subscription,
    SubscriptionOptOut,
    SubscriptionTarget,
)
from apps.notifications.subscriptions import unwatch, watch
from apps.projects.models import ActivityAction, Milestone, Project
from apps.projects.services import record_activity
from apps.work.models import Issue, Task, TaskComment

pytestmark = pytest.mark.django_db


@pytest.fixture
def data(db):
    pm = User.objects.create_user("owner", password="valid-password")
    pm.pcc_profile.role = Role.PROJECT_MANAGER
    pm.pcc_profile.save()
    member = User.objects.create_user("member", password="valid-password")
    watcher = User.objects.create_user("watcher", password="valid-password")
    stranger = User.objects.create_user("stranger", password="valid-password")
    project = Project.objects.create(
        name="Watch project",
        code="WATCH",
        manager=pm,
        start_date=date(2026, 10, 1),
        target_end_date=date(2026, 11, 1),
    )
    project.members.add(member, watcher)
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
        watcher=watcher,
        stranger=stranger,
        project=project,
        task=task,
        issue=issue,
        milestone=milestone,
    )


def test_watch_and_unwatch_toggle_is_unique(data):
    watch(data.member, SubscriptionTarget.TASK, data.task.pk)
    watch(data.member, SubscriptionTarget.TASK, data.task.pk)
    assert Subscription.objects.filter(
        user=data.member, target_type=SubscriptionTarget.TASK, target_id=data.task.pk
    ).count() == 1

    unwatch(data.member, SubscriptionTarget.TASK, data.task.pk)
    assert not Subscription.objects.filter(
        user=data.member, target_type=SubscriptionTarget.TASK, target_id=data.task.pk
    ).exists()
    assert SubscriptionOptOut.objects.filter(
        user=data.member, target_type=SubscriptionTarget.TASK, target_id=data.task.pk
    ).exists()

    watch(data.member, SubscriptionTarget.TASK, data.task.pk)
    assert Subscription.objects.filter(
        user=data.member, target_type=SubscriptionTarget.TASK, target_id=data.task.pk
    ).count() == 1
    assert not SubscriptionOptOut.objects.filter(user=data.member).exists()


def test_watch_endpoint_is_post_only_and_csrf_protected(data):
    url = reverse("notifications:watch_project", args=[data.project.pk])
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(data.watcher)
    assert csrf_client.get(url).status_code == 405
    assert csrf_client.post(url).status_code == 403

    client = Client()
    client.force_login(data.watcher)
    response = client.post(url)
    assert response.status_code == 302
    assert Subscription.objects.filter(
        user=data.watcher, target_type=SubscriptionTarget.PROJECT, target_id=data.project.pk
    ).exists()


def test_project_and_task_detail_show_toggle_labels(client, data):
    client.force_login(data.watcher)
    response = client.get(reverse("projects:project_detail", args=[data.project.pk]))
    assert response.status_code == 200
    assert b"Ikuti" in response.content

    response = client.get(reverse("work:task_detail", args=[data.task.pk]))
    assert response.status_code == 200
    assert b"Ikuti" in response.content


def test_users_without_access_cannot_watch(client, data):
    client.force_login(data.stranger)
    response = client.post(reverse("notifications:watch_project", args=[data.project.pk]))
    assert response.status_code == 404
    response = client.post(reverse("notifications:watch_task", args=[data.task.pk]))
    assert response.status_code == 404
    assert not Subscription.objects.filter(user=data.stranger).exists()


def test_assignee_and_collaborators_auto_subscribe(data):
    collaborator = User.objects.create_user("collaborator", password="valid-password")
    data.project.members.add(collaborator)
    data.task.collaborators.add(collaborator)

    for user in (data.member, collaborator):
        subscription = Subscription.objects.get(
            user=user, target_type=SubscriptionTarget.TASK, target_id=data.task.pk
        )
        assert subscription.auto_subscribed is True


def test_comment_author_auto_subscribes(data):
    author = User.objects.create_user("commenter", password="valid-password")
    data.project.members.add(author)
    TaskComment.objects.create(task=data.task, author=author, content="Halo")

    assert Subscription.objects.filter(
        user=author, target_type=SubscriptionTarget.TASK, target_id=data.task.pk
    ).exists()


def test_project_manager_auto_subscribes(data):
    assert Subscription.objects.filter(
        user=data.pm, target_type=SubscriptionTarget.PROJECT, target_id=data.project.pk
    ).exists()


def test_explicit_unwatch_survives_later_saves(data):
    unwatch(data.watcher, SubscriptionTarget.TASK, data.task.pk)
    data.task.status = "in_progress"
    data.task.save()
    data.task.assignee = data.watcher
    data.task.save()

    assert not Subscription.objects.filter(
        user=data.watcher, target_type=SubscriptionTarget.TASK, target_id=data.task.pk
    ).exists()


def test_task_watcher_receives_status_and_comment_notifications(data):
    watch(data.watcher, SubscriptionTarget.TASK, data.task.pk)
    record_activity(
        data.project, data.pm, ActivityAction.TASK_STATUS, "Status berubah.", target=data.task
    )
    TaskComment.objects.create(task=data.task, author=data.member, content="Komentar")
    record_activity(
        data.project,
        data.member,
        ActivityAction.COMMENT_ADDED,
        "Komentar baru.",
        target=data.task,
        dedupe_token="1",
    )

    verbs = set(
        Notification.objects.filter(recipient=data.watcher).values_list("verb", flat=True)
    )
    assert {"task.status", "comment.added"} <= verbs


def test_project_watcher_receives_issue_and_milestone_notifications(data):
    watch(data.watcher, SubscriptionTarget.PROJECT, data.project.pk)
    record_activity(
        data.project, data.pm, ActivityAction.ISSUE_CREATED, "Issue baru.", target=data.issue
    )
    record_activity(
        data.project,
        data.pm,
        ActivityAction.MILESTONE_COMPLETED,
        "Milestone selesai.",
        target=data.milestone,
    )

    verbs = set(
        Notification.objects.filter(recipient=data.watcher).values_list("verb", flat=True)
    )
    assert {"issue.created", "milestone.completed"} <= verbs


def test_assignee_and_watcher_overlap_delivers_once(data):
    watch(data.member, SubscriptionTarget.TASK, data.task.pk)
    record_activity(
        data.project, data.pm, ActivityAction.TASK_STATUS, "Status berubah.", target=data.task
    )

    assert Notification.objects.filter(recipient=data.member, verb="task.status").count() == 1


def test_actor_never_receives_own_notification(data):
    watch(data.member, SubscriptionTarget.TASK, data.task.pk)
    record_activity(
        data.project, data.member, ActivityAction.TASK_STATUS, "Status berubah.", target=data.task
    )

    assert not Notification.objects.filter(recipient=data.member).exists()


def test_unwatch_endpoint_removes_subscription(client, data):
    watch(data.watcher, SubscriptionTarget.TASK, data.task.pk)
    client.force_login(data.watcher)
    response = client.post(reverse("notifications:unwatch_task", args=[data.task.pk]))
    assert response.status_code == 302
    assert not Subscription.objects.filter(
        user=data.watcher, target_type=SubscriptionTarget.TASK, target_id=data.task.pk
    ).exists()
