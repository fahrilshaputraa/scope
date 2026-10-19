from datetime import date
from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

from apps.projects.demo import DEMO_PROJECT_CODES
from apps.projects.models import Project

pytestmark = pytest.mark.django_db


def make_project(code, name):
    return Project.objects.create(
        name=name,
        code=code,
        start_date=date(2026, 1, 1),
        target_end_date=date(2026, 6, 30),
    )


def test_remove_demo_deletes_only_demo_projects():
    user = User.objects.create_user("demo-user")
    demo = make_project("HRMS-01", "Demo project")
    real = make_project("REAL-01", "Real project")

    output = StringIO()
    call_command("remove_demo", stdout=output)

    assert not Project.objects.filter(pk=demo.pk).exists()
    assert Project.objects.filter(pk=real.pk).exists()
    assert User.objects.filter(pk=user.pk).exists()
    assert "1 project" in output.getvalue()


def test_remove_demo_dry_run_keeps_data():
    demo = make_project("LBR-02", "Demo project")

    output = StringIO()
    call_command("remove_demo", "--dry-run", stdout=output)

    assert Project.objects.filter(pk=demo.pk).exists()
    assert "Dry run" in output.getvalue()
    assert "LBR-02" in output.getvalue()


def test_remove_demo_reports_when_nothing_to_delete():
    output = StringIO()
    call_command("remove_demo", stdout=output)
    assert "Tidak ada data demo." in output.getvalue()


def test_seed_then_remove_demo_round_trip():
    call_command("seed_demo", stdout=StringIO())
    assert Project.objects.filter(code__in=DEMO_PROJECT_CODES).count() == len(DEMO_PROJECT_CODES)

    call_command("remove_demo", stdout=StringIO())
    assert not Project.objects.filter(code__in=DEMO_PROJECT_CODES).exists()
