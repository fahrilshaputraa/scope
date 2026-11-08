"""Fase 4: Progress Task, Project Control, tindak lanjut, dan dashboard Owner."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from apps.identity.models import Role, RoleDefinition
from apps.identity.roles import assign_roles
from apps.notifications.models import Notification
from apps.projects.control import flag_counts, task_flags
from apps.projects.models import ActivityEvent, LifecycleStatus, Milestone, Project, Risk
from apps.work.models import Issue, Task, TaskComment, TaskStatus

pytestmark = pytest.mark.django_db
TODAY = timezone.localdate()


def make_user(name, *roles, **extra):
    user = User.objects.create_user(name, password="valid-password", **extra)
    assign_roles(user, list(roles))
    return user


@pytest.fixture
def world():
    pm = make_user("pm", Role.PROJECT_MANAGER)
    other_pm = make_user("pm2", Role.PROJECT_MANAGER)
    worker = make_user("worker", Role.MEMBER)
    worker2 = make_user("worker2", Role.MEMBER)
    owner = make_user("sponsor", Role.OWNER)
    admin = make_user("adm", Role.ADMIN)
    project = Project.objects.create(
        name="Alpha",
        code="ALPHA",
        manager=pm,
        owner=owner,
        lifecycle_status=LifecycleStatus.IN_PROGRESS,
        start_date=TODAY - timedelta(days=30),
        target_end_date=TODAY + timedelta(days=30),
    )
    project.members.add(worker, worker2)
    other = Project.objects.create(
        name="Beta",
        code="BETA",
        manager=other_pm,
        start_date=TODAY - timedelta(days=30),
        target_end_date=TODAY + timedelta(days=30),
    )
    return {
        "pm": pm,
        "other_pm": other_pm,
        "worker": worker,
        "worker2": worker2,
        "owner": owner,
        "admin": admin,
        "project": project,
        "other": other,
    }


def task(project, title, **extra):
    return Task.objects.create(project=project, title=title, **extra)


# ------------------------------------------------------------------- flags


def test_task_flags_and_counts(world):
    p = world["project"]
    late = task(p, "late", due_date=TODAY - timedelta(days=2), status=TaskStatus.IN_PROGRESS)
    blocked = task(p, "blocked", status=TaskStatus.BLOCKED, blocked_reason="x")
    review = task(p, "review", status=TaskStatus.REVIEW)
    late_start = task(p, "ls", start_date=TODAY - timedelta(days=1), status=TaskStatus.TODO)
    deviating = task(
        p,
        "dev",
        due_date=TODAY + timedelta(days=9),
        baseline_end_date=TODAY + timedelta(days=5),
        status=TaskStatus.IN_PROGRESS,
    )
    done = task(p, "done", due_date=TODAY - timedelta(days=5), status=TaskStatus.DONE)
    assert task_flags(late) == ["overdue"]
    assert task_flags(blocked) == ["blocked"]
    assert task_flags(review) == ["review"]
    assert task_flags(late_start) == ["late_start", "not_started"]
    assert task_flags(deviating) == ["deviation"]
    assert task_flags(done) == ["done"]  # selesai tidak dianggap overdue
    counts = flag_counts(Task.objects.filter(project=p))
    assert counts["overdue"] == 1 and counts["blocked"] == 1 and counts["review"] == 1
    assert counts["late_start"] == 1 and counts["deviation"] == 1 and counts["done"] == 1


def test_actual_start_is_set_once_when_work_begins(world):
    t = task(world["project"], "T")
    assert t.actual_start is None
    t.status = TaskStatus.IN_PROGRESS
    t.save()
    assert t.actual_start == TODAY
    t.actual_start = TODAY - timedelta(days=3)
    t.save()
    t.status = TaskStatus.DONE
    t.save()
    t.refresh_from_db()
    assert t.actual_start == TODAY - timedelta(days=3) and t.actual_end == TODAY


# ----------------------------------------------------------- progress task


def test_progress_task_scope_and_access(client, world):
    task(world["project"], "milik alpha")
    task(world["other"], "milik beta")
    url = reverse("projects:progress_task")
    client.force_login(world["pm"])
    titles = [r["task"].title for r in client.get(url).context["rows"]]
    assert titles == ["milik alpha"]
    client.force_login(world["admin"])
    assert len(client.get(url).context["rows"]) == 2
    for user in (world["worker"], world["owner"]):
        client.force_login(user)
        assert client.get(url).status_code == 403


def test_progress_task_filters(client, world):
    p = world["project"]
    task(p, "a", assignee=world["worker"], status=TaskStatus.IN_PROGRESS,
         due_date=TODAY - timedelta(days=1))
    task(p, "b", assignee=world["worker2"], status=TaskStatus.REVIEW)
    task(p, "c", status=TaskStatus.BLOCKED, blocked_reason="x")
    client.force_login(world["pm"])
    url = reverse("projects:progress_task")

    def titles(**params):
        return sorted(r["task"].title for r in client.get(url, params).context["rows"])

    assert titles(flag="overdue") == ["a"]
    assert titles(flag="blocked") == ["c"]
    assert titles(status="review") == ["b"]
    assert titles(assignee="none") == ["c"]
    assert titles(assignee=world["worker2"].pk) == ["b"]
    assert titles(project=world["project"].pk) == ["a", "b", "c"]
    assert titles(to=(TODAY - timedelta(days=1)).isoformat()) == ["a"]
    assert titles(status="nonsense", flag="nonsense") == ["a", "b", "c"]


def test_progress_task_is_read_only_for_the_pm(client, world):
    task(world["project"], "a", assignee=world["worker"])
    client.force_login(world["pm"])
    body = client.get(reverse("projects:progress_task")).content.decode()
    assert "task_status" not in body and 'name="progress"' not in body
    assert 'aria-label="Progress task"' in body


# --------------------------------------------------------- project control


def test_control_index_orders_by_exceptions_and_hides_other_projects(client, world):
    task(world["project"], "x", status=TaskStatus.BLOCKED, blocked_reason="r")
    client.force_login(world["pm"])
    response = client.get(reverse("projects:control_index"))
    assert [r["project"].code for r in response.context["rows"]] == ["ALPHA"]
    assert response.context["rows"][0]["counts"]["blocked"] == 1
    client.force_login(world["worker"])
    assert client.get(reverse("projects:control_index")).status_code == 403


def test_project_control_lists_each_task_once_and_checks_ownership(client, world):
    p = world["project"]
    both = task(p, "late and blocked", status=TaskStatus.BLOCKED, blocked_reason="r",
                due_date=TODAY - timedelta(days=1))
    client.force_login(world["pm"])
    url = reverse("projects:project_control", args=[p.pk])
    sections = {s["flag"]: s["rows"] for s in client.get(url).context["sections"]}
    assert [r["task"] for r in sections["overdue"]] == [both]
    assert sections["blocked"] == []  # tidak diulang
    other_url = reverse("projects:project_control", args=[world["other"].pk])
    assert client.get(other_url).status_code == 404
    detail = reverse("projects:project_detail", args=[p.pk])
    # Kontrol menjadi bagian dari tab Aktivitas (U6), hanya untuk yang boleh mengontrol.
    assert "control" in client.get(detail).context["project_sections"]
    client.force_login(world["worker"])
    assert client.get(url).status_code == 403
    assert "control" not in client.get(detail).context["project_sections"]


# ---------------------------------------------------------------- reassign


def test_pm_can_reassign_and_it_is_logged(client, world):
    t = task(world["project"], "T", assignee=world["worker"])
    client.force_login(world["pm"])
    url = reverse("projects:task_reassign", args=[t.pk])
    response = client.post(url, {"assignee": world["worker2"].pk})
    assert response.status_code == 302
    t.refresh_from_db()
    assert t.assignee == world["worker2"]
    event = ActivityEvent.objects.filter(action="task.assigned").latest("pk")
    assert "dipindahkan dari" in event.message and event.active_role == Role.PROJECT_MANAGER


def test_reassign_rejects_non_executors_and_the_pm_themselves(client, world):
    t = task(world["project"], "T", assignee=world["worker"])
    client.force_login(world["pm"])
    url = reverse("projects:task_reassign", args=[t.pk])
    for bad in (world["pm"].pk, world["owner"].pk, 99999, ""):
        client.post(url, {"assignee": bad})
        t.refresh_from_db()
        assert t.assignee == world["worker"]


def test_reassign_needs_permission_and_ownership(client, world):
    t = task(world["project"], "T", assignee=world["worker"])
    url = reverse("projects:task_reassign", args=[t.pk])
    client.force_login(world["other_pm"])
    assert client.post(url, {"assignee": world["worker2"].pk}).status_code == 404
    client.force_login(world["worker"])
    assert client.post(url, {"assignee": world["worker2"].pk}).status_code == 403
    role = RoleDefinition.objects.get(code="pm")
    role.permissions = [p for p in role.permissions if p != "task.reassign"]
    role.save()
    client.force_login(world["pm"])
    assert client.post(url, {"assignee": world["worker2"].pk}).status_code == 403
    assert client.get(url).status_code == 405


# --------------------------------------------------------------- follow up


def test_follow_up_creates_comment_and_notifies_the_assignee(client, world):
    t = task(world["project"], "T", assignee=world["worker"])
    client.force_login(world["pm"])
    url = reverse("projects:task_follow_up", args=[t.pk])
    response = client.post(url, {"message": "Mohon update hari ini"})
    assert response.status_code == 302
    assert TaskComment.objects.get(task=t).content == "Tindak lanjut: Mohon update hari ini"
    note = Notification.objects.get(recipient=world["worker"], verb="task.follow_up")
    assert "Mohon update" in note.body


def test_follow_up_validates_message_and_assignee(client, world):
    assigned = task(world["project"], "A", assignee=world["worker"])
    unassigned = task(world["project"], "B")
    client.force_login(world["pm"])
    client.post(reverse("projects:task_follow_up", args=[assigned.pk]), {"message": "  "})
    client.post(reverse("projects:task_follow_up", args=[unassigned.pk]), {"message": "hi"})
    assert TaskComment.objects.count() == 0 and Notification.objects.count() == 0


def test_follow_up_ignores_unsafe_next_redirect(client, world):
    t = task(world["project"], "T", assignee=world["worker"])
    client.force_login(world["pm"])
    response = client.post(
        reverse("projects:task_follow_up", args=[t.pk]),
        {"message": "hi", "next": "https://evil.example/"},
    )
    assert response.url == reverse("projects:project_control", args=[world["project"].pk])


# --------------------------------------------------------- owner dashboard


def test_owner_dashboard_shows_only_owned_projects(client, world):
    p = world["project"]
    Issue.objects.create(project=p, title="Besar", severity="critical")
    Issue.objects.create(project=p, title="Kecil", severity="low")
    Issue.objects.create(project=world["other"], title="Bukan milik", severity="critical")
    Risk.objects.create(project=p, title="Risiko tinggi", severity="high", status="open")
    Milestone.objects.create(project=p, name="Rilis", date=TODAY + timedelta(days=5))
    client.force_login(world["owner"])
    response = client.get(reverse("projects:dashboard"))
    assert response.status_code == 200
    assert [r["project"].code for r in response.context["rows"]] == ["ALPHA"]
    assert [i.title for i in response.context["issues"]] == ["Besar"]
    assert [r.title for r in response.context["risks"]] == ["Risiko tinggi"]
    assert [m.name for m in response.context["upcoming"]] == ["Rilis"]
    assert b"Ringkasan outcome" in response.content


def test_owner_with_another_role_gets_the_matching_dashboard(client, world):
    both = make_user("dual", Role.PROJECT_MANAGER, Role.OWNER)
    client.force_login(both)
    assert b"Ringkasan outcome" not in client.get(reverse("projects:dashboard")).content
    client.post(reverse("identity:switch_role"), {"role": Role.OWNER})
    assert b"Ringkasan outcome" in client.get(reverse("projects:dashboard")).content


def test_pm_navigation_has_control_pages_but_not_my_tasks(client, world):
    client.force_login(world["pm"])
    body = client.get(reverse("projects:dashboard")).content
    assert b'aria-label="Progress task"' in body and b'aria-label="Kontrol project"' in body
    assert b'aria-label="Pekerjaan saya"' not in body

