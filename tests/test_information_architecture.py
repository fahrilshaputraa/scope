"""U6–U8: tujuh tab project, wizard Buat project, jadwal cepat, checklist Siap berjalan."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from apps.identity.models import Role
from apps.identity.navigation import ROLE_NAV, nav_groups
from apps.identity.roles import assign_roles
from apps.projects.models import LifecycleStatus, Phase, Project, ProjectTemplate
from apps.projects.project_templates import plain_list_structure
from apps.work.models import Task

pytestmark = pytest.mark.django_db
TODAY = timezone.localdate()


def make_user(name, *roles):
    user = User.objects.create_user(name, password="valid-password")
    assign_roles(user, list(roles))
    return user


@pytest.fixture
def world():
    pm = make_user("pm", Role.PROJECT_MANAGER)
    owner = make_user("sponsor", Role.OWNER)
    worker = make_user("worker", Role.MEMBER)
    project = Project.objects.create(
        name="Alpha",
        code="ALPHA",
        manager=pm,
        owner=owner,
        start_date=TODAY,
        target_end_date=TODAY + timedelta(days=60),
    )
    project.members.add(worker)
    return {"pm": pm, "owner": owner, "worker": worker, "project": project}


def wizard_data(world, **extra):
    return {
        "name": "Portal",
        "manager": world["pm"].pk,
        "owner": world["owner"].pk,
        "start_date": TODAY.isoformat(),
        "target_end_date": (TODAY + timedelta(days=10)).isoformat(),
        "lifecycle_status": "planning",
        **extra,
    }


# ------------------------------------------------------------- navigation


def test_project_has_at_most_seven_tabs_and_every_old_url_still_works(client, world):
    client.force_login(world["pm"])
    project = world["project"]
    response = client.get(reverse("projects:project_detail", args=[project.pk]))
    tabs = [key for key, _ in response.context["tabs"]]
    assert len(tabs) <= 7
    assert tabs == ["overview", "work", "progress", "issues", "milestones", "notes", "activity"]
    for name in (
        "projects:project_progress",
        "projects:project_timeline",
        "projects:project_tasks",
        "projects:project_structure",
        "projects:project_issues",
        "projects:project_milestones",
        "projects:project_notes",
        "projects:project_activity",
        "projects:project_history",
        "projects:project_control",
        "projects:project_settings",
        "projects:project_members",
        "projects:project_share",
        "governance:project_deliverables",
        "governance:project_approvals",
    ):
        assert client.get(reverse(name, args=[project.pk])).status_code == 200, name


def test_views_inside_a_tab_use_a_view_switch(client, world):
    client.force_login(world["pm"])
    url = reverse("projects:project_timeline", args=[world["project"].pk])
    response = client.get(url)
    assert response.context["active_group"] == "work"
    keys = [sub["key"] for sub in response.context["subtabs"]]
    assert keys == ["tasks_list", "tasks", "timeline", "structure"]
    body = response.content.decode()
    assert "data-view-switch" in body and 'data-view="timeline" aria-current="page"' in body
    history = client.get(reverse("projects:project_history", args=[world["project"].pk]))
    assert [s["key"] for s in history.context["subtabs"]] == [
        "activity",
        "history",
        "approvals",
        "control",
    ]


def test_header_shows_one_primary_action(client, world):
    client.force_login(world["pm"])
    detail = client.get(reverse("projects:project_detail", args=[world["project"].pk]))
    assert detail.context["header_primary"] is True
    board = client.get(reverse("projects:project_tasks", args=[world["project"].pk]))
    # Board punya tombol Tambah task sendiri; header tidak menggandakannya.
    assert board.context["header_primary"] is False


def test_sidebar_groups_are_small_and_admin_pages_live_in_settings(client, world):
    for role, groups in ROLE_NAV.items():
        assert [title for title, _ in groups] == ["Kerja", "Pantau"], role
        assert sum(len(items) for _, items in groups) <= 8, role
    labels = [i["label"] for g in nav_groups("admin", "/") for i in g["items"]]
    assert "Pengguna" not in labels and "Jejak audit" not in labels
    admin = make_user("adm", Role.ADMIN)
    client.force_login(admin)
    body = client.get(reverse("identity:settings")).content.decode()
    for label in ("Pengguna", "Role &amp; permission", "Template", "Jejak audit", "Integrasi"):
        assert label in body, label
    assert client.get(reverse("projects:audit_trail")).status_code == 200


def test_settings_page_is_for_project_managers_only(client, world):
    url = reverse("projects:project_settings", args=[world["project"].pk])
    client.force_login(world["worker"])
    assert client.get(url).status_code == 403
    client.force_login(world["pm"])
    body = client.get(url).content.decode()
    assert "data-project-settings" in body and "Tautan publik" in body


def test_quick_actions_offer_project_shortcuts(client, world):
    client.force_login(world["pm"])
    response = client.get(reverse("projects:project_detail", args=[world["project"].pk]))
    labels = {a["label"] for a in response.context["quick_actions"]}
    assert {"Buat task cepat", "Tempel daftar task", "Persetujuan & perubahan"} <= labels


# ----------------------------------------------------------------- wizard


def test_wizard_pastes_a_task_list_and_extends_the_target_date(client, world):
    client.force_login(world["pm"])
    response = client.post(
        reverse("projects:project_create"),
        wizard_data(world, source="paste", plan_text="Analisis | 3\nDesain | 5\nBangun | 10"),
    )
    project = Project.objects.get(name="Portal")
    assert response.url == reverse("projects:project_timeline", args=[project.pk])
    tasks = list(project.tasks.order_by("start_date"))
    assert [t.title for t in tasks] == ["Analisis", "Desain", "Bangun"]
    assert tasks[1].start_date == tasks[0].due_date + timedelta(days=1)
    # Rencana 18 hari melewati target awal 10 hari: tanggal akhir ikut mundur.
    assert project.target_end_date == tasks[-1].due_date == TODAY + timedelta(days=17)


def test_wizard_outline_creates_phases(client, world):
    structure = plain_list_structure("Persiapan\n- Kickoff | 1\nEksekusi\n- Bangun | 4")
    assert [p["name"] for p in structure["phases"]] == ["Persiapan", "Eksekusi"]
    client.force_login(world["pm"])
    client.post(
        reverse("projects:project_create"),
        wizard_data(
            world, source="paste", plan_text="Persiapan\n- Kickoff | 1\nEksekusi\n- Bangun"
        ),
    )
    project = Project.objects.get(name="Portal")
    assert list(project.phases.values_list("name", flat=True)) == ["Persiapan", "Eksekusi"]


def test_wizard_validates_the_chosen_source(client, world):
    client.force_login(world["pm"])
    response = client.post(reverse("projects:project_create"), wizard_data(world, source="paste"))
    assert response.status_code == 200 and "plan_text" in response.context["form"].errors
    response = client.post(
        reverse("projects:project_create"), wizard_data(world, source="template")
    )
    assert "template" in response.context["form"].errors
    assert not Project.objects.filter(name="Portal").exists()


def test_wizard_ai_source_continues_to_the_import(client, world):
    client.force_login(world["pm"])
    response = client.post(reverse("projects:project_create"), wizard_data(world, source="ai"))
    project = Project.objects.get(name="Portal")
    assert response.url == reverse("projects:plan_import", args=[project.pk])


def test_wizard_defaults_owner_and_end_date(client, world):
    solo_owner = make_user("pm_owner", Role.PROJECT_MANAGER, Role.OWNER)
    client.force_login(solo_owner)
    form = client.get(reverse("projects:project_create")).context["form"]
    assert form.initial["owner"] == solo_owner
    assert form.initial["target_end_date"] == TODAY + timedelta(days=30)


# --------------------------------------------------------------- schedule


def test_empty_schedule_offers_fast_starts(client, world):
    client.force_login(world["pm"])
    body = client.get(reverse("projects:project_timeline", args=[world["project"].pk]))
    text = body.content.decode()
    assert "data-schedule-empty" in text
    for label in ("Tempel daftar task", "Mulai dari template", "Import rencana AI", "Tambah phase"):
        assert label in text, label


def test_paste_form_appends_after_the_last_task(client, world):
    project = world["project"]
    Task.objects.create(project=project, title="A", start_date=TODAY, due_date=TODAY)
    client.force_login(world["pm"])
    url = reverse("projects:project_paste_tasks", args=[project.pk])
    assert client.get(url).context["form"].initial["start_date"] == TODAY + timedelta(days=1)
    client.post(
        url, {"plan_text": "B | 2\nC", "start_date": (TODAY + timedelta(days=1)).isoformat()}
    )
    b, c = project.tasks.get(title="B"), project.tasks.get(title="C")
    assert (b.start_date, b.due_date) == (TODAY + timedelta(days=1), TODAY + timedelta(days=2))
    assert c.start_date == TODAY + timedelta(days=3)


def test_apply_template_only_on_an_empty_schedule(client, world):
    template = ProjectTemplate.objects.create(
        name="Std",
        structure_config={
            "phases": [
                {
                    "name": "Fase",
                    "offset": 0,
                    "duration": 3,
                    "packages": [],
                    "tasks": [{"title": "T1", "offset": 0, "duration": 3, "subtasks": []}],
                }
            ],
            "tasks": [],
            "milestones": [],
        },
    )
    project = world["project"]
    client.force_login(world["pm"])
    url = reverse("projects:project_apply_template", args=[project.pk])
    client.post(url, {"template": template.pk})
    assert list(project.tasks.values_list("title", flat=True)) == ["T1"]
    assert Phase.objects.filter(project=project, name="Fase").exists()
    client.post(url, {"template": template.pk})
    assert project.tasks.count() == 1  # tidak ditimpa


def test_task_list_view_filters_and_has_empty_state(client, world):
    project = world["project"]
    client.force_login(world["pm"])
    url = reverse("projects:project_tasks", args=[project.pk]) + "?view=list"
    assert "Belum ada task di project ini" in client.get(url).content.decode()
    Task.objects.create(project=project, title="Late", due_date=TODAY - timedelta(days=2))
    Task.objects.create(project=project, title="Fine", due_date=TODAY + timedelta(days=2))
    rows = client.get(url + "&filter=overdue").context["task_rows"]
    assert [t.title for t in rows] == ["Late"]


# -------------------------------------------------------------- readiness


def test_readiness_checklist_baseline_and_start(client, world):
    project = world["project"]
    project.lifecycle_status = LifecycleStatus.PLANNING
    project.save()
    client.force_login(world["pm"])
    detail = reverse("projects:project_detail", args=[project.pk])
    readiness = client.get(detail).context["readiness"]
    assert {s["key"]: s["done"] for s in readiness["steps"]} == {
        "owner": True,
        "manager": True,
        "tasks": False,
        "baseline": False,
    }
    Task.objects.create(project=project, title="A", start_date=TODAY, due_date=TODAY)
    response = client.post(
        reverse("projects:capture_baseline", args=[project.pk]), {"next": detail}
    )
    assert response.url == detail  # kembali ke Ringkasan
    readiness = client.get(detail).context["readiness"]
    assert readiness["ready"] and readiness["can_start"]
    client.post(reverse("projects:project_start", args=[project.pk]))
    project.refresh_from_db()
    assert project.lifecycle_status == LifecycleStatus.IN_PROGRESS
    assert client.get(detail).context["readiness"] is None


def test_start_is_refused_until_requirements_are_met(client, world):
    project = world["project"]
    project.lifecycle_status = LifecycleStatus.PLANNING
    project.save()
    client.force_login(world["pm"])
    client.post(reverse("projects:project_start", args=[project.pk]))
    project.refresh_from_db()
    assert project.lifecycle_status == LifecycleStatus.PLANNING
    client.force_login(world["worker"])
    client.post(reverse("projects:project_start", args=[project.pk]))
    project.refresh_from_db()
    assert project.lifecycle_status == LifecycleStatus.PLANNING
