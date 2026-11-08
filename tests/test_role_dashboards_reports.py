"""Fase 8: dashboard per role, portfolio health, laporan, audit trail, decision log."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.governance.changes import submit_deliverable
from apps.governance.models import Deliverable
from apps.governance.services import decide
from apps.identity.models import Role
from apps.identity.roles import assign_roles
from apps.projects.dashboards import portfolio_health
from apps.projects.exports import REPORTS, export_rows
from apps.projects.models import (
    ActivityEvent,
    Decision,
    LifecycleStatus,
    Milestone,
    ProgressBaselinePoint,
    Project,
)
from apps.projects.services import with_project_metrics
from apps.work.models import Issue, Task, TaskStatus

pytestmark = pytest.mark.django_db
TODAY = timezone.localdate()


def make_user(name, *roles):
    user = User.objects.create_user(name, password="valid-password")
    assign_roles(user, list(roles))
    return user


@pytest.fixture
def world():
    pm = make_user("pm", Role.PROJECT_MANAGER)
    worker = make_user("worker", Role.MEMBER)
    owner = make_user("sponsor", Role.OWNER)
    boss = make_user("direksi", Role.MANAGEMENT)
    client_user = make_user("klien", Role.CLIENT)
    admin = make_user("adm", Role.ADMIN)
    project = Project.objects.create(
        name="Alpha",
        code="ALPHA",
        manager=pm,
        owner=owner,
        lifecycle_status=LifecycleStatus.IN_PROGRESS,
        start_date=TODAY - timedelta(days=20),
        target_end_date=TODAY + timedelta(days=20),
    )
    project.members.add(worker, client_user)
    for offset, percent in ((-20, 0), (20, 100)):
        ProgressBaselinePoint.objects.create(
            project=project, date=TODAY + timedelta(days=offset), planned_percent=percent
        )
    secret = Task.objects.create(
        project=project,
        title="Rahasia teknis migrasi DB",
        assignee=worker,
        status=TaskStatus.IN_PROGRESS,
        due_date=TODAY - timedelta(days=1),
    )
    Task.objects.create(
        project=project, title="Blokir", assignee=worker, status="blocked", blocked_reason="x"
    )
    Milestone.objects.create(project=project, name="UAT", date=TODAY + timedelta(days=5))
    return {
        "pm": pm,
        "worker": worker,
        "owner": owner,
        "boss": boss,
        "client": client_user,
        "admin": admin,
        "project": project,
        "secret": secret,
    }


# -------------------------------------------------------------- dashboards


def test_member_dashboard_lists_own_work(world, client):
    client.force_login(world["worker"])
    body = client.get(reverse("projects:dashboard")).content.decode()
    assert "Pekerjaan Anda" in body and "Rahasia teknis migrasi DB" in body
    assert 'data-member-section="overdue"' in body and 'data-member-section="blocked"' in body


def test_management_dashboard_hides_technical_task_details(world, client):
    client.force_login(world["boss"])
    body = client.get(reverse("projects:dashboard")).content.decode()
    assert "Kondisi portfolio" in body and "data-health-distribution" in body
    assert "Rahasia teknis migrasi DB" not in body
    assert "UAT" in body  # milestone tetap terlihat


def test_client_dashboard_shows_deliverables_and_pending_acceptance(world, client):
    item = Deliverable.objects.create(
        project=world["project"],
        name="Manual pengguna",
        acceptance_criteria="Lengkap",
        evidence="link",
        owner=world["worker"],
        reviewer=world["client"],
    )
    submit_deliverable(item, world["worker"])
    client.force_login(world["client"])
    body = client.get(reverse("projects:dashboard")).content.decode()
    assert "Project Anda" in body and "data-pending-acceptance" in body
    assert "Manual pengguna" in body and "Rahasia teknis" not in body


def test_pm_dashboard_has_action_sections(world, client):
    client.force_login(world["pm"])
    response = client.get(reverse("projects:dashboard"))
    body = response.content.decode()
    assert "data-pm-sections" in body and "data-pending-approvals" in body
    assert response.context["pm"]["overdue_count"] == 1
    assert response.context["pm"]["blocked_count"] == 1


def test_portfolio_health_is_computed_from_data(world):
    Project.objects.create(
        name="Draft", code="DRAFT", start_date=TODAY, target_end_date=TODAY + timedelta(days=5)
    )
    Issue.objects.create(project=world["project"], title="Down", severity="critical")
    projects = list(with_project_metrics(Project.objects.all()))
    health = portfolio_health(projects)
    assert health["assessed"] == 1 and health["unassessed"] == 1
    assert health["attention"][0]["project"] == world["project"]
    assert "1 masalah kritis" in health["attention"][0]["reasons"]


# ------------------------------------------------------------------ reports


@pytest.mark.parametrize("kind", list(REPORTS))
def test_report_pages_render_for_pm(world, client, kind):
    client.force_login(world["pm"])
    response = client.get(reverse("projects:report_detail", args=[kind]))
    assert response.status_code == 200
    assert f'data-report="{kind}"' in response.content.decode()


def test_report_content_matches_prd_sections(world):
    projects = list(with_project_metrics(Project.objects.all()).prefetch_related("snapshots"))
    headers, rows = export_rows(projects, "executive")
    assert {"Owner", "Health", "Deviasi jadwal (hari)", "Risiko terbuka"} <= set(headers)
    headers, rows = export_rows(projects, "task_report")
    everyone = rows[0]
    assert everyone[1] == "Semua pelaksana" and everyone[2] == 2 and everyone[-1] == 1
    headers, rows = export_rows(projects, "schedule")
    assert any(row[1] == "Milestone" and row[-1] == "Akan datang" for row in rows)


def test_export_follows_report_export_permission(world, client):
    url = reverse("projects:export_report")
    client.force_login(world["client"])  # Client tidak punya report.export
    assert client.get(url, {"dataset": "executive", "format": "csv"}).status_code == 403
    client.force_login(world["boss"])
    assert client.get(url, {"dataset": "tasks", "format": "csv"}).status_code == 403
    assert client.get(reverse("projects:report_detail", args=["schedule"])).status_code == 403
    ok = client.get(url, {"dataset": "management", "format": "csv"})
    assert ok.status_code == 200 and "ALPHA" in ok.content.decode()
    outsider = make_user("pm2", Role.PROJECT_MANAGER)
    Project.objects.create(
        name="Beta", code="BETA", manager=outsider, start_date=TODAY, target_end_date=TODAY
    )
    client.force_login(world["pm"])
    body = client.get(url, {"dataset": "executive", "format": "csv"}).content.decode()
    assert "ALPHA" in body and "BETA" not in body


# -------------------------------------------------------------------- audit


def test_audit_trail_is_admin_only_and_traces_one_entity(world, client):
    task = world["secret"]
    client.force_login(world["pm"])
    assert client.get(reverse("projects:audit_trail")).status_code == 403
    task.reviewer = world["owner"]
    task.save()
    from apps.governance.services import submit_task

    approval = submit_task(task, world["worker"])
    decide(approval.steps.get(), world["owner"], False, "Bukti kurang")
    client.force_login(world["admin"])
    response = client.get(reverse("projects:audit_trail"), {"entity": "task", "id": task.pk})
    body = response.content.decode()
    rows = response.context["rows"]
    assert {row["kind"] for row in rows} == {"activity", "revision"}
    assert all(row["entity_id"] == task.pk for row in rows)
    assert "Bukti kurang" in body and "Reviewer" in body
    rejected = ActivityEvent.objects.get(action="approval.rejected")
    assert rejected.reason == "Bukti kurang" and rejected.active_role == Role.OWNER


# ------------------------------------------------------------ decision log


def test_decision_links_to_issue_of_same_project(world, client):
    issue = Issue.objects.create(project=world["project"], title="Kuota habis")
    client.force_login(world["pm"])
    client.post(
        reverse("projects:decision_create", args=[world["project"].pk]),
        {"title": "Pakai Redis", "decision": "Redis untuk kuota", "related_issue": issue.pk},
    )
    decision = Decision.objects.get()
    assert decision.related_issue == issue
    notes = client.get(reverse("projects:project_notes", args=[world["project"].pk]))
    assert "ISS-" in notes.content.decode()
    other = Project.objects.create(
        name="Beta", code="BETA", start_date=TODAY, target_end_date=TODAY
    )
    foreign = Issue.objects.create(project=other, title="Lain")
    decision.related_issue = foreign
    with pytest.raises(ValidationError):
        decision.full_clean()
