from datetime import date
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from apps.identity.models import Role
from apps.notifications.models import Notification, SubscriptionTarget
from apps.notifications.subscriptions import watch
from apps.projects.models import Milestone, Note, Project
from apps.work.models import Comment, CommentMention, Issue, Task

pytestmark = pytest.mark.django_db


@pytest.fixture
def data(db):
    pm = User.objects.create_user("owner", password="valid-password")
    pm.pcc_profile.role = Role.PROJECT_MANAGER
    pm.pcc_profile.save()
    member = User.objects.create_user("member", password="valid-password")
    watcher = User.objects.create_user("watcher", password="valid-password")
    management = User.objects.create_user("management", password="valid-password")
    management.pcc_profile.role = Role.MANAGEMENT
    management.pcc_profile.save()
    stranger = User.objects.create_user("stranger", password="valid-password")
    staff = User.objects.create_user("staff", password="valid-password", is_staff=True)

    project = Project.objects.create(
        name="Comment project",
        code="COMMENT",
        manager=pm,
        start_date=date(2026, 10, 1),
        target_end_date=date(2026, 11, 1),
    )
    project.members.add(member, watcher)
    other = Project.objects.create(
        name="Other project",
        code="OTHER",
        manager=pm,
        start_date=date(2026, 10, 1),
        target_end_date=date(2026, 11, 1),
    )
    task = Task.objects.create(project=project, title="Build", assignee=member, progress=40)
    issue = Issue.objects.create(project=project, title="Bug", owner=member)
    note = Note.objects.create(project=project, title="Kickoff", content="Notes")
    milestone = Milestone.objects.create(
        project=project, name="Beta", date=date(2026, 10, 20), owner=member
    )
    other_issue = Issue.objects.create(project=other, title="Other bug")
    return SimpleNamespace(
        pm=pm,
        member=member,
        watcher=watcher,
        management=management,
        stranger=stranger,
        staff=staff,
        project=project,
        other=other,
        task=task,
        issue=issue,
        note=note,
        milestone=milestone,
        other_issue=other_issue,
    )


def _post(client, data, target_type, target_id, content="Komentar baru.", **extra):
    payload = {
        "target_type": target_type,
        "target_id": target_id,
        "project": data.project.pk,
        "content": content,
        "next": reverse("projects:project_detail", args=[data.project.pk]),
    }
    payload.update(extra)
    return client.post(reverse("work:comment_create"), payload)


@pytest.mark.parametrize(
    "target_type,attr",
    [
        ("issue", "issue"),
        ("note", "note"),
        ("milestone", "milestone"),
        ("project", "project"),
    ],
)
def test_comment_creation_on_all_target_types(client, data, target_type, attr):
    target = getattr(data, attr)
    client.force_login(data.member)
    response = _post(client, data, target_type, target.pk)
    assert response.status_code == 302
    comment = Comment.objects.get(target_type=target_type, target_id=target.pk)
    assert comment.project == data.project
    assert comment.author == data.member
    assert comment.content == "Komentar baru."


def test_cross_project_target_is_rejected(client, data):
    client.force_login(data.member)
    response = _post(client, data, "issue", data.other_issue.pk)
    assert response.status_code == 404
    assert not Comment.objects.exists()


def test_invisible_project_is_rejected(client, data):
    client.force_login(data.stranger)
    response = _post(client, data, "issue", data.issue.pk)
    assert response.status_code == 404
    assert not Comment.objects.exists()


def test_management_read_only_cannot_comment(client, data):
    client.force_login(data.management)
    response = _post(client, data, "issue", data.issue.pk)
    assert response.status_code == 403
    assert not Comment.objects.exists()


@pytest.mark.parametrize("user_attr", ["member", "pm", "staff"])
def test_allowed_roles_can_comment(client, data, user_attr):
    client.force_login(getattr(data, user_attr))
    response = _post(client, data, "milestone", data.milestone.pk)
    assert response.status_code == 302
    assert Comment.objects.filter(target_type="milestone", target_id=data.milestone.pk).exists()


def test_comment_does_not_change_status_or_progress(client, data):
    issue_status = data.issue.status
    milestone_status = data.milestone.status
    project_status = data.project.status
    progress = data.task.progress
    client.force_login(data.member)
    assert _post(client, data, "issue", data.issue.pk).status_code == 302
    assert _post(client, data, "milestone", data.milestone.pk).status_code == 302
    assert _post(client, data, "project", data.project.pk).status_code == 302

    data.issue.refresh_from_db()
    data.milestone.refresh_from_db()
    data.project.refresh_from_db()
    data.task.refresh_from_db()
    assert data.issue.status == issue_status
    assert data.milestone.status == milestone_status
    assert data.project.status == project_status
    assert data.task.progress == progress


def test_unknown_mention_rejects_the_whole_comment(client, data):
    client.force_login(data.member)
    response = _post(client, data, "note", data.note.pk, content="Halo @nobody")
    assert response.status_code == 302
    assert not Comment.objects.exists()
    followed = client.get(response.url)
    assert "tidak ditemukan" in followed.content.decode()


def test_unauthorized_mention_rejects_the_whole_comment(client, data):
    client.force_login(data.member)
    response = _post(client, data, "note", data.note.pk, content="Halo @stranger")
    assert response.status_code == 302
    assert not Comment.objects.exists()
    followed = client.get(response.url)
    assert "tidak punya akses" in followed.content.decode()


