from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.identity.models import Role
from apps.projects.models import ActivityAction, ActivityEvent, Project
from apps.work.models import Priority, Task, TaskStatus

pytestmark = pytest.mark.django_db

TODAY = date(2026, 10, 10)


@pytest.fixture
def workspace(db):
    pm = User.objects.create_user("owner", password="valid-password")
    pm.pcc_profile.role = Role.PROJECT_MANAGER
    pm.pcc_profile.save()
    member = User.objects.create_user("member", password="valid-password")
    viewer = User.objects.create_user("viewer", password="valid-password")
    stranger = User.objects.create_user("stranger", password="valid-password")
    management = User.objects.create_user("management", password="valid-password")
    management.pcc_profile.role = Role.MANAGEMENT
    management.pcc_profile.save()

    project = Project.objects.create(
        name="Alpha project",
        code="ALPHA",
        manager=pm,
        start_date=date(2026, 10, 1),
        target_end_date=date(2026, 12, 1),
    )
    project.members.add(member, viewer)
    other = Project.objects.create(
        name="Beta project",
        code="BETA",
        manager=pm,
        start_date=date(2026, 10, 1),
        target_end_date=date(2026, 12, 1),
    )
    return {
        "pm": pm,
        "member": member,
        "viewer": viewer,
        "stranger": stranger,
        "management": management,
        "project": project,
        "other": other,
    }


@pytest.fixture
def buckets(workspace, monkeypatch):
    monkeypatch.setattr("django.utils.timezone.localdate", lambda: TODAY)
    member = workspace["member"]
    project = workspace["project"]
    tasks = {
        "overdue": Task.objects.create(
            project=project,
            title="Overdue work",
            assignee=member,
            due_date=TODAY - timedelta(days=1),
            status=TaskStatus.TODO,
        ),
        "today": Task.objects.create(
            project=project,
            title="Due today work",
            assignee=member,
            due_date=TODAY,
            status=TaskStatus.IN_PROGRESS,
        ),
        "plus7": Task.objects.create(
            project=project,
            title="Due in seven days",
            assignee=member,
            due_date=TODAY + timedelta(days=7),
            status=TaskStatus.REVIEW,
        ),
        "plus8": Task.objects.create(
            project=project,
            title="Due in eight days",
            assignee=member,
            due_date=TODAY + timedelta(days=8),
            status=TaskStatus.TODO,
            priority=Priority.HIGH,
        ),
        "undated": Task.objects.create(
            project=project,
            title="No target work",
            assignee=member,
            status=TaskStatus.BACKLOG,
        ),
        "done": Task.objects.create(
            project=project,
            title="Finished overdue work",
            assignee=member,
            due_date=TODAY - timedelta(days=5),
            status=TaskStatus.DONE,
        ),
    }
    return tasks


def _ids(tasks):
    return [task.pk for task in tasks]


def test_my_tasks_partitions_due_buckets_without_duplicates(client, workspace, buckets):
    client.force_login(workspace["member"])
    response = client.get(reverse("work:my_tasks"))
    assert response.status_code == 200
    context = response.context

    assert _ids(context["bucket_overdue"]) == [buckets["overdue"].pk]
    assert _ids(context["bucket_soon"]) == [buckets["today"].pk, buckets["plus7"].pk]
    assert _ids(context["bucket_undated"]) == [buckets["undated"].pk]
    assert buckets["plus8"] in context["bucket_next"]
    assert buckets["done"] in context["done"]

    rendered = (
        context["bucket_overdue"]
        + context["bucket_soon"]
        + context["bucket_undated"]
        + context["bucket_blocked"]
        + context["bucket_current"]
        + context["bucket_review"]
        + context["bucket_next"]
        + context["done"]
    )
    ids = _ids(rendered)
    assert len(ids) == len(set(ids))

    content = response.content
    assert b"Terlambat" in content
    assert b"Jatuh tempo 7 hari" in content
    assert b"Tanpa target" in content


