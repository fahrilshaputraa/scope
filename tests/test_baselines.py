"""Fase 5: baseline berversi (tanpa mekanisme approval)."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.identity.models import Role
from apps.identity.roles import assign_roles
from apps.projects.models import (
    BaselineStatus,
    ProgressSnapshot,
    Project,
)
from apps.projects.services import capture_baseline, planned_progress_on, record_snapshot
from apps.work.models import Task

pytestmark = pytest.mark.django_db


def make_user(name, *roles):
    user = User.objects.create_user(name, password="valid-password")
    assign_roles(user, list(roles))
    return user


@pytest.fixture
def people():
    return {
        "pm": make_user("pm", Role.PROJECT_MANAGER),
        "owner": make_user("sponsor", Role.OWNER),
        "owner2": make_user("sponsor2", Role.OWNER),
        "worker": make_user("worker", Role.MEMBER),
    }


@pytest.fixture
def project(people):
    today = timezone.localdate()
    project = Project.objects.create(
        name="Alpha",
        code="ALPHA",
        manager=people["pm"],
        owner=people["owner"],
        start_date=today - timedelta(days=10),
        target_end_date=today + timedelta(days=30),
    )
    Task.objects.create(
        project=project,
        title="Bangun",
        assignee=people["worker"],
        start_date=today - timedelta(days=10),
        due_date=today + timedelta(days=10),
        weight=1,
    )
    return project


# ------------------------------------------------------------------ baseline


def test_capture_baseline_applies_immediately(project, people):
    baseline = capture_baseline(project, people["pm"])
    assert baseline.version == 1
    assert baseline.status == BaselineStatus.ACTIVE
    assert project.baseline_points.exists()
    assert baseline.baseline_data["curve"]


def test_new_version_supersedes_old_and_keeps_history(project, people):
    capture_baseline(project, people["pm"])
    before = planned_progress_on(project)
    task = project.tasks.get()
    task.due_date = task.due_date + timedelta(days=20)
    task.save()

    second = capture_baseline(project, people["pm"])
    assert second.version == 2
    assert second.status == BaselineStatus.ACTIVE
    assert planned_progress_on(project) != before
    # Versi lama tidak dihapus (BR-CHG-006).
    assert project.baselines.get(version=1).status == BaselineStatus.SUPERSEDED
    assert project.baselines.count() == 2
    assert project.baselines.filter(status=BaselineStatus.ACTIVE).count() == 1


def test_snapshots_record_baseline_version_and_health(project, people):
    capture_baseline(project, people["pm"])
    old = record_snapshot(project, timezone.localdate() - timedelta(days=3))
    assert old.baseline.version == 1
    assert old.health_status in {"", "on_track", "at_risk", "delayed", "critical"}
    capture_baseline(project, people["pm"])
    assert ProgressSnapshot.objects.get(pk=old.pk).baseline.version == 1  # tidak dihitung ulang
    assert record_snapshot(project).baseline.version == 2


def test_baseline_needs_complete_schedule(project, people):
    project.tasks.update(due_date=None)
    with pytest.raises(ValidationError, match="tanggal"):
        capture_baseline(project, people["pm"])
    assert project.baselines.count() == 0


def test_deleting_a_project_keeps_working_with_baselines(project, people):
    capture_baseline(project, people["pm"])
    project.delete()
    assert not Project.objects.filter(code="ALPHA").exists()
