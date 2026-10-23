from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.identity.models import Role
from apps.projects.models import ActivityEvent, Project, Revision
from apps.work.models import Task

pytestmark = pytest.mark.django_db


def _user(username, role=None):
    user = User.objects.create_user(username, password="test-password")
    if role is not None:
        user.pcc_profile.role = role
        user.pcc_profile.save()
    return user


@pytest.fixture
def workspace():
    pm = _user("history-pm", Role.PROJECT_MANAGER)
    member = _user("history-member")
    management = _user("history-management", Role.MANAGEMENT)
    project = Project.objects.create(
        name="History project",
        code="HIST",
        manager=pm,
        start_date=date(2026, 10, 1),
        target_end_date=date(2026, 11, 30),
    )
    project.members.add(member)
    task = Task.objects.create(
        project=project,
        title="Login module",
        assignee=member,
        status="todo",
        progress=Decimal("20"),
        start_date=date(2026, 10, 5),
        due_date=date(2026, 10, 20),
    )
    return {
        "pm": pm,
        "member": member,
        "management": management,
        "project": project,
        "task": task,
    }


def _task_revisions(task):
    return Revision.objects.filter(entity="task", object_id=task.pk)


def test_creation_records_created_revision(workspace):
    revision = _task_revisions(workspace["task"]).get(action="created")
    assert revision.project == workspace["project"]
    assert revision.object_repr == 'Task "Login module"'
    assert revision.changes == {}


def test_change_records_revision_with_field_diff(workspace):
    task = workspace["task"]
    before = _task_revisions(task).count()

    task.start_date = date(2026, 10, 6)
    task.status = "in_progress"
    task.progress = Decimal("40")
    task.assignee = workspace["pm"]
    task.save()

    assert _task_revisions(task).count() == before + 1
    revision = _task_revisions(task).latest("id")
    assert revision.action == "updated"
    assert revision.project == workspace["project"]
    assert revision.changes["start_date"] == {"old": "2026-10-05", "new": "2026-10-06"}
    assert revision.changes["status"] == {"old": "todo", "new": "in_progress"}
    assert Decimal(revision.changes["progress"]["new"]) == Decimal("40")
    assert revision.changes["assignee"] == {
        "old": workspace["member"].pk,
        "new": workspace["pm"].pk,
    }


def test_noop_save_does_not_create_revision(workspace):
    task = workspace["task"]
    before = _task_revisions(task).count()

    task.save()
    task.save(update_fields=["updated_at"])

    assert _task_revisions(task).count() == before


def test_member_update_is_merged_into_one_revision_per_request(client, workspace):
    project = workspace["project"]
    extra = _user("history-extra")
    client.force_login(workspace["pm"])
    before = Revision.objects.filter(entity="project", object_id=project.pk).count()

    response = client.post(
        reverse("projects:project_members", args=[project.pk]),
        {"members": [workspace["member"].pk, extra.pk]},
    )

    assert response.status_code == 302
    revisions = Revision.objects.filter(entity="project", object_id=project.pk)
    assert revisions.count() == before + 1
    revision = revisions.latest("id")
    assert revision.changes["members"] == {
        "old": [workspace["member"].pk],
        "new": sorted([workspace["member"].pk, extra.pk]),
    }


def test_project_history_page_renders_diff_newest_first(client, workspace):
    task = workspace["task"]
    client.force_login(workspace["pm"])
    task.status = "done"
    task.progress = Decimal("100")
    task.save()

    response = client.get(reverse("projects:project_history", args=[workspace["project"].pk]))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Riwayat perubahan" in content
    assert "Login module" in content
    assert "Status" in content
    assert "Selesai" in content
    assert "Sebelum" in content
    revisions = response.context["revisions"]
    timestamps = [revision.created_at for revision in revisions]
    assert timestamps == sorted(timestamps, reverse=True)
    assert revisions[0].object_repr == 'Task "Login module"'


def test_restore_task_fields_creates_revision_and_activity(client, workspace):
    task = workspace["task"]
    client.force_login(workspace["pm"])

    task.start_date = date(2026, 10, 9)
    task.due_date = date(2026, 11, 2)
    task.status = "done"
    task.progress = Decimal("100")
    task.assignee = workspace["pm"]
    task.save()

    revision = _task_revisions(task).latest("id")
    response = client.post(
        reverse(
            "projects:project_history_restore",
            args=[workspace["project"].pk, revision.pk],
        )
    )
    assert response.status_code == 302

    task.refresh_from_db()
    assert task.start_date == date(2026, 10, 5)
    assert task.due_date == date(2026, 10, 20)
    assert task.status == "todo"
    assert task.progress == Decimal("20.00")
    assert task.assignee_id == workspace["member"].pk

    restored = _task_revisions(task).filter(action="restored").latest("id")
    assert restored.changes["status"] == {"old": "done", "new": "todo"}
    assert restored.changes["start_date"] == {"old": "2026-10-09", "new": "2026-10-05"}
    assert ActivityEvent.objects.filter(
        project=workspace["project"], action="history.restored"
    ).exists()


def test_member_and_management_cannot_restore(client, workspace):
    task = workspace["task"]
    task.progress = Decimal("90")
    task.save()
    revision = _task_revisions(task).latest("id")
    url = reverse(
        "projects:project_history_restore",
        args=[workspace["project"].pk, revision.pk],
    )

    client.force_login(workspace["member"])
    assert client.post(url).status_code == 403
    client.force_login(workspace["management"])
    assert client.post(url).status_code == 403

    task.refresh_from_db()
    assert task.progress == Decimal("90.00")
    assert not _task_revisions(task).filter(action="restored").exists()


def test_history_is_hidden_for_projects_outside_the_visible_scope(client, workspace):
    stranger = _user("history-stranger")
    client.force_login(stranger)
    response = client.get(reverse("projects:project_history", args=[workspace["project"].pk]))
    assert response.status_code == 404