def test_mention_creates_row_and_one_notification(client, data):
    client.force_login(data.member)
    assert _post(client, data, "note", data.note.pk, content="Halo @watcher").status_code == 302
    comment = Comment.objects.get(target_type="note", target_id=data.note.pk)
    assert CommentMention.objects.filter(comment=comment, user=data.watcher).count() == 1
    notification = Notification.objects.get(recipient=data.watcher)
    assert notification.target_type == "note"
    assert notification.target_id == data.note.pk
    assert notification.url.endswith(f"#comments-note-{data.note.pk}")
    assert Notification.objects.filter(recipient=data.member).count() == 0


def test_manager_and_watcher_are_notified_once(client, data):
    watch(data.watcher, SubscriptionTarget.PROJECT, data.project.pk)
    client.force_login(data.member)
    assert _post(client, data, "issue", data.issue.pk, content="Mohon dicek.").status_code == 302
    assert Notification.objects.filter(recipient=data.pm).count() == 1
    assert Notification.objects.filter(recipient=data.watcher).count() == 1
    assert Notification.objects.filter(recipient=data.member).count() == 0
    assert Notification.objects.filter(recipient=data.management).count() == 0


def test_duplicate_mention_and_watcher_get_one_notification(client, data):
    watch(data.watcher, SubscriptionTarget.PROJECT, data.project.pk)
    client.force_login(data.member)
    response = _post(client, data, "issue", data.issue.pk, content="@watcher @watcher cek.")
    assert response.status_code == 302
    assert CommentMention.objects.filter(user=data.watcher).count() == 1
    assert Notification.objects.filter(recipient=data.watcher).count() == 1


def test_comments_render_safely_with_mentions(client, data):
    Comment.objects.create(
        project=data.project,
        target_type="note",
        target_id=data.note.pk,
        author=data.member,
        content='<script>alert(1)</script>Halo @watcher <img src=x onerror=alert(2)>',
    )
    client.force_login(data.member)
    body = client.get(reverse("projects:project_notes", args=[data.project.pk])).content.decode()
    assert "<script>" not in body
    assert "onerror" not in body
    assert '<strong class="mention">@watcher</strong>' in body


def test_threads_render_on_every_target_page(client, data):
    for target_type, target_id in (
        ("issue", data.issue.pk),
        ("note", data.note.pk),
        ("milestone", data.milestone.pk),
        ("project", data.project.pk),
    ):
        Comment.objects.create(
            project=data.project,
            target_type=target_type,
            target_id=target_id,
            author=data.member,
            content=f"Komentar {target_type}",
        )
    client.force_login(data.member)
    pages = [
        (reverse("work:issue_update", args=[data.issue.pk]), "Diskusi issue", "Komentar issue"),
        (
            reverse("projects:project_notes", args=[data.project.pk]),
            "Komentar catatan",
            "Komentar note",
        ),
        (
            reverse("projects:project_milestones", args=[data.project.pk]),
            "Komentar milestone",
            "Komentar milestone",
        ),
        (
            reverse("projects:project_detail", args=[data.project.pk]),
            "Diskusi project",
            "Komentar project",
        ),
    ]
    for url, heading, content in pages:
        body = client.get(url).content.decode()
        assert heading in body
        assert content in body

    client.force_login(data.pm)
    manager_form = client.get(reverse("work:issue_update", args=[data.issue.pk]))
    assert manager_form.status_code == 200
    assert "Diskusi issue" in manager_form.content.decode()


def test_issue_thread_paginates(client, data):
    for index in range(25):
        Comment.objects.create(
            project=data.project,
            target_type="issue",
            target_id=data.issue.pk,
            author=data.member,
            content=f"Komentar {index}",
        )
    client.force_login(data.member)
    url = reverse("work:issue_update", args=[data.issue.pk])
    first = client.get(url)
    assert first.status_code == 200
    assert first.context["comments_page"].paginator.count == 25
    assert len(first.context["comments"]) == 20
    second = client.get(url, {"page": 2})
    assert len(second.context["comments"]) == 5


def test_note_thread_shows_latest_count(client, data):
    for index in range(25):
        Comment.objects.create(
            project=data.project,
            target_type="note",
            target_id=data.note.pk,
            author=data.member,
            content=f"Komentar {index}",
        )
    client.force_login(data.member)
    body = client.get(reverse("projects:project_notes", args=[data.project.pk])).content.decode()
    assert "Menampilkan 20 komentar terbaru dari 25." in body


def test_comment_endpoint_is_post_only_and_csrf_protected(client, data):
    url = reverse("work:comment_create")
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(data.member)
    assert csrf_client.get(url).status_code == 405
    response = csrf_client.post(
        url,
        {
            "target_type": "issue",
            "target_id": data.issue.pk,
            "project": data.project.pk,
            "content": "Halo",
        },
    )
    assert response.status_code == 403
    assert not Comment.objects.exists()


def test_unsafe_next_is_ignored(client, data):
    client.force_login(data.member)
    response = _post(
        client, data, "issue", data.issue.pk, next="https://evil.example/steal"
    )
    assert response.status_code == 302
    assert "evil.example" not in response.url
    assert Comment.objects.count() == 1