def test_due_buckets_sort_by_target_then_priority(client, workspace, monkeypatch):
    monkeypatch.setattr("django.utils.timezone.localdate", lambda: TODAY)
    member = workspace["member"]
    project = workspace["project"]
    low = Task.objects.create(
        project=project,
        title="Low later",
        assignee=member,
        due_date=TODAY + timedelta(days=1),
        priority=Priority.LOW,
    )
    critical = Task.objects.create(
        project=project,
        title="Critical later",
        assignee=member,
        due_date=TODAY + timedelta(days=1),
        priority=Priority.CRITICAL,
    )
    client.force_login(member)
    response = client.get(reverse("work:my_tasks"))
    assert _ids(response.context["bucket_soon"]) == [critical.pk, low.pk]


def test_due_filters_and_counts(client, workspace, buckets):
    client.force_login(workspace["member"])
    url = reverse("work:my_tasks")

    response = client.get(url)
    assert response.context["due_counts"] == {"all": 6, "overdue": 1, "soon": 2, "none": 1}

    response = client.get(url, {"due": "overdue"})
    assert _ids(response.context["bucket_overdue"]) == [buckets["overdue"].pk]
    assert response.context["bucket_soon"] == []
    assert response.context["due_filter"] == "overdue"

    response = client.get(url, {"due": "soon"})
    assert _ids(response.context["bucket_soon"]) == [
        buckets["today"].pk,
        buckets["plus7"].pk,
    ]
    assert response.context["bucket_overdue"] == []

    response = client.get(url, {"due": "none"})
    assert _ids(response.context["bucket_undated"]) == [buckets["undated"].pk]
    assert response.context["bucket_soon"] == []

    response = client.get(url, {"due": "unknown"})
    assert response.context["due_filter"] == "all"


def test_filters_combine_and_stay_in_url(client, workspace, buckets):
    client.force_login(workspace["member"])
    url = reverse("work:my_tasks")
    response = client.get(
        url,
        {"q": "seven", "project": workspace["project"].pk, "status": "review", "due": "soon"},
    )
    assert response.status_code == 200
    context = response.context
    assert context["query"] == "seven"
    assert context["selected_project"] == workspace["project"]
    assert context["status_filter"] == "review"
    assert context["due_filter"] == "soon"
    assert _ids(context["bucket_soon"]) == [buckets["plus7"].pk]

    content = response.content
    assert b"due=soon" in content
    assert b"project=" + str(workspace["project"].pk).encode() in content
    assert b"status=review" in content
    assert b"q=seven" in content

    response = client.get(url, {"q": "nothing matches"})
    assert response.context["open_count"] == 0
    assert b"Reset filter" in response.content


def test_grouping_by_project_uses_project_name_and_count(client, workspace, buckets):
    other_task = Task.objects.create(
        project=workspace["other"],
        title="Beta work",
        assignee=workspace["member"],
        due_date=TODAY + timedelta(days=20),
    )
    client.force_login(workspace["member"])
    response = client.get(reverse("work:my_tasks"), {"group": "project"})
    assert response.status_code == 200
    groups = response.context["project_groups"]
    assert [group["project"].code for group in groups] == ["ALPHA", "BETA"]
    by_code = {group["project"].code: group for group in groups}
    assert by_code["ALPHA"]["count"] == 5
    assert other_task in by_code["BETA"]["tasks"]
    assert b"Alpha project" in response.content and b"BETA" in response.content
    assert b"group=project" in response.content


def test_my_tasks_scope_does_not_leak_foreign_projects(client, workspace, buckets):
    stranger_task = Task.objects.create(
        project=workspace["project"],
        title="Stranger task",
        assignee=workspace["member"],
    )
    client.force_login(workspace["stranger"])
    response = client.get(reverse("work:my_tasks"))
    assert response.status_code == 200
    assert stranger_task not in response.context["bucket_undated"]
    assert b"Stranger task" not in response.content

    response = client.get(reverse("work:my_tasks"), {"project": workspace["project"].pk})
    assert response.status_code == 404


def test_quick_update_controls_only_render_for_editable_tasks(client, workspace):
    project = workspace["project"]
    editable = Task.objects.create(
        project=project, title="Editable task", assignee=workspace["member"]
    )
    managed_task = Task.objects.create(
        project=project, title="Managed task", assignee=workspace["management"]
    )

    client.force_login(workspace["member"])
    content = client.get(reverse("work:my_tasks")).content
    assert b"data-quick-update" in content
    assert b"data-quick-status" in content
    assert b"data-quick-progress" in content
    assert f'data-task-id="{editable.pk}"'.encode() in content

    client.force_login(workspace["management"])
    content = client.get(reverse("work:my_tasks")).content
    assert b"Managed task" in content
    assert b"data-quick-update" not in content
    assert f'data-task-id="{managed_task.pk}"'.encode() not in content


