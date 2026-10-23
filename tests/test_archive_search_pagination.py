from datetime import date

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.identity.models import Role
from apps.projects.models import ActivityEvent, Decision, Milestone, Note, Phase, Project
from apps.work.models import Issue, Task, TaskComment

pytestmark = pytest.mark.django_db


@pytest.fixture
def workspace(db):
    pm = User.objects.create_user("owner", password="valid-password")
    pm.pcc_profile.role = Role.PROJECT_MANAGER
    pm.pcc_profile.save()
    member = User.objects.create_user("member", password="valid-password")
    stranger = User.objects.create_user("stranger", password="valid-password")
    project = Project.objects.create(
        name="Alpha project",
        code="ALPHA",
        manager=pm,
        start_date=date(2026, 10, 1),
        target_end_date=date(2026, 11, 1),
    )
    project.members.add(member)
    task = Task.objects.create(
        project=project,
        title="Build zebra engine",
        assignee=member,
        start_date=date(2026, 10, 2),
        due_date=date(2026, 10, 10),
    )
    return {
        "pm": pm,
        "member": member,
        "stranger": stranger,
        "project": project,
        "task": task,
    }


def _create_projects(pm, count):
    for index in range(count):
        Project.objects.create(
            name=f"Paged project {index:02d}",
            code=f"PAGE-{index:02d}",
            manager=pm,
            start_date=date(2026, 10, 1),
            target_end_date=date(2026, 11, 1),
        )


def test_project_list_paginates_and_keeps_filters(client, workspace):
    _create_projects(workspace["pm"], 23)
    client.force_login(workspace["pm"])
    response = client.get(reverse("projects:project_list"), {"page": 2})
    assert response.status_code == 200
    assert response.context["page_obj"].number == 2
    assert response.context["total_rows"] == 24
    assert len(response.context["rows"]) == 4

    filtered = client.get(reverse("projects:project_list"), {"q": "Paged", "page": 2})
    assert filtered.context["page_obj"].number == 2
    assert b"page=1" in filtered.content or b"page=3" in filtered.content


def test_note_list_paginates(client, workspace):
    for index in range(25):
        Note.objects.create(
            project=workspace["project"],
            title=f"Note {index:02d}",
            content="Isi catatan",
            author=workspace["pm"],
        )
    client.force_login(workspace["pm"])
    response = client.get(reverse("projects:note_list"), {"page": 2})
    assert response.status_code == 200
    assert response.context["page_obj"].number == 2
    assert len(response.context["notes"]) == 1


def test_issue_list_paginates(client, workspace):
    for index in range(30):
        Issue.objects.create(
            project=workspace["project"],
            title=f"Issue {index:02d}",
            owner=workspace["pm"],
        )
    client.force_login(workspace["pm"])
    response = client.get(reverse("work:issue_list"), {"page": 2})
    assert response.status_code == 200
    assert response.context["page_obj"].number == 2
    assert len(response.context["issues"]) == 5


def test_activity_and_comments_paginate(client, workspace):
    project = workspace["project"]
    for index in range(35):
        ActivityEvent.objects.create(
            project=project,
            actor=workspace["pm"],
            action="project.updated",
            message=f"Event {index:02d}",
        )
    task = workspace["task"]
    for index in range(25):
        TaskComment.objects.create(task=task, author=workspace["pm"], content=f"Comment {index}")

    client.force_login(workspace["pm"])
    activity = client.get(reverse("projects:project_activity", args=[project.pk]), {"page": 2})
    assert activity.context["page_obj"].number == 2
    assert len(activity.context["activities"]) == 5

    detail = client.get(reverse("work:task_detail", args=[task.pk]), {"page": 2})
    assert detail.context["comments_page"].number == 2
    assert len(detail.context["comments"]) == 5


