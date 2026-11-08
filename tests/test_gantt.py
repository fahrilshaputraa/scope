"""Gantt endpoints (roadmap G4-G7) and quick planning: create, paste, duplicate, sequence."""

import json
from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from apps.identity.models import Role
from apps.identity.roles import assign_roles
from apps.projects.models import ActivityEvent, Milestone, Phase, Project
from apps.work.gantt import parse_lines, portfolio_payload, project_payload
from apps.work.models import Task, TaskStatus

pytestmark = pytest.mark.django_db

D = date(2026, 10, 1)


def day(n):
    return D + timedelta(days=n)


def user(name, *roles, **extra):
    account = User.objects.create_user(name, password="valid-password", **extra)
    assign_roles(account, list(roles))
    return account


@pytest.fixture
def plan():
    pm = user("pm", Role.PROJECT_MANAGER)
    worker = user("rina", Role.MEMBER, first_name="Rina", last_name="Saputri")
    management = user("boss", Role.MANAGEMENT)
    admin = user("adm", Role.ADMIN)
    stranger = user("stranger", Role.MEMBER)
    project = Project.objects.create(
        name="Alpha", code="ALPHA", manager=pm, start_date=D, target_end_date=day(60)
    )
    project.members.add(worker)
    phase = Phase.objects.create(project=project, name="Build", sequence=1)
    a = Task.objects.create(
        project=project, phase=phase, title="A", start_date=day(0), due_date=day(4)
    )
    b = Task.objects.create(
        project=project, phase=phase, title="B", start_date=day(5), due_date=day(9)
    )
    b.dependencies.add(a)
    return {
        "pm": pm,
        "worker": worker,
        "management": management,
        "admin": admin,
        "stranger": stranger,
        "project": project,
        "phase": phase,
        "a": a,
        "b": b,
    }


def move(client, task, start, end, **extra):
    body = f"start={start.isoformat()}&end={end.isoformat()}"
    for key, value in extra.items():
        body += f"&{key}={value}"
    return client.post(
        reverse("work:task_dates", args=[task.pk]),
        body,
        content_type="application/x-www-form-urlencoded",
    )


def post(client, name, project, payload, *args):
    return client.post(
        reverse(name, args=[project.pk, *args]),
        json.dumps(payload),
        content_type="application/json",
    )


# ----------------------------------------------------------- permissions ---


def test_only_project_pm_or_admin_can_change_schedule(client, plan):
    a, project = plan["a"], plan["project"]
    a.assignee = plan["worker"]
    a.save()
    for account, expected in (
        (plan["worker"], 403),
        (plan["management"], 403),
        (plan["stranger"], 404),
    ):
        client.force_login(account)
        response = move(client, a, day(1), day(5))
        assert response.status_code == expected, account
        assert response.json()["ok"] is False
        create = post(client, "work:gantt_create", project, {"items": [{"title": "X"}]})
        assert create.status_code == expected
        assert (
            post(client, "work:gantt_sequence", project, {"ids": [a.pk, plan["b"].pk]}).status_code
            == expected
        )
    assert not Task.objects.filter(title="X").exists()
    a.refresh_from_db()
    assert a.start_date == day(0)
    client.force_login(plan["admin"])
    assert move(client, a, day(-2), day(2)).status_code == 200


# ------------------------------------------------------------- task_dates ---


def test_move_saves_current_schedule_only_and_logs_activity(client, plan):
    a = plan["a"]
    a.baseline_start_date, a.baseline_end_date = day(0), day(4)
    a.save()
    client.force_login(plan["pm"])
    response = move(client, a, day(-3), day(1))
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] and data["changes"][0]["old_start"] == day(0).isoformat()
    a.refresh_from_db()
    assert (a.start_date, a.due_date) == (day(-3), day(1))
    assert (a.baseline_start_date, a.baseline_end_date) == (day(0), day(4))
    event = ActivityEvent.objects.filter(project=plan["project"], action="timeline.changed").latest(
        "pk"
    )
    assert '"A"' in event.message and "→" in event.message


@pytest.mark.parametrize(
    "start,end",
    [("2026-10-10", "2026-10-01"), ("bad", "2026-10-02"), ("", ""), ("2026-02-30", "2026-03-01")],
)
def test_dates_must_be_valid_and_chronological(client, plan, start, end):
    client.force_login(plan["pm"])
    response = client.post(
        reverse("work:task_dates", args=[plan["a"].pk]), {"start": start, "end": end}
    )
    assert response.status_code == 400
    assert response.json()["code"] == "order" and response.json()["error"]


