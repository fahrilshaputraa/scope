"""Fase 3: lifecycle dan health terpisah, aturan transisi, dan aturan PM vs pelaksana."""

from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.identity.models import Role, RoleDefinition
from apps.identity.roles import assign_roles
from apps.projects.models import (
    HealthStatus,
    LifecycleStatus,
    ProgressBaselinePoint,
    Project,
)
from apps.work.forms import TaskForm
from apps.work.models import KANBAN_COLUMNS, Issue, Task, TaskStatus

pytestmark = pytest.mark.django_db


def make_user(name, *roles, **extra):
    user = User.objects.create_user(name, password="valid-password", **extra)
    assign_roles(user, list(roles))
    return user


@pytest.fixture
def people():
    return {
        "pm": make_user("pm", Role.PROJECT_MANAGER),
        "owner": make_user("sponsor", Role.OWNER),
        "worker": make_user("worker", Role.MEMBER),
        "admin": make_user("adm", Role.ADMIN),
    }


def make_project(people, **extra):
    fields = {
        "name": "Alpha",
        "code": "ALPHA",
        "manager": people["pm"],
        "owner": people["owner"],
        "start_date": timezone.localdate() - timedelta(days=30),
        "target_end_date": timezone.localdate() + timedelta(days=30),
        **extra,
    }
    return Project.objects.create(**fields)


def baseline(project, planned_now):
    ProgressBaselinePoint.objects.create(
        project=project, date=project.start_date, planned_percent=0
    )
    ProgressBaselinePoint.objects.create(
        project=project, date=timezone.localdate(), planned_percent=planned_now
    )
    ProgressBaselinePoint.objects.create(
        project=project, date=project.target_end_date, planned_percent=100
    )


# ----------------------------------------------------------- lifecycle rules


def test_new_project_must_start_as_draft_or_planning(people):
    project = Project(
        name="X",
        code="X",
        manager=people["pm"],
        start_date=date(2026, 1, 1),
        target_end_date=date(2026, 2, 1),
        lifecycle_status=LifecycleStatus.IN_PROGRESS,
    )
    with pytest.raises(ValidationError) as error:
        project.full_clean()
    assert "lifecycle_status" in error.value.message_dict
    project.lifecycle_status = LifecycleStatus.DRAFT
    project.full_clean()


def test_in_progress_requires_planning_requirements(people):
    project = make_project(people, owner=None)
    project.lifecycle_status = LifecycleStatus.IN_PROGRESS
    with pytest.raises(ValidationError) as error:
        project.full_clean()
    message = " ".join(error.value.message_dict["lifecycle_status"])
    assert "Owner" in message and "task" in message and "baseline" in message
    project.owner = people["owner"]
    Task.objects.create(project=project, title="T")
    baseline(project, 0)
    project.full_clean()


def test_completed_requires_closure_and_cancelled_requires_reason(people):
    project = make_project(people, lifecycle_status=LifecycleStatus.IN_PROGRESS)
    task = Task.objects.create(project=project, title="T")
    Issue.objects.create(project=project, title="Masalah")
    project.lifecycle_status = LifecycleStatus.COMPLETED
    with pytest.raises(ValidationError) as error:
        project.full_clean()
    message = " ".join(error.value.message_dict["lifecycle_status"])
    assert "1 task belum selesai" in message and "1 issue masih terbuka" in message
    task.status = TaskStatus.DONE
    task.save()
    Issue.objects.update(status="closed")
    project.full_clean()

    project.lifecycle_status = LifecycleStatus.CANCELLED
    with pytest.raises(ValidationError) as error:
        project.full_clean()
    assert "cancellation_reason" in error.value.message_dict
    project.cancellation_reason = "Anggaran dihentikan"
    project.full_clean()


def test_unchanged_lifecycle_is_not_revalidated(people):
    project = make_project(people, owner=None, lifecycle_status=LifecycleStatus.IN_PROGRESS)
    project.name = "Diubah"
    project.full_clean()  # tidak mengulang syarat bila status tidak berubah


# -------------------------------------------------------------------- health


def test_health_is_not_assessed_before_the_project_runs(people):
    project = make_project(people, lifecycle_status=LifecycleStatus.PLANNING)
    assert project.health_status is None and project.get_health_status_display() == "—"


def test_health_follows_progress_and_deadline(people):
    project = make_project(people, lifecycle_status=LifecycleStatus.IN_PROGRESS)
    Task.objects.create(project=project, title="T", progress=50)
    baseline(project, 50)
    assert project.health_status == HealthStatus.ON_TRACK
    ProgressBaselinePoint.objects.filter(date=timezone.localdate()).update(planned_percent=53)
    assert project.health_status == HealthStatus.AT_RISK
    ProgressBaselinePoint.objects.filter(date=timezone.localdate()).update(planned_percent=70)
    assert project.health_status == HealthStatus.DELAYED
    Project.objects.filter(pk=project.pk).update(
        target_end_date=timezone.localdate() - timedelta(days=1)
    )
    project.refresh_from_db()
    assert project.health_status == HealthStatus.CRITICAL


def test_critical_issue_raises_health_to_at_risk(people):
    project = make_project(people, lifecycle_status=LifecycleStatus.IN_PROGRESS)
    Task.objects.create(project=project, title="T", progress=50)
    baseline(project, 50)
    Issue.objects.create(project=project, title="Gawat", severity="critical")
    assert project.health_status == HealthStatus.AT_RISK