def test_task_archive_hides_from_board_my_tasks_and_search(client, workspace):
    task = workspace["task"]
    client.force_login(workspace["pm"])
    response = client.post(reverse("work:task_archive", args=[task.pk]))
    assert response.status_code == 302
    task.refresh_from_db()
    assert task.archived_at is not None
    assert not Task.objects.filter(pk=task.pk).exists()

    board = client.get(reverse("projects:project_tasks", args=[task.project_id]))
    assert f'data-task-id="{task.pk}"'.encode() not in board.content
    assert b"Pekerjaan diarsipkan" in board.content
    client.force_login(workspace["member"])
    assert b"Build zebra engine" not in client.get(reverse("work:my_tasks")).content
    assert b"Build zebra engine" not in client.get(
        reverse("projects:nav_search"), {"q": "zebra"}
    ).content

    client.force_login(workspace["pm"])
    restored = client.post(reverse("work:task_restore", args=[task.pk]))
    assert restored.status_code == 302
    task.refresh_from_db()
    assert task.archived_at is None
    assert f'data-task-id="{task.pk}"'.encode() in client.get(
        reverse("projects:project_tasks", args=[task.project_id])
    ).content


def test_task_archive_cascades_to_details(client, workspace):
    parent = workspace["task"]
    child = Task.objects.create(
        project=workspace["project"],
        parent_task=parent,
        title="Detail zebra",
        assignee=workspace["member"],
    )
    client.force_login(workspace["pm"])
    client.post(reverse("work:task_archive", args=[parent.pk]))
    assert Task.all_objects.get(pk=parent.pk).archived_at is not None
    assert Task.all_objects.get(pk=child.pk).archived_at is not None

    client.post(reverse("work:task_restore", args=[parent.pk]))
    assert Task.all_objects.get(pk=parent.pk).archived_at is None
    assert Task.all_objects.get(pk=child.pk).archived_at is None


def test_project_archive_hides_from_active_views_and_public_link(client, workspace):
    project = workspace["project"]
    project.is_public = True
    project.save()
    public_url = reverse("projects:public_project", args=[project.public_token])
    assert client.get(public_url).status_code == 200

    client.force_login(workspace["pm"])
    assert client.post(reverse("projects:project_archive", args=[project.pk])).status_code == 302
    project.refresh_from_db()
    assert project.archived_at is not None
    assert not Project.objects.filter(pk=project.pk).exists()

    assert b"Alpha project" not in client.get(reverse("projects:project_list")).content
    assert b"Alpha project" in client.get(
        reverse("projects:project_list"), {"archived": 1}
    ).content
    assert b"Alpha project" not in client.get(reverse("projects:dashboard")).content
    assert b"Alpha project" not in client.get(
        reverse("projects:search"), {"q": "Alpha"}
    ).content
    assert client.get(public_url).status_code == 404

    client.post(reverse("projects:project_restore", args=[project.pk]))
    project.refresh_from_db()
    assert project.archived_at is None
    assert b"Alpha project" in client.get(reverse("projects:project_list")).content
    assert client.get(public_url).status_code == 200


def test_member_cannot_archive(client, workspace):
    client.force_login(workspace["member"])
    assert client.post(reverse("work:task_archive", args=[workspace["task"].pk])).status_code == 403
    assert (
        client.post(reverse("projects:project_archive", args=[workspace["project"].pk])).status_code
        == 403
    )


def test_issue_archive_and_restore(client, workspace):
    issue = Issue.objects.create(
        project=workspace["project"], title="Zebra blocker", owner=workspace["pm"]
    )
    client.force_login(workspace["pm"])
    client.post(reverse("work:issue_archive", args=[issue.pk]))
    issue.refresh_from_db()
    assert issue.archived_at is not None
    page = client.get(reverse("projects:project_issues", args=[workspace["project"].pk]))
    assert b"Zebra blocker" in page.content
    assert [item.pk for item in page.context["archived_issues"]] == [issue.pk]

    client.post(reverse("work:issue_restore", args=[issue.pk]))
    issue.refresh_from_db()
    assert issue.archived_at is None


def test_restoring_task_from_archived_phase_clears_phase(client, workspace):
    project = workspace["project"]
    phase = Phase.objects.create(project=project, name="Phase arsip", sequence=2)
    task = workspace["task"]
    task.phase = phase
    task.save()
    client.force_login(workspace["pm"])
    client.post(reverse("projects:phase_archive", args=[project.pk, phase.pk]))
    client.post(reverse("work:task_restore", args=[task.pk]))
    task.refresh_from_db()
    assert task.archived_at is None
    assert task.phase_id is None


