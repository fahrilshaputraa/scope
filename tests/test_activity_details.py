from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.identity.models import Role
from apps.projects.models import Phase, Project
from apps.projects.services import actual_progress, timeline_data
from apps.work.forms import TaskForm
from apps.work.models import Task

pytestmark = pytest.mark.django_db


@pytest.fixture
def activity():
    pm = User.objects.create_user("activity-pm", password="test-password")
    pm.pcc_profile.role = Role.PROJECT_MANAGER
    pm.pcc_profile.save()
    project = Project.objects.create(
        name="Activity project",
        code="ACT",
        manager=pm,
        start_date=date(2026, 10, 1),
        target_end_date=date(2026, 11, 1),
    )
    phase = Phase.objects.create(project=project, name="Development")
    return Task.objects.create(
        project=project,
        phase=phase,
        title="Login module",
        progress=80,
        weight=4,
        start_date=date(2026, 10, 5),
        due_date=date(2026, 10, 20),
    )


def detail(activity, **kwargs):
    return Task.objects.create(
        project=activity.project, parent_task=activity, title="Login API", **kwargs
    )


def test_weighted_details_roll_up_without_double_counting(activity):
    detail(activity, status="done", weight=1)
    child = detail(activity, progress=20, weight=3)
    Task.objects.create(project=activity.project, phase=activity.phase, title="Other", weight=1)
    assert activity.display_progress == Decimal("40.00")
    assert actual_progress(activity.project) == Decimal("32.00")
    assert activity.phase.progress == Decimal("32.00")
    child.progress = 60
    child.save()
    assert activity.display_progress == Decimal("70.00")
    assert actual_progress(activity.project) == Decimal("56.00")


def test_optional_details_and_zero_total_weight(activity):
    assert activity.display_progress == 80
    detail(activity, progress=90, weight=0)
    assert activity.display_progress == Decimal("0.00")
    assert actual_progress(activity.project) == Decimal("0.00")


def test_detail_inherits_phase_and_follows_parent_move(activity):
    child = detail(activity)
    assert child.phase == activity.phase
    phase = Phase.objects.create(project=activity.project, name="Testing", sequence=2)
    activity.phase = phase
    activity.save()
    child.refresh_from_db()
    assert child.phase == phase


def test_hierarchy_rejects_deeper_nesting_cycles_and_cross_project(activity):
    child = detail(activity)
    with pytest.raises(ValidationError):
        detail(child)
    activity.parent_task = child
    with pytest.raises(ValidationError):
        activity.full_clean()
    activity.parent_task = None
    activity.parent_task = activity
    with pytest.raises(ValidationError):
        activity.save()
    other = Project.objects.create(
        name="Other",
        code="OTHER",
        start_date=date(2026, 10, 1),
        target_end_date=date(2026, 11, 1),
    )
    with pytest.raises(ValidationError):
        Task.objects.create(project=other, parent_task=child, title="Invalid")


def test_activity_with_details_cannot_become_a_detail(activity):
    detail(activity)
    root = Task.objects.create(project=activity.project, title="Another activity")
    activity.parent_task = root
    with pytest.raises(ValidationError):
        activity.save()


def test_completion_requires_finished_details_and_reopening_reopens_parent(activity):
    child = detail(activity)
    activity.status = "done"
    with pytest.raises(ValidationError):
        activity.full_clean()
    child.status = "done"
    child.save()
    activity.save()
    assert activity.display_progress == 100
    child.status, child.progress = "in_progress", 25
    child.save()
    activity.refresh_from_db()
    assert activity.status == "in_progress"
    assert activity.completed_at is None
    assert activity.display_progress == 25


def test_contextual_create_locks_parent_and_inherits_phase(client, activity):
    child = detail(activity)
    client.force_login(activity.project.manager)
    url = reverse("work:task_create") + f"?project={activity.project_id}&parent_task={activity.pk}"
    form = client.get(url).context["form"]
    assert form.fields["parent_task"].disabled
    assert form.fields["phase"].disabled
    response = client.post(url, {"title": "Login screen", "parent_task": child.pk})
    assert response.status_code == 302, response.context["form"].errors
    created = Task.objects.get(title="Login screen")
    assert created.parent_task == activity
    assert created.phase == activity.phase
    assert response.url == reverse("work:task_detail", args=[activity.pk])
    assert (
        client.get(
            reverse("work:task_create"), {"project": activity.project_id, "parent_task": child.pk}
        ).status_code
        == 404
    )


def test_parent_progress_is_calculated_in_form_and_api(client, activity):
    detail(activity, progress=25)
    form = TaskForm(
        {"title": activity.title, "status": "todo", "progress": "99"},
        instance=activity,
        project=activity.project,
    )
    assert form.fields["progress"].disabled
    assert form.is_valid(), form.errors
    form.save()
    assert activity.display_progress == 25
    client.force_login(activity.project.manager)
    response = client.post(reverse("work:task_progress", args=[activity.pk]), {"progress": "99"})
    assert response.status_code == 400
    response = client.post(reverse("work:task_status", args=[activity.pk]), {"status": "done"})
    assert response.status_code == 400
    response = client.post(
        reverse("work:task_update", args=[activity.pk]),
        {"title": activity.title, "status": "done", "progress": "100"},
    )
    assert response.status_code == 200
    assert "status" in response.context["form"].errors


def test_member_can_update_assigned_detail_but_cannot_create(client, activity):
    member = User.objects.create_user("detail-member")
    activity.project.members.add(member)
    child = detail(activity, assignee=member)
    client.force_login(member)
    response = client.post(reverse("work:task_progress", args=[child.pk]), {"progress": "50"})
    assert response.status_code == 200
    assert actual_progress(activity.project) == 50
    response = client.post(
        reverse("work:task_create") + f"?project={activity.project_id}&parent_task={activity.pk}",
        {"title": "Unauthorized"},
    )
    assert response.status_code == 302
    assert not Task.objects.filter(title="Unauthorized").exists()


def test_timeline_groups_details_even_when_dates_sort_before_parent(client, activity):
    child = detail(activity, start_date=date(2026, 10, 1), due_date=date(2026, 10, 2))
    Task.objects.create(
        project=activity.project,
        phase=activity.phase,
        title="Earlier activity",
        start_date=date(2026, 10, 3),
    )
    rows = timeline_data(activity.project)["timeline_rows"]
    ids = [row["task"].pk for row in rows]
    assert ids.index(child.pk) == ids.index(activity.pk) + 1
    assert not rows[ids.index(child.pk)]["phase_heading"]
    client.force_login(activity.project.manager)
    response = client.get(reverse("projects:project_timeline", args=[activity.project_id]))
    assert f'data-toggle-details="{activity.pk}"'.encode() in response.content
    assert f'data-parent-task="{activity.pk}"'.encode() in response.content
    response = client.get(reverse("work:task_detail", args=[activity.pk]))
    assert b"Tambah detail activity" in response.content
    assert child.title.encode() in response.content


def test_parent_context_cannot_reference_another_project(client, activity):
    other = Project.objects.create(
        name="Other",
        code="OTHER",
        manager=activity.project.manager,
        start_date=date(2026, 10, 1),
        target_end_date=date(2026, 11, 1),
    )
    client.force_login(activity.project.manager)
    response = client.get(
        reverse("work:task_create"), {"project": other.pk, "parent_task": activity.pk}
    )
    assert response.status_code == 404