def test_done_task_is_locked(client, plan):
    a = plan["a"]
    a.status = TaskStatus.DONE
    a.save()
    client.force_login(plan["pm"])
    response = move(client, a, day(1), day(5))
    assert response.status_code == 400 and response.json()["code"] == "done"
    a.refresh_from_db()
    assert a.start_date == day(0)


def test_detail_must_stay_inside_activity_and_activity_must_cover_details(client, plan):
    a = plan["a"]
    child = Task.objects.create(
        project=plan["project"], parent_task=a, title="A.1", start_date=day(1), due_date=day(3)
    )
    client.force_login(plan["pm"])
    response = move(client, child, day(3), day(6))
    assert response.status_code == 400 and response.json()["code"] == "parent"
    response = move(client, a, day(2), day(4))  # resize would exclude the detail
    assert response.status_code == 400 and response.json()["code"] == "children"
    # A pure move carries the details along.
    b = plan["b"]
    b.dependencies.clear()
    response = move(client, a, day(-10), day(-6))
    assert response.status_code == 200
    child.refresh_from_db()
    assert (child.start_date, child.due_date) == (day(-9), day(-7))
    assert {c["id"] for c in response.json()["changes"]} == {a.pk, child.pk}


def test_dependency_blocks_starting_before_predecessor_finishes(client, plan):
    client.force_login(plan["pm"])
    response = move(client, plan["b"], day(3), day(8))
    assert response.status_code == 400
    assert response.json()["code"] == "dependency" and '"A"' in response.json()["error"]


def test_successor_conflict_needs_confirmation_then_shifts_with_preview(client, plan):
    a, b = plan["a"], plan["b"]
    c = Task.objects.create(
        project=plan["project"], title="C", start_date=day(10), due_date=day(11)
    )
    c.dependencies.add(b)
    client.force_login(plan["pm"])
    response = move(client, a, day(0), day(6))
    assert response.status_code == 409
    data = response.json()
    assert data["code"] == "successor_conflict"
    assert {row["id"] for row in data["impact"]} == {a.pk, b.pk, c.pk}
    b.refresh_from_db()
    assert b.start_date == day(5)  # nothing saved
    preview = move(client, a, day(0), day(6), shift_successors="true", preview="true")
    assert preview.status_code == 200 and preview.json()["preview"]
    b.refresh_from_db()
    assert b.start_date == day(5)
    response = move(client, a, day(0), day(6), shift_successors="true")
    assert response.status_code == 200
    b.refresh_from_db()
    c.refresh_from_db()
    assert (b.start_date, b.due_date) == (day(7), day(11))  # duration kept
    assert (c.start_date, c.due_date) == (day(12), day(13))


def test_shift_refuses_to_move_finished_successor(client, plan):
    b = plan["b"]
    b.status = TaskStatus.DONE
    b.save()
    client.force_login(plan["pm"])
    response = move(client, plan["a"], day(0), day(7), shift_successors="true")
    assert response.status_code == 400 and response.json()["code"] == "done"


def test_bulk_dates_restores_previous_schedule_for_undo(client, plan):
    a = plan["a"]
    client.force_login(plan["pm"])
    changes = move(client, a, day(-4), day(0)).json()["changes"]
    undo = [{"id": c["id"], "start": c["old_start"], "end": c["old_end"]} for c in changes]
    response = post(
        client, "work:gantt_bulk_dates", plan["project"], {"changes": undo, "reason": "undo"}
    )
    assert response.status_code == 200
    a.refresh_from_db()
    assert (a.start_date, a.due_date) == (day(0), day(4))
    assert ActivityEvent.objects.filter(message__startswith="Urungkan jadwal").exists()
    bad = post(client, "work:gantt_bulk_dates", plan["project"], {"changes": [{"id": 999999}]})
    assert bad.status_code == 400


# ----------------------------------------------------------- dependencies ---


