from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.identity.models import Role
from apps.projects.models import Phase, Project
from apps.projects.services import actual_progress
from apps.work.models import Task


@pytest.fixture
def project(db):
    user = User.objects.create_user("pm", password="test-password")
    user.pcc_profile.role = Role.PROJECT_MANAGER
    user.pcc_profile.save()
    return Project.objects.create(
        name="Project",
        code="P1",
        manager=user,
        start_date=date(2026, 10, 1),
        target_end_date=date(2026, 11, 1),
    )


@pytest.mark.django_db
def test_done_updates_all_progress_consumers(client, project):
    phase = Phase.objects.create(project=project, name="Build")
    task = Task.objects.create(project=project, phase=phase, title="Work", progress=40)
    client.force_login(project.manager)
    response = client.patch(
        reverse("work:task_status", args=[task.pk]),
        "status=done",
        content_type="application/x-www-form-urlencoded",
    )
    assert response.status_code == 200
    task.refresh_from_db()
    assert task.progress == 100
    assert task.completed_at is not None
    assert actual_progress(project) == Decimal("100.00")
    assert phase.progress == Decimal("100.00")
