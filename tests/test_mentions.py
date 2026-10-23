from datetime import date

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.identity.models import Role
from apps.notifications.models import Notification
from apps.projects.models import Project
from apps.work.models import Mention, Task, TaskComment

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup_mentions(db):
    pm = User.objects.create_user("owner", password="valid-password")
    pm.pcc_profile.role = Role.PROJECT_MANAGER
    pm.pcc_profile.save()
    author = User.objects.create_user("author", password="valid-password")
    bob = User.objects.create_user("bob", password="valid-password")
    inactive = User.objects.create_user("sleepy", password="valid-password", is_active=False)
    stranger = User.objects.create_user("stranger", password="valid-password")
    project = Project.objects.create(
        name="Mention project",
        code="MENTION",
        manager=pm,
        start_date=date(2026, 10, 1),
        target_end_date=date(2026, 11, 1),
    )
    project.members.add(author, bob)
    task = Task.objects.create(project=project, title="Build", assignee=author)
    return {
        "pm": pm,
        "author": author,
        "bob": bob,
        "inactive": inactive,
        "stranger": stranger,
        "project": project,
        "task": task,
    }


def _comment(client, data, content):
    return client.post(
        reverse("work:task_detail", args=[data["task"].pk]),
        {"content": content},
    )


def _errors(response):
    return " ".join(response.context["comment_form"].errors["content"])


def test_valid_mention_creates_row_and_one_notification(client, setup_mentions):
    data = setup_mentions
    client.force_login(data["author"])
    response = _comment(client, data, "Halo @bob tolong cek task ini.")
    assert response.status_code == 302
    comment = data["task"].comments.get()
    mention = Mention.objects.get(task_comment=comment)
    assert mention.user == data["bob"]
    notification = Notification.objects.get(recipient=data["bob"])
    assert "Build" in notification.title
    assert notification.url == reverse("work:task_detail", args=[data["task"].pk])


def test_unknown_mention_rejects_the_whole_comment(client, setup_mentions):
    data = setup_mentions
    client.force_login(data["author"])
    response = _comment(client, data, "Halo @nobody")
    assert response.status_code == 200
    assert not TaskComment.objects.exists()
    assert "@nobody" in _errors(response)
    assert "@nobody" in response.context["comment_form"].errors["content"][0]


def test_inactive_user_is_rejected(client, setup_mentions):
    data = setup_mentions
    client.force_login(data["author"])
    response = _comment(client, data, "Halo @sleepy")
    assert response.status_code == 200
    assert not TaskComment.objects.exists()
    assert "tidak aktif" in _errors(response)


def test_user_without_project_access_is_rejected(client, setup_mentions):
    data = setup_mentions
    client.force_login(data["author"])
    response = _comment(client, data, "Halo @stranger")
    assert response.status_code == 200
    assert not TaskComment.objects.exists()
    assert "tidak punya akses" in _errors(response)


def test_duplicate_mentions_store_one_row_and_one_notification(client, setup_mentions):
    data = setup_mentions
    client.force_login(data["author"])
    assert _comment(client, data, "@bob @bob mohon dicek.").status_code == 302
    comment = data["task"].comments.get()
    assert Mention.objects.filter(task_comment=comment, user=data["bob"]).count() == 1
    assert Notification.objects.filter(recipient=data["bob"]).count() == 1


def test_mentioned_assignee_gets_one_notification(client, setup_mentions):
    data = setup_mentions
    data["task"].assignee = data["bob"]
    data["task"].save(update_fields=["assignee"])
    client.force_login(data["author"])
    assert _comment(client, data, "@bob statusnya bagaimana?").status_code == 302
    assert Notification.objects.filter(recipient=data["bob"]).count() == 1
    assert Mention.objects.filter(user=data["bob"]).count() == 1


def test_author_is_not_notified_for_own_mention(client, setup_mentions):
    data = setup_mentions
    client.force_login(data["author"])
    assert _comment(client, data, "Catatan saya @author").status_code == 302
    assert Mention.objects.filter(user=data["author"]).count() == 1
    assert Notification.objects.filter(recipient=data["author"]).count() == 0


def test_autocomplete_returns_only_visible_active_users(client, setup_mentions):
    data = setup_mentions
    client.force_login(data["author"])
    response = client.get(
        reverse("work:mention_suggest"),
        {"project": data["project"].pk, "q": "bo"},
    )
    assert response.status_code == 200
    assert response.json() == [{"username": "bob", "name": "bob"}]


def test_autocomplete_limits_results_to_eight(client, setup_mentions):
    data = setup_mentions
    for index in range(10):
        user = User.objects.create_user(f"member{index}", password="valid-password")
        data["project"].members.add(user)
    client.force_login(data["author"])
    response = client.get(
        reverse("work:mention_suggest"),
        {"project": data["project"].pk, "q": "member"},
    )
    assert response.status_code == 200
    assert len(response.json()) == 8


def test_autocomplete_rejects_invisible_project_and_requires_login(client, setup_mentions):
    data = setup_mentions
    url = reverse("work:mention_suggest")
    assert client.get(url, {"project": data["project"].pk}).status_code == 302
    client.force_login(data["stranger"])
    assert client.get(url, {"project": data["project"].pk}).status_code == 404
    client.force_login(data["author"])
    assert client.get(url, {"project": data["project"].pk}).status_code == 200
    assert client.get(url).status_code == 404
    assert client.get(url, {"project": "invalid"}).status_code == 404


def test_mentions_render_safely_without_html_injection(client, setup_mentions):
    data = setup_mentions
    TaskComment.objects.create(
        task=data["task"],
        author=data["author"],
        content='<script>alert(1)</script>Halo @bob <img src=x onerror=alert(2)>',
    )
    client.force_login(data["author"])
    response = client.get(reverse("work:task_detail", args=[data["task"].pk]))
    body = response.content.decode()
    assert "<script>" not in body
    assert "onerror" not in body
    assert '<strong class="mention">@bob</strong>' in body


def test_management_read_only_cannot_comment(client, setup_mentions):
    data = setup_mentions
    management = User.objects.create_user("management", password="valid-password")
    management.pcc_profile.role = Role.MANAGEMENT
    management.pcc_profile.save()
    client.force_login(management)
    response = _comment(client, data, "Halo @bob")
    assert response.status_code == 403
    assert not TaskComment.objects.exists()
