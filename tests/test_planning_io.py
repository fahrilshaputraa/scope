import copy
import json
from datetime import date

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.identity.models import Role
from apps.projects.models import PlanningImport, Project
from apps.projects.planning_io import export_plan, import_plan, planning_template, read_plan
from apps.work.models import Task

pytestmark = pytest.mark.django_db


@pytest.fixture
def plan_case():
    pm = User.objects.create_user("planner")
    pm.pcc_profile.role = Role.PROJECT_MANAGER
    pm.pcc_profile.save()
    member = User.objects.create_user("worker")
    project = Project.objects.create(
        name="Launch",
        code="LAUNCH",
        manager=pm,
        start_date=date(2026, 10, 1),
        target_end_date=date(2026, 11, 1),
    )
    payload = planning_template(pm, project)
    payload["tasks"][1]["assignee"] = member.username
    return pm, member, project, payload


def upload(payload):
    return SimpleUploadedFile(
        "plan.json", json.dumps(payload).encode(), content_type="application/json"
    )


def test_import_builds_complete_plan_and_duplicate_is_noop(plan_case):
    pm, member, project, payload = plan_case
    result = import_plan(read_plan(upload(payload)), pm, project, baseline=True)
    assert result["tasks"] == 2 and result["phases"] == 1 and result["milestones"] == 1
    first, second = project.tasks.order_by("order")
    assert second.assignee == member and second.dependencies.get() == first
    assert second.phase.project == project and second.milestone.project == project
    assert project.members.filter(pk=member.pk).exists()
    assert project.baseline_points.exists() and second.baseline_start_date
    repeat = import_plan(payload, pm, project)
    assert repeat["already_imported"] and project.tasks.count() == 2
    assert PlanningImport.objects.count() == 1


@pytest.mark.parametrize(
    "case",
    [
        "cycle",
        "parent_cycle",
        "unknown_user",
        "unknown_phase",
        "unknown_task",
        "reversed_dates",
        "negative_weight",
        "bad_progress",
        "bad_status",
        "blocked_no_reason",
        "dependency_unfinished",
    ],
)
def test_invalid_import_rolls_back_every_entity(plan_case, case):
    pm, member, project, payload = plan_case
    first, second = payload["tasks"]
    if case == "cycle":
        first["dependencies"] = ["task-2"]
    if case == "parent_cycle":
        first["parent_task"] = "task-2"
        second["parent_task"] = "task-1"
    if case == "unknown_user":
        second["assignee"] = "missing-user"
    if case == "unknown_phase":
        second["phase"] = "missing-phase"
    if case == "unknown_task":
        second["dependencies"] = ["missing-task"]
    if case == "reversed_dates":
        second["due_date"] = "2020-01-01"
    if case == "negative_weight":
        second["weight"] = -1
    if case == "bad_progress":
        second["progress"] = 101
    if case == "bad_status":
        second["status"] = "fake-status"
    if case == "blocked_no_reason":
        second["status"] = "blocked"
    if case == "dependency_unfinished":
        second["status"] = "in_progress"
    before = project.snapshots.get().actual_progress
    with pytest.raises(ValidationError):
        import_plan(payload, pm, project)
    assert (
        not project.tasks.exists()
        and not project.phases.exists()
        and not project.milestones.exists()
    )
    assert not project.members.exists() and not project.planning_imports.exists()
    assert project.snapshots.get().actual_progress == before


@pytest.mark.parametrize(
    "text",
    [
        '{"version":1,"version":1}',
        '{"version":1,"tasks":[]}',
        '{"version":1,"tasks":[NaN]}',
        '{"version":true,"tasks":[{}]}',
        '{"version":1,"taskz":[]}',
        "not JSON",
    ],
)
def test_json_parser_rejects_wrong_or_ambiguous_documents(text):
    with pytest.raises(ValidationError):
        read_plan(SimpleUploadedFile("plan.json", text.encode()))


def test_import_done_normalization_parent_and_export_refs(plan_case):
    pm, member, project, payload = plan_case
    payload["tasks"][0]["status"] = "done"
    payload["tasks"][0]["progress"] = 25
    payload["tasks"][1]["status"] = "in_progress"
    payload["tasks"][1]["parent_task"] = "task-1"
    import_plan(payload, pm, project)
    first, second = project.tasks.order_by("order")
    assert first.progress == 100 and first.completed_at
    assert second.parent_task == first
    exported = export_plan(project)
    assert exported["tasks"][1]["dependencies"] == [f"task-{first.pk}"]
    assert exported["tasks"][1]["parent_task"] == f"task-{first.pk}"
    assert read_plan(upload(exported))["version"] == 1