def test_dependency_create_remove_and_cycle_rules(client, plan):
    a, b, project = plan["a"], plan["b"], plan["project"]
    c = Task.objects.create(project=project, title="C", start_date=day(2), due_date=day(3))
    client.force_login(plan["pm"])
    url = "work:gantt_dependency"
    cycle = post(client, url, project, {"from": b.pk, "to": a.pk})
    assert cycle.status_code == 400 and "siklus" in cycle.json()["error"]
    assert post(client, url, project, {"from": a.pk, "to": a.pk}).status_code == 400
    assert post(client, url, project, {"from": a.pk, "to": b.pk}).status_code == 400  # duplicate
    added = post(client, url, project, {"from": b.pk, "to": c.pk})
    assert added.status_code == 200 and added.json()["warning"]  # C starts before B ends
    assert c.dependencies.filter(pk=b.pk).exists()
    assert (
        post(client, url, project, {"from": a.pk, "to": c.pk, "action": "remove"}).status_code
        == 400
    )
    removed = post(client, url, project, {"from": b.pk, "to": c.pk, "action": "remove"})
    assert removed.status_code == 200 and not c.dependencies.exists()
    other = Project.objects.create(
        name="Other", code="OTH", manager=plan["pm"], start_date=D, target_end_date=day(5)
    )
    foreign = Task.objects.create(project=other, title="Foreign")
    assert post(client, url, project, {"from": a.pk, "to": foreign.pk}).status_code == 404


def test_running_task_cannot_get_unfinished_prerequisite(client, plan):
    a, b, project = plan["a"], plan["b"], plan["project"]
    b.dependencies.clear()
    a.status = TaskStatus.IN_PROGRESS
    a.save()
    client.force_login(plan["pm"])
    response = post(client, "work:gantt_dependency", project, {"from": b.pk, "to": a.pk})
    assert response.status_code == 400 and "berjalan" in response.json()["error"]


# ------------------------------------------------------------ quick create ---


def test_drag_create_single_task_in_phase(client, plan):
    client.force_login(plan["pm"])
    response = post(
        client,
        "work:gantt_create",
        plan["project"],
        {
            "items": [{"title": "Desain", "start": "2026-10-20", "end": "2026-10-22"}],
            "phase": plan["phase"].pk,
        },
    )
    assert response.status_code == 201
    task = Task.objects.get(pk=response.json()["ids"][0])
    assert (task.title, task.phase, task.start_date, task.due_date) == (
        "Desain",
        plan["phase"],
        date(2026, 10, 20),
        date(2026, 10, 22),
    )
    assert task.baseline_start_date is None
    assert ActivityEvent.objects.filter(action="task.created", message__contains="Desain").exists()


def test_paste_list_creates_many_tasks_sequentially_with_optional_columns(client, plan):
    client.force_login(plan["pm"])
    text = "\n".join(
        [
            "Analisis kebutuhan",
            "- Desain UI | 2026-11-10 | 2026-11-14 | rina",
            "",
            "Pengujian | 17/11/2026 | | Rina Saputri",
            "Rilis",
        ]
    )
    response = post(
        client,
        "work:gantt_create",
        plan["project"],
        {"text": text, "phase": plan["phase"].pk, "start": "2026-11-01", "duration": 2},
    )
    assert response.status_code == 201, response.json()
    tasks = [Task.objects.get(pk=pk) for pk in response.json()["ids"]]
    assert [t.title for t in tasks] == ["Analisis kebutuhan", "Desain UI", "Pengujian", "Rilis"]
    assert (tasks[0].start_date, tasks[0].due_date) == (date(2026, 11, 1), date(2026, 11, 2))
    assert (tasks[1].start_date, tasks[1].due_date) == (date(2026, 11, 10), date(2026, 11, 14))
    assert (tasks[2].start_date, tasks[2].due_date) == (date(2026, 11, 17), date(2026, 11, 18))
    assert tasks[3].start_date == date(2026, 11, 19)  # continues after the previous line
    assert tasks[1].assignee == plan["worker"] and tasks[2].assignee == plan["worker"]
    assert all(t.phase == plan["phase"] for t in tasks)
    assert ActivityEvent.objects.filter(message="4 task dibuat sekaligus dari Gantt.").exists()


