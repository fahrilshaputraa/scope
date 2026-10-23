import threading
from datetime import date
from decimal import Decimal

import pytest
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

from apps.projects.models import ProgressSnapshot, Project, ProjectStatus
from apps.projects.scheduler import THREAD_NAME, start_scheduler, tick

pytestmark = pytest.mark.django_db


def make_project(code, **kwargs):
    defaults = {
        "name": f"Project {code}",
        "code": code,
        "start_date": date(2026, 10, 1),
        "target_end_date": date(2026, 11, 1),
    }
    defaults.update(kwargs)
    return Project.objects.create(**defaults)


def clear_today(project):
    project.snapshots.filter(date=timezone.localdate()).delete()


def test_due_command_is_idempotent_per_day():
    project = make_project("DUE1")
    clear_today(project)

    call_command("snapshot_progress", "--due")
    call_command("snapshot_progress", "--due")

    assert project.snapshots.filter(date=timezone.localdate()).count() == 1
    assert ProgressSnapshot.objects.filter(project=project).count() == 1


def test_due_command_skips_projects_with_today_snapshot():
    project = make_project("SKIP1")
    snapshot = project.snapshots.get(date=timezone.localdate())
    snapshot.actual_progress = Decimal("12.34")
    snapshot.save(update_fields=["actual_progress"])

    call_command("snapshot_progress", "--due")

    snapshot.refresh_from_db()
    assert snapshot.actual_progress == Decimal("12.34")


def test_due_command_excludes_archived_and_cancelled_projects():
    active = make_project("ACTIVE")
    archived = make_project("ARCH")
    archived.archive()
    cancelled = make_project("CANC")
    cancelled.status = ProjectStatus.CANCELLED
    cancelled.save()
    for project in (active, archived, cancelled):
        clear_today(project)

    call_command("snapshot_progress", "--due")

    today = timezone.localdate()
    assert active.snapshots.filter(date=today).count() == 1
    assert not archived.snapshots.filter(date=today).exists()
    assert not cancelled.snapshots.filter(date=today).exists()


def test_scheduler_tick_captures_once_per_day():
    project = make_project("TICK")
    clear_today(project)

    assert tick() == 1
    assert tick() == 0
    assert project.snapshots.filter(date=timezone.localdate()).count() == 1


def test_scheduler_is_disabled_by_default():
    assert settings.SCOPE_SCHEDULER_ENABLED is False
    assert start_scheduler() is None
    assert not any(thread.name == THREAD_NAME for thread in threading.enumerate())