def test_project_list_filters_by_lifecycle_and_health_separately(client, people):
    running = make_project(people, lifecycle_status=LifecycleStatus.IN_PROGRESS)
    Task.objects.create(project=running, title="T", progress=0)
    baseline(running, 80)
    make_project(people, name="Beta", code="BETA", lifecycle_status=LifecycleStatus.PLANNING)
    client.force_login(people["admin"])
    by_lifecycle = client.get(reverse("projects:project_list"), {"status": "planning"})
    assert [r["project"].code for r in by_lifecycle.context["rows"]] == ["BETA"]
    by_health = client.get(reverse("projects:project_list"), {"health": "delayed"})
    assert [r["project"].code for r in by_health.context["rows"]] == ["ALPHA"]
    page = client.get(reverse("projects:project_detail", args=[running.pk])).content
    assert b"Berjalan" in page and b"Terlambat" in page


def test_dashboard_counts_health_only_for_running_projects(client, people):
    make_project(people, lifecycle_status=LifecycleStatus.PLANNING)
    client.force_login(people["admin"])
    counts = client.get(reverse("projects:dashboard")).context["counts"]
    assert counts == {"total": 1, "on_track": 0, "at_risk": 0, "delayed": 0}


# ---------------------------------------------------------------- task order


def test_task_status_order_and_label_follow_the_prd():
    expected = ["backlog", "todo", "in_progress", "review", "blocked", "done"]
    assert [s.value for s in KANBAN_COLUMNS] == expected
    assert list(TaskStatus.values) == [s.value for s in KANBAN_COLUMNS]
    assert TaskStatus.REVIEW.label == "In Review"


# --------------------------------------------------------- assignment rules


def test_project_manager_cannot_be_assignee_of_their_own_project(people):
    project = make_project(people)
    task = Task(project=project, title="T", assignee=people["pm"])
    with pytest.raises(ValidationError) as error:
        task.full_clean()
    assert "assignee" in error.value.message_dict


def test_only_executor_roles_can_be_assigned(people):
    project = make_project(people)
    owner_only = Task(project=project, title="T", assignee=people["owner"])
    with pytest.raises(ValidationError):
        owner_only.full_clean()
    Task(project=project, title="T", assignee=people["worker"]).full_clean()
    other_pm = make_user("pm2", Role.PROJECT_MANAGER)
    with pytest.raises(ValidationError):
        Task(project=project, title="T", assignee=other_pm).full_clean()
    both = make_user("dual", Role.PROJECT_MANAGER, Role.MEMBER)
    Task(project=project, title="T", assignee=both).full_clean()


def test_existing_legacy_assignee_is_not_revalidated(people):
    project = make_project(people)
    task = Task.objects.create(project=project, title="T", assignee=people["pm"])
    task.title = "Diubah"
    task.full_clean()


def test_assignee_choices_exclude_the_manager_and_non_executors(people):
    project = make_project(people)
    project.members.add(people["pm"], people["owner"], people["worker"])
    form = TaskForm(project=project)
    assert list(form.fields["assignee"].queryset) == [people["worker"]]


# -------------------------------------------------- PM plans, member executes


def test_pm_form_has_no_progress_and_limited_status(people):
    project = make_project(people)
    task = Task.objects.create(
        project=project, title="T", assignee=people["worker"], status=TaskStatus.TODO
    )
    form = TaskForm(instance=task, project=project, can_plan=True, can_execute=False)
    assert "progress" not in form.fields and "blocked_reason" not in form.fields
    assert [k for k, _ in form.fields["status"].choices] == ["backlog", "todo"]
    task.status = TaskStatus.IN_PROGRESS
    started = TaskForm(instance=task, project=project, can_plan=True, can_execute=False)
    assert started.fields["status"].disabled


def test_pm_cannot_update_progress_or_status_through_the_api(client, people):
    project = make_project(people)
    task = Task.objects.create(project=project, title="T", assignee=people["worker"])
    client.force_login(people["pm"])
    progress = reverse("work:task_progress", args=[task.pk])
    status = reverse("work:task_status", args=[task.pk])
    assert client.post(progress, {"progress": "50"}).status_code == 403
    assert client.post(status, {"status": "done"}).status_code == 403
    client.force_login(people["worker"])
    assert client.post(progress, {"progress": "50"}).status_code == 200


def test_pm_can_plan_but_not_open_the_work_update_mode(client, people):
    project = make_project(people)
    task = Task.objects.create(project=project, title="T", assignee=people["worker"])
    client.force_login(people["pm"])
    edit = client.get(reverse("work:task_update", args=[task.pk]))
    assert edit.status_code == 200 and "progress" not in edit.context["form"].fields
    work = client.get(reverse("work:task_update", args=[task.pk]) + "?mode=update")
    assert work.status_code == 302


def test_admin_keeps_both_planning_and_execution_fields(client, people):
    project = make_project(people)
    task = Task.objects.create(project=project, title="T", assignee=people["worker"])
    client.force_login(people["admin"])
    form = client.get(reverse("work:task_update", args=[task.pk])).context["form"]
    assert "progress" in form.fields and "assignee" in form.fields


def test_reassignment_needs_the_reassign_permission(people):
    project = make_project(people)
    task = Task.objects.create(project=project, title="T", assignee=people["worker"])
    role = RoleDefinition.objects.get(code="pm")
    role.permissions = [p for p in role.permissions if p != "task.reassign"]
    role.save()
    allowed = TaskForm(instance=task, project=project, can_plan=True, can_execute=False)
    assert not allowed.fields["assignee"].disabled  # default True mengikuti argumen
    from apps.identity.roles import has_perm

    assert not has_perm(people["pm"], "task.reassign")
    locked = TaskForm(
        instance=task, project=project, can_plan=True, can_execute=False, can_reassign=False
    )
    assert locked.fields["assignee"].disabled and locked.fields["collaborators"].disabled
