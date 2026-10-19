from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.identity.models import Role
from apps.projects.models import (
    ActivityAction,
    ActivityEvent,
    Milestone,
    Note,
    Phase,
    ProgressBaselinePoint,
    Project,
    Risk,
)
from apps.work.models import Issue, Task, TaskComment

pytestmark = pytest.mark.django_db


@pytest.fixture
def public_case():
    pm = User.objects.create_user("pm-user")
    pm.pcc_profile.role = Role.PROJECT_MANAGER
    pm.pcc_profile.display_name = "Petra Manager"
    pm.pcc_profile.save()
    member = User.objects.create_user("member-user")
    member.pcc_profile.display_name = "Mira Member"
    member.pcc_profile.save()
    outsider = User.objects.create_user("outsider-user")
    project = Project.objects.create(
        name="Public Launch",
        code="PUB-LAUNCH",
        description="Internal-only description",
        manager=pm,
        team="Team Secret",
        start_date=date(2026, 1, 1),
        target_end_date=date(2026, 6, 30),
        status="on_track",
    )
    project.members.add(pm, member)
    discovery = Phase.objects.create(
        project=project,
        name="Discovery",
        sequence=1,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 2, 1),
        status="completed",
    )
    Phase.objects.create(
        project=project,
        name="Delivery",
        sequence=2,
        start_date=date(2026, 2, 2),
        end_date=date(2026, 6, 30),
        status="in_progress",
    )
    Milestone.objects.create(
        project=project,
        name="Go Live",
        date=date(2026, 6, 30),
        status="upcoming",
        owner=pm,
        description="Internal milestone detail",
    )
    ProgressBaselinePoint.objects.create(
        project=project,
        date=date(2026, 1, 1),
        planned_percent=Decimal("10.00"),
    )
    task = Task.objects.create(
        project=project,
        title="Secret task title",
        description="secret task description",
        phase=discovery,
        assignee=member,
        status="in_progress",
        progress=Decimal("40.00"),
        weight=Decimal("1.00"),
    )
    TaskComment.objects.create(task=task, author=member, content="secret comment body")
    Note.objects.create(project=project, title="Secret note title", content="secret note body")
    Risk.objects.create(project=project, title="Secret risk title")
    Issue.objects.create(project=project, title="Secret issue title", owner=pm)
    ActivityEvent.objects.create(
        project=project,
        actor=pm,
        action=ActivityAction.PROJECT_UPDATED,
        message="secret activity message",
    )
    return SimpleNamespace(pm=pm, member=member, outsider=outsider, project=project)


def publish(project):
    project.is_public = True
    project.save(update_fields=["is_public"])


def public_url(project):
    return reverse("projects:public_project", args=[project.public_token])


def test_unpublished_project_is_not_public(client, public_case):
    assert client.get(public_url(public_case.project)).status_code == 404


def test_public_page_shows_progress_and_hides_internal_data(client, public_case):
    publish(public_case.project)
    response = client.get(public_url(public_case.project))
    assert response.status_code == 200
    content = response.content
    for visible in (
        b"Public Launch",
        b"PUB-LAUNCH",
        b"Discovery",
        b"Delivery",
        b"Go Live",
        b"Rencana",
        b"Actual",
        b"progress-chart-data",
        b"Secret task title",
        b"task-timeline-grid",
        b"public-phase",
        b"Belum ada pekerjaan di fase ini.",
    ):
        assert visible in content
    assert response.context["timeline_rows"]
    assert response.context["phase_groups"]
    for hidden in (
        b"pm-user",
        b"Petra Manager",
        b"member-user",
        b"Mira Member",
        b"Secret task description",
        b"secret comment body",
        b"Internal-only description",
        b"Team Secret",
        b"Secret note title",
        b"secret note body",
        b"Secret risk title",
        b"Secret issue title",
        b"secret activity message",
        b"Internal milestone detail",
    ):
        assert hidden not in content
    assert response["X-Robots-Tag"] == "noindex, nofollow"
    assert "no-store" in response["Cache-Control"] or "no-cache" in response["Cache-Control"]
    for internal_path in (b"/projects/", b"/tasks/", b"/auth/"):
        assert internal_path not in content


def test_unknown_or_malformed_token_returns_404(client, public_case):
    assert client.get("/p/00000000-0000-4000-8000-000000000000/").status_code == 404


def test_pm_can_publish_and_unpublish(client, public_case):
    project = public_case.project
    client.force_login(public_case.pm)
    share_url = reverse("projects:project_share", args=[project.pk])

    assert client.post(share_url, {"action": "publish"}).status_code == 302
    project.refresh_from_db()
    assert project.is_public is True and project.published_at is not None
    assert ActivityEvent.objects.filter(project=project, message="Project dipublikasikan.").exists()
    assert client.get(public_url(project)).status_code == 200

    assert client.post(share_url, {"action": "unpublish"}).status_code == 302
    project.refresh_from_db()
    assert project.is_public is False
    assert client.get(public_url(project)).status_code == 404


def test_reset_rotates_token_and_kills_old_link(client, public_case):
    project = public_case.project
    publish(project)
    old_token = project.public_token
    client.force_login(public_case.pm)

    response = client.post(reverse("projects:project_share_reset", args=[project.pk]))
    assert response.status_code == 302
    project.refresh_from_db()
    assert project.public_token != old_token
    assert client.get(reverse("projects:public_project", args=[old_token])).status_code == 404
    assert client.get(public_url(project)).status_code == 200


def test_share_controls_are_pm_only(client, public_case):
    project = public_case.project
    share_url = reverse("projects:project_share", args=[project.pk])

    response = client.get(share_url)
    assert response.status_code == 302 and "/auth/login/" in response["Location"]

    client.force_login(public_case.member)
    assert client.get(share_url).status_code == 403
    assert client.post(share_url, {"action": "publish"}).status_code == 403

    client.force_login(public_case.outsider)
    assert client.get(share_url).status_code == 404


def test_public_page_is_get_only_and_reset_is_post_only(client, public_case):
    project = public_case.project
    publish(project)
    url = public_url(project)
    assert client.post(url).status_code == 405

    client.force_login(public_case.pm)
    reset_url = reverse("projects:project_share_reset", args=[project.pk])
    assert client.get(reset_url).status_code == 405


def test_chart_requires_baseline(client, public_case):
    project = public_case.project
    publish(project)
    response = client.get(public_url(project))
    assert b"progress-chart-data" in response.content

    project.baseline_points.all().delete()
    response = client.get(public_url(project))
    assert b"progress-chart-data" not in response.content
    assert b"belum tersedia" in response.content


def test_each_project_gets_a_unique_public_token(public_case):
    other = Project.objects.create(
        name="Other",
        code="OTHER",
        manager=public_case.pm,
        start_date=date(2026, 1, 1),
        target_end_date=date(2026, 6, 30),
    )
    assert other.public_token is not None
    assert other.public_token != public_case.project.public_token


def test_share_page_exposes_url_and_privacy_note(client, public_case):
    project = public_case.project
    client.force_login(public_case.pm)
    response = client.get(reverse("projects:project_share", args=[project.pk]))
    assert response.status_code == 200
    assert f"/p/{project.public_token}/".encode() in response.content
    assert b"TIDAK DITAMPILKAN" in response.content
    assert b"Buat ulang tautan" in response.content