def test_phase_restore_rejects_sequence_collision(client, workspace):
    project = workspace["project"]
    phase = Phase.objects.create(project=project, name="Phase lama", sequence=3)
    client.force_login(workspace["pm"])
    client.post(reverse("projects:phase_archive", args=[project.pk, phase.pk]))
    Phase.objects.create(project=project, name="Phase baru", sequence=3)

    response = client.post(
        reverse("projects:phase_restore", args=[project.pk, phase.pk]), follow=True
    )
    phase.refresh_from_db()
    assert phase.archived_at is not None
    assert b"Urutan phase ini sudah dipakai" in response.content


def test_phase_archive_cascades_and_clears_current_phase(client, workspace):
    project = workspace["project"]
    phase = Phase.objects.create(project=project, name="Phase zebra", sequence=1)
    task = workspace["task"]
    task.phase = phase
    task.save()
    project.current_phase = phase
    project.save()

    client.force_login(workspace["pm"])
    client.post(reverse("projects:phase_archive", args=[project.pk, phase.pk]))
    phase.refresh_from_db()
    project.refresh_from_db()
    task.refresh_from_db()
    assert phase.archived_at is not None
    assert project.current_phase_id is None
    assert task.archived_at is not None

    timeline = client.get(reverse("projects:project_timeline", args=[project.pk]))
    assert [item.pk for item in timeline.context["archived_phases"]] == [phase.pk]
    assert list(timeline.context["phases"]) == []

    client.post(reverse("projects:phase_restore", args=[project.pk, phase.pk]))
    phase.refresh_from_db()
    task.refresh_from_db()
    assert phase.archived_at is None
    assert task.archived_at is None


def test_search_covers_all_entities(client, workspace):
    project = workspace["project"]
    project.name = "Alpha zebra project"
    project.save()
    Issue.objects.create(project=project, title="Zebra issue", owner=workspace["pm"])
    Note.objects.create(project=project, title="Zebra note", content="Isi zebra")
    Milestone.objects.create(project=project, name="Zebra milestone", date=date(2026, 10, 20))
    Decision.objects.create(project=project, title="Zebra decision", decision="Pakai zebra")

    client.force_login(workspace["pm"])
    suggest = client.get(reverse("projects:nav_search"), {"q": "zebra"})
    assert suggest.status_code == 200
    for text in ("Alpha zebra project", "Build zebra engine", "Zebra issue", "Zebra note"):
        assert text.encode() in suggest.content
    assert b"Zebra milestone" in suggest.content
    assert b"Zebra decision" in suggest.content
    assert b"Lihat semua hasil" in suggest.content

    results = client.get(reverse("projects:search"), {"q": "zebra"})
    for text in (
        "Alpha zebra project",
        "Build zebra engine",
        "Zebra issue",
        "Zebra note",
        "Zebra milestone",
        "Zebra decision",
    ):
        assert text.encode() in results.content


def test_search_respects_project_visibility(client, workspace):
    other_pm = User.objects.create_user("other", password="valid-password")
    other_pm.pcc_profile.role = Role.PROJECT_MANAGER
    other_pm.pcc_profile.save()
    other = Project.objects.create(
        name="Private zebra",
        code="PRIVATE-Z",
        manager=other_pm,
        start_date=date(2026, 10, 1),
        target_end_date=date(2026, 11, 1),
    )
    Task.objects.create(project=other, title="Private zebra task", assignee=other_pm)
    Note.objects.create(project=other, title="Private zebra note", content="Rahasia")

    client.force_login(workspace["member"])
    for url_name in ("projects:nav_search", "projects:search"):
        response = client.get(reverse(url_name), {"q": "Private zebra"})
        assert response.status_code == 200
        assert response.context["total"] == 0
        assert b"Private zebra task" not in response.content
        assert b"Private zebra note" not in response.content


def test_search_excludes_archived_rows(client, workspace):
    task = workspace["task"]
    client.force_login(workspace["pm"])
    client.post(reverse("work:task_archive", args=[task.pk]))
    response = client.get(reverse("projects:search"), {"q": "zebra"})
    assert b"Build zebra engine" not in response.content
    assert b"Alpha project" in client.get(
        reverse("projects:search"), {"q": "Alpha"}
    ).content


def test_search_empty_query(client, workspace):
    client.force_login(workspace["pm"])
    response = client.get(reverse("projects:search"))
    assert response.status_code == 200
    assert b"Masukkan kata kunci" in response.content