@pytest.mark.parametrize(
    "text,fragment",
    [
        ("Baik\nBuruk | 31/02/2026", "Baris 2"),
        ("Satu\nDua | 2026-11-10 | 2026-11-01", "sebelum tanggal mulai"),
        ("Satu\nDua | | | pm", "bukan anggota pelaksana"),
        ("   \n\n", "minimal satu"),
    ],
)
def test_paste_list_rejects_whole_batch_with_line_message(client, plan, text, fragment):
    client.force_login(plan["pm"])
    before = Task.objects.count()
    response = post(client, "work:gantt_create", plan["project"], {"text": text})
    assert response.status_code == 400 and fragment in response.json()["error"]
    assert Task.objects.count() == before


def test_details_created_inside_activity_range(client, plan):
    client.force_login(plan["pm"])
    parent = plan["a"]
    ok = post(
        client,
        "work:gantt_create",
        plan["project"],
        {"text": "Satu\nDua", "parent": parent.pk, "duration": 2},
    )
    assert ok.status_code == 201
    kids = list(parent.subtasks.order_by("pk"))
    assert [(k.start_date, k.due_date) for k in kids] == [(day(0), day(1)), (day(2), day(3))]
    too_long = post(
        client,
        "work:gantt_create",
        plan["project"],
        {"text": "Tiga", "parent": parent.pk, "start": day(3).isoformat(), "duration": 5},
    )
    assert too_long.status_code == 400 and too_long.json()["code"] == "parent"


def test_paste_limit(client, plan):
    client.force_login(plan["pm"])
    text = "\n".join(f"Task {n}" for n in range(201))
    assert post(client, "work:gantt_create", plan["project"], {"text": text}).status_code == 400


def test_parse_lines_accepts_tabs_and_semicolons():
    rows = parse_lines("Satu\tmulai\nDua; 2026-01-01")
    assert [r["title"] for r in rows] == ["Satu", "Dua"]
    assert rows[1]["start"] == "2026-01-01" and rows[1]["line"] == 2


def test_undo_create_removes_only_untouched_new_tasks(client, plan):
    client.force_login(plan["pm"])
    ids = post(client, "work:gantt_create", plan["project"], {"text": "X\nY"}).json()["ids"]
    response = post(client, "work:gantt_undo_create", plan["project"], {"ids": ids})
    assert response.status_code == 200 and response.json()["removed"] == 2
    assert not Task.objects.filter(pk__in=ids).exists()
    old = plan["a"]
    Task.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=2))
    assert (
        post(client, "work:gantt_undo_create", plan["project"], {"ids": [old.pk]}).status_code
        == 400
    )
    assert Task.objects.filter(pk=old.pk).exists()


# --------------------------------------------------- duplicate / sequence ---


def test_duplicate_copies_details_and_internal_dependencies_after_the_range(client, plan):
    a, b = plan["a"], plan["b"]
    a.assignee = plan["worker"]
    a.progress = 40
    a.status = TaskStatus.IN_PROGRESS
    a.save()
    Task.objects.create(
        project=plan["project"], parent_task=a, title="A.1", start_date=day(1), due_date=day(2)
    )
    client.force_login(plan["pm"])
    response = post(client, "work:gantt_duplicate", plan["project"], {"ids": [a.pk, b.pk]})
    assert response.status_code == 201
    copies = {t.title: t for t in Task.objects.filter(pk__in=response.json()["ids"])}
    assert set(copies) == {"A (salinan)", "B (salinan)", "A.1"}
    offset = timedelta(days=10)  # selection spans day 0..9
    assert copies["A (salinan)"].start_date == a.start_date + offset
    assert copies["A.1"].parent_task == copies["A (salinan)"]
    assert copies["A (salinan)"].assignee == plan["worker"]
    assert copies["A (salinan)"].progress == 0 and copies["A (salinan)"].status == TaskStatus.TODO
    assert list(copies["B (salinan)"].dependencies.all()) == [copies["A (salinan)"]]
    assert copies["A (salinan)"].baseline_start_date is None


