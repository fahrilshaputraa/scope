import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db


def test_run_scheduler_once_runs_a_tick(capsys):
    call_command("run_scheduler", "--once")
    assert "Tick selesai" in capsys.readouterr().out