def test_import_new_project_and_retry(plan_case):
    pm, member, project, payload = plan_case
    payload["project"]["code"] = "NEW-PLAN"
    result = import_plan(payload, pm)
    assert result["project"] != project and result["project"].manager == pm
    assert result["project"].tasks.count() == 2
    assert import_plan(payload, pm)["already_imported"]
    assert Project.objects.filter(code="NEW-PLAN").count() == 1


def test_invalid_new_project_is_not_created(plan_case):
    pm, member, project, payload = plan_case
    payload["project"]["code"] = "INVALID"
    payload["tasks"][1]["assignee"] = "invalid-user"
    with pytest.raises(ValidationError):
        import_plan(payload, pm)
    assert not Project.objects.filter(code="INVALID").exists()


def test_http_import_template_export_and_permission(plan_case, client):
    pm, member, project, payload = plan_case
    project.members.add(member)
    client.force_login(pm)
    assert client.get(reverse("projects:plan_import", args=[project.pk])).status_code == 200
    template = client.get(reverse("projects:plan_template", args=[project.pk]))
    assert template.json()["available_users"] and "attachment" in template["Content-Disposition"]
    response = client.post(
        reverse("projects:plan_import", args=[project.pk]), {"file": upload(payload)}
    )
    assert response.status_code == 302 and project.tasks.count() == 2
    client.force_login(member)
    assert (
        client.post(
            reverse("projects:plan_import", args=[project.pk]), {"file": upload(payload)}
        ).status_code
        == 403
    )
    assert client.get(reverse("projects:plan_template", args=[project.pk])).status_code == 403
    assert client.get(reverse("projects:plan_export", args=[project.pk])).status_code == 200
    stranger = User.objects.create_user("outsider")
    client.force_login(stranger)
    assert client.get(reverse("projects:plan_export", args=[project.pk])).status_code == 404


def test_wrong_project_code_and_failed_baseline_are_atomic(plan_case):
    pm, member, project, payload = plan_case
    wrong = copy.deepcopy(payload)
    wrong["project"]["code"] = "SOMEWHERE-ELSE"
    with pytest.raises(ValidationError):
        import_plan(wrong, pm, project)
    Task.objects.create(project=project, title="Existing undated task")
    with pytest.raises(ValidationError):
        import_plan(payload, pm, project, baseline=True)
    assert project.tasks.count() == 1 and not project.phases.exists()


def test_minimal_project_and_task_forms_keep_defaults(plan_case, client):
    pm, member, project, payload = plan_case
    client.force_login(pm)
    response = client.post(reverse("projects:project_create"), {"name": "Quick project"})
    assert response.status_code == 302
    new = Project.objects.get(name="Quick project")
    assert (
        new.manager == pm and new.code.startswith("PRJ-") and new.target_end_date > new.start_date
    )
    response = client.post(
        reverse("work:task_create") + f"?project={new.pk}", {"title": "Quick task"}
    )
    assert response.status_code == 302
    task = new.tasks.get()
    assert task.weight == 1 and task.progress == 0 and task.status == "todo"
    for route in ("project_detail", "project_tasks", "project_activity"):
        assert client.get(reverse("projects:" + route, args=[new.pk])).status_code == 200
    assert client.get(reverse("work:task_detail", args=[task.pk])).status_code == 200


def test_member_picker_clears_and_rejects_outside_assignee(plan_case, client):
    pm, member, project, payload = plan_case
    project.members.add(member)
    client.force_login(pm)
    page = client.get(reverse("projects:project_members", args=[project.pk]))
    assert b"data-choice-search" in page.content and b"data-choice-count" in page.content
    assert f'value="{member.pk}"'.encode() in page.content
    assert b'name="members" value=""' not in page.content
    assert (
        client.post(reverse("projects:project_members", args=[project.pk]), {}).status_code == 302
    )
    assert not project.members.exists()
    response = client.post(
        reverse("work:task_create") + f"?project={project.pk}",
        {"title": "Foreign assignment", "assignee": member.pk},
    )
    assert response.status_code == 200 and not project.tasks.exists()


def test_collaborator_survives_plan_export_and_reimport(plan_case):
    pm, member, project, payload = plan_case
    payload["tasks"][1]["collaborators"] = [pm.username]
    import_plan(payload, pm, project)
    task = project.tasks.order_by("order")[1]
    assert task.collaborators.get() == pm
    exported = export_plan(project)
    assert exported["tasks"][1]["collaborators"] == [pm.username]
    target = Project.objects.create(
        name="Second",
        code="SECOND",
        manager=pm,
        start_date=project.start_date,
        target_end_date=project.target_end_date,
    )
    exported["project"]["code"] = target.code
    import_plan(read_plan(upload(exported)), pm, target)
    assert target.tasks.order_by("order")[1].collaborators.get() == pm