def test_sequence_chains_selected_tasks_keeping_durations(client, plan):
    project = plan["project"]
    x = Task.objects.create(project=project, title="X", start_date=day(20), due_date=day(22))
    y = Task.objects.create(project=project, title="Y")
    z = Task.objects.create(project=project, title="Z", start_date=day(1), due_date=day(1))
    client.force_login(plan["pm"])
    payload = {"ids": [x.pk, y.pk, z.pk], "start": day(30).isoformat(), "duration": 2, "link": True}
    preview = post(client, "work:gantt_sequence", project, {**payload, "preview": True})
    assert preview.status_code == 200 and len(preview.json()["impact"]) == 3
    assert not y.dependencies.exists()
    response = post(client, "work:gantt_sequence", project, payload)
    assert response.status_code == 200
    for t in (x, y, z):
        t.refresh_from_db()
    assert (x.start_date, x.due_date) == (day(30), day(32))
    assert (y.start_date, y.due_date) == (day(33), day(34))
    assert (z.start_date, z.due_date) == (day(35), day(35))
    assert list(y.dependencies.all()) == [x] and list(z.dependencies.all()) == [y]
    assert len(response.json()["links"]) == 2


def test_sequence_rejects_done_tasks_and_cycles(client, plan):
    a, b, project = plan["a"], plan["b"], plan["project"]
    client.force_login(plan["pm"])
    cycle = post(client, "work:gantt_sequence", project, {"ids": [b.pk, a.pk], "link": True})
    assert cycle.status_code == 400 and "siklus" in cycle.json()["error"]
    assert post(client, "work:gantt_sequence", project, {"ids": [a.pk]}).status_code == 400
    a.status = TaskStatus.DONE
    a.save()
    done = post(client, "work:gantt_sequence", project, {"ids": [a.pk, b.pk]})
    assert done.status_code == 400 and done.json()["code"] == "done"


# ------------------------------------------------------------- inline edit ---


def test_inline_title_and_assignee_edit(client, plan):
    a, project = plan["a"], plan["project"]
    client.force_login(plan["pm"])
    url = "work:gantt_patch"
    assert post(client, url, project, {"title": "  "}, a.pk).status_code == 400
    response = post(client, url, project, {"title": "A baru", "assignee": plan["worker"].pk}, a.pk)
    assert response.status_code == 200
    a.refresh_from_db()
    assert a.title == "A baru" and a.assignee == plan["worker"]
    assert post(client, url, project, {"assignee": plan["pm"].pk}, a.pk).status_code == 400
    assert post(client, url, project, {"assignee": None}, a.pk).status_code == 200
    a.refresh_from_db()
    assert a.assignee is None
    client.force_login(plan["worker"])
    assert post(client, url, project, {"title": "Hack"}, a.pk).status_code == 403


# ----------------------------------------------------------------- payload ---


def test_payload_tree_baseline_links_and_public_privacy(client, plan):
    a = plan["a"]
    a.assignee = plan["worker"]
    a.baseline_start_date, a.baseline_end_date = day(0), day(2)
    a.save()
    Milestone.objects.create(project=plan["project"], name="Go live", date=day(20))
    data = project_payload(plan["project"], plan["pm"])
    kinds = [row["kind"] for row in data["rows"]]
    assert kinds[:3] == ["phase", "task", "task"] and "milestone" in kinds
    row = next(r for r in data["rows"] if r.get("task") == a.pk)
    assert row["baseEnd"] == day(2).isoformat() and row["assigneeName"] == "Rina Saputri"
    assert {"from": a.pk, "to": plan["b"].pk} in data["links"]
    assert data["editable"] and "dates" in data["urls"]
    public = project_payload(plan["project"], public=True, titles={a.pk: "Task 1"})
    text = json.dumps(public)
    assert "Rina" not in text and "rina" not in text and "urls" not in public
    assert any(r.get("title") == "Task 1" for r in public["rows"])
    assert not project_payload(plan["project"], plan["worker"])["editable"]
    portfolio = portfolio_payload([plan["project"]])
    assert portfolio["rows"][0]["kind"] == "project" and not portfolio["editable"]


def test_gantt_data_endpoint_and_pages_render(client, plan):
    client.force_login(plan["pm"])
    response = client.get(reverse("work:gantt_data", args=[plan["project"].pk]))
    assert response.status_code == 200 and response.json()["gantt"]["mode"] == "project"
    page = client.get(reverse("projects:project_timeline", args=[plan["project"].pk]))
    assert b'data-gantt-source="project-gantt"' in page.content and b"js/gantt.js" in page.content
    portfolio = client.get(reverse("projects:timeline_global"))
    assert b'data-gantt-source="portfolio-gantt"' in portfolio.content
    client.force_login(plan["stranger"])
    assert client.get(reverse("work:gantt_data", args=[plan["project"].pk])).status_code == 404