def test_quick_update_disables_progress_when_task_has_details(client, workspace):
    parent = Task.objects.create(
        project=workspace["project"], title="Parent activity", assignee=workspace["member"]
    )
    Task.objects.create(
        project=workspace["project"],
        title="Child detail",
        parent_task=parent,
        assignee=workspace["member"],
    )
    client.force_login(workspace["member"])
    content = client.get(reverse("work:my_tasks")).content
    assert b"Progress mengikuti detail activity." in content
    assert f'id="quick-progress-{parent.pk}"'.encode() in content
    assert b'data-locked="true"' in content


def test_project_tasks_board_renders_quick_update_for_editable_cards(client, workspace):
    task = Task.objects.create(
        project=workspace["project"], title="Board task", assignee=workspace["member"]
    )
    url = reverse("projects:project_tasks", args=[workspace["project"].pk])

    client.force_login(workspace["member"])
    content = client.get(url).content
    assert content.count(b"data-quick-update") == 1
    assert content.count(b"data-quick-progress") == 1
    assert f'data-task-id="{task.pk}"'.encode() in content
    assert b"data-status-select" in content

    client.force_login(workspace["management"])
    content = client.get(url).content
    assert b"Board task" in content
    assert b"data-quick-update" not in content


def test_status_endpoint_enforces_permissions_and_dependencies(client, workspace):
    task = Task.objects.create(
        project=workspace["project"], title="Gated task", assignee=workspace["member"]
    )
    dependency = Task.objects.create(project=workspace["project"], title="Prerequisite")
    task.dependencies.add(dependency)
    url = reverse("work:task_status", args=[task.pk])

    client.force_login(workspace["viewer"])
    response = client.post(url, {"status": "in_progress"})
    assert response.status_code == 403

    client.force_login(workspace["member"])
    response = client.post(url, {"status": "in_progress"})
    assert response.status_code == 400
    assert b"Selesaikan dependency" in response.content

    dependency.status = TaskStatus.DONE
    dependency.save()
    response = client.post(url, {"status": "in_progress"})
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"

    client.force_login(workspace["stranger"])
    assert client.post(url, {"status": "todo"}).status_code == 404


def test_progress_endpoint_enforces_details_and_range(client, workspace):
    simple = Task.objects.create(
        project=workspace["project"], title="Simple task", assignee=workspace["member"]
    )
    parent = Task.objects.create(
        project=workspace["project"], title="Rolled up task", assignee=workspace["member"]
    )
    Task.objects.create(
        project=workspace["project"],
        title="Detail",
        parent_task=parent,
        assignee=workspace["member"],
    )
    client.force_login(workspace["member"])

    url = reverse("work:task_progress", args=[simple.pk])
    assert client.post(url, {"progress": "150"}).status_code == 400
    response = client.post(url, {"progress": "45"})
    assert response.status_code == 200
    assert response.json()["progress"] == 45.0

    rolled_up = reverse("work:task_progress", args=[parent.pk])
    response = client.post(rolled_up, {"progress": "50"})
    assert response.status_code == 400
    assert b"dihitung otomatis" in response.content

    assert client.post(rolled_up, {"progress": "50"}).status_code == 400
    client.force_login(workspace["stranger"])
    assert client.post(url, {"progress": "10"}).status_code == 404


def test_quick_updates_create_one_activity_event_each(client, workspace):
    task = Task.objects.create(
        project=workspace["project"], title="Tracked task", assignee=workspace["member"]
    )
    client.force_login(workspace["member"])
    before = ActivityEvent.objects.filter(project=workspace["project"]).count()

    client.post(reverse("work:task_status", args=[task.pk]), {"status": "in_progress"})
    client.post(reverse("work:task_progress", args=[task.pk]), {"progress": "30"})

    events = ActivityEvent.objects.filter(project=workspace["project"])
    assert events.count() == before + 2
    assert events.filter(action=ActivityAction.TASK_STATUS).count() == 1
    assert events.filter(action=ActivityAction.PROGRESS_UPDATED).count() == 1
