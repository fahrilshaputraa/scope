"""Fase 7: risk lengkap, work package, metode progress, bobot 100%, template, field tambahan."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from apps.identity.models import Role
from apps.identity.roles import assign_roles
from apps.projects.exports import export_rows
from apps.projects.models import (
    Phase,
    Project,
    ProjectTemplate,
    Risk,
    WeightMode,
    WorkPackage,
    risk_level,
)
from apps.projects.project_templates import (
    apply_template,
    outline_to_structure,
    parse_field_definitions,
    structure_to_outline,
)
from apps.projects.services import actual_progress
from apps.work import weights
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
    admin = make_user("adm", Role.ADMIN)
    project = Project.objects.create(
        name="Alpha",
        code="ALPHA",
        manager=pm,
        start_date=TODAY,
        target_end_date=TODAY + timedelta(days=60),
    )
    project.members.add(worker)
    return {"pm": pm, "worker": worker, "admin": admin, "project": project}


# -------------------------------------------------------------------- risk


def test_risk_score_and_level_from_probability_and_impact(world):
    risk = Risk.objects.create(project=world["project"], title="Vendor", probability=4, impact=5)
    assert risk.score == 20 and risk.severity == "critical"
    risk.probability = 1
    risk.save()
    assert risk.score == 5 and risk.severity == "medium"
    assert [risk_level(n) for n in (4, 9, 16, 25)] == ["low", "medium", "high", "critical"]


def test_legacy_severity_maps_to_same_level(world):
    for severity in ("low", "medium", "high", "critical"):
        risk = Risk.objects.create(project=world["project"], title=severity, severity=severity)
        assert risk.severity == severity


def test_risk_form_requires_owner_mitigation_review_date(world, client):
    client.force_login(world["pm"])
    url = reverse("projects:risk_create", args=[world["project"].pk])
    response = client.post(url, {"title": "Data", "probability": 3, "impact": 3})
    errors = response.context["form"].errors
    assert {"owner", "mitigation", "review_date"} <= set(errors)
    client.post(
        url,
        {
            "title": "Data",
            "probability": 3,
            "impact": 4,
            "owner": world["worker"].pk,
            "mitigation": "Backup harian",
            "review_date": (TODAY + timedelta(days=7)).isoformat(),
            "status": "open",
        },
    )
    risk = Risk.objects.get()
    assert risk.score == 12 and risk.severity == "high"


def test_risk_converts_to_issue(world, client):
    risk = Risk.objects.create(
        project=world["project"], title="Server down", probability=5, impact=5, owner=world["pm"]
    )
    client.force_login(world["pm"])
    client.post(reverse("projects:risk_convert", args=[world["project"].pk, risk.pk]))
    risk.refresh_from_db()
    issue = Issue.objects.get()
    assert risk.status == "converted" and risk.issue == issue
    assert issue.severity == "critical" and issue.owner == world["pm"]
    assert risk.project.revisions.filter(entity="risk", object_id=risk.pk).exists()


# ------------------------------------------------------------ work package


def test_work_package_between_phase_and_task(world, client):
    project = world["project"]
    phase = Phase.objects.create(project=project, name="Build", sequence=1)
    package = WorkPackage.objects.create(project=project, phase=phase, name="Backend")
    task = Task.objects.create(project=project, title="API", work_package=package)
    detail = Task.objects.create(project=project, title="Endpoint", parent_task=task)
    task.refresh_from_db()
    detail.refresh_from_db()
    assert task.phase == phase and detail.work_package == package
    client.force_login(world["pm"])
    page = client.get(reverse("projects:project_structure", args=[project.pk])).content.decode()
    assert page.index("Build") < page.index("Backend") < page.index("API") < page.index("Endpoint")


# ---------------------------------------------------------- progress method


def test_three_progress_methods(world):
    project = world["project"]
    project.progress_config = {"in_progress": 40}
    project.save()
    manual = Task.objects.create(project=project, title="Manual", progress=30)
    by_status = Task.objects.create(
        project=project, title="Status", progress_method="status", status=TaskStatus.IN_PROGRESS
    )
    assert manual.progress == 30
    assert by_status.progress == 40
    by_status.status = TaskStatus.REVIEW
    by_status.save()
    assert by_status.progress == 80
    by_status.status, by_status.blocked_reason = TaskStatus.BLOCKED, "Menunggu"
    by_status.save()
    assert by_status.progress == 80  # Blocked mempertahankan progress terakhir
    parent = Task.objects.create(project=project, title="Induk", progress=90)
    Task.objects.create(project=project, title="A", parent_task=parent, progress=50)
    Task.objects.create(project=project, title="B", parent_task=parent, status="done")
    parent.refresh_from_db()
    assert parent.progress_method == "subtask"
    assert parent.display_progress == Decimal("75.00")  # bukan 90 manual


def test_status_method_rejects_manual_progress_api(world, client):
    task = Task.objects.create(
        project=world["project"], title="S", progress_method="status", assignee=world["worker"]
    )
    client.force_login(world["worker"])
    response = client.post(reverse("work:task_progress", args=[task.pk]), {"progress": "60"})
    assert response.status_code == 400


# ------------------------------------------------------------------ weights


def test_equal_and_normalized_weights_total_100(world):
    project = world["project"]
    tasks = [
        Task.objects.create(project=project, title=n, weight=w)
        for n, w in [("a", 1), ("b", 1), ("c", 2)]
    ]
    weights.normalize(project, None, world["pm"])
    values = [t.weight for t in weights.group_tasks(project)]
    assert values == [Decimal("25.00"), Decimal("25.00"), Decimal("50.00")]
    weights.equalize(project, None, world["pm"])
    values = [t.weight for t in weights.group_tasks(project)]
    assert sum(values) == 100 and values == [Decimal("33.33"), Decimal("33.33"), Decimal("33.34")]
    assert len(tasks) == 3


def test_manual_weights_must_total_100(world, client):
    project = world["project"]
    a = Task.objects.create(project=project, title="a")
    b = Task.objects.create(project=project, title="b")
    client.force_login(world["pm"])
    url = reverse("projects:weights_edit", args=[project.pk])
    bad = client.post(url, {f"w{a.pk}": "50", f"w{b.pk}": "40"})
    assert bad.status_code == 200 and "harus 100%" in bad.content.decode()
    client.post(url, {f"w{a.pk}": "70", f"w{b.pk}": "30"})
    a.refresh_from_db()
    b.refresh_from_db()
    assert a.weight == 70
    b.progress = 100
    b.save()
    project.refresh_from_db()
    assert actual_progress(project) == Decimal("30.00")


def test_auto_mode_rebalances_siblings(world):
    project = world["project"]
    project.weight_mode = WeightMode.AUTO
    project.save()
    first = Task.objects.create(project=project, title="1")
    first.refresh_from_db()
    assert first.weight == 100
    second = Task.objects.create(project=project, title="2")
    assert [t.weight for t in weights.group_tasks(project)] == [Decimal("50.00")] * 2
    second.archive(world["pm"])
    first.refresh_from_db()
    assert first.weight == 100


# ---------------------------------------------------------------- templates


OUTLINE = """Perencanaan
- Kickoff | 2
- Analisis | 3
-- Wawancara | 1
Pengembangan
+ Backend
- API | 5
* Go-live | 20"""


def test_outline_round_trip():
    structure = outline_to_structure(OUTLINE)
    assert [p["name"] for p in structure["phases"]] == ["Perencanaan", "Pengembangan"]
    assert structure["phases"][1]["tasks"][0]["package"] == "Backend"
    assert structure["phases"][1]["tasks"][0]["offset"] == 5
    assert structure_to_outline(structure) == OUTLINE


def test_create_project_from_template_and_template_changes_do_not_leak(world, client):
    template = ProjectTemplate.objects.create(
        name="Implementasi",
        project_type="implementation",
        structure_config=outline_to_structure(OUTLINE),
        approval_config=[{"type": "task", "enabled": True, "mode": "sequential"}],
        custom_fields=[{"key": "kontrak", "label": "Kontrak", "type": "text"}],
    )
    owner = make_user("sponsor", Role.OWNER)
    client.force_login(world["pm"])
    response = client.post(
        reverse("projects:project_create"),
        {
            "name": "Portal",
            "template": template.pk,
            "owner": owner.pk,
            "manager": world["pm"].pk,
            "start_date": TODAY.isoformat(),
            "target_end_date": (TODAY + timedelta(days=30)).isoformat(),
            "lifecycle_status": "planning",
        },
    )
    assert response.status_code == 302
    project = Project.objects.get(name="Portal")
    assert project.project_type == "implementation" and project.template == template
    assert project.phases.count() == 2 and project.work_packages.count() == 1
    assert project.tasks.filter(parent_task__isnull=True).count() == 3
    assert project.milestones.get().date == TODAY + timedelta(days=20)
    api = project.tasks.get(title="API")
    assert api.start_date == TODAY + timedelta(days=5) and api.work_package.name == "Backend"
    assert project.approval_policies.get(approval_type="task").enabled
    assert project.custom_fields[0]["label"] == "Kontrak"
    # Ubah template: project yang sudah ada tidak berubah.
    template.structure_config = outline_to_structure("Lain\n- Satu | 1")
    template.version = 2
    template.save()
    project.refresh_from_db()
    assert project.phases.count() == 2 and project.template_version == 1


def test_save_project_as_template_requires_permission(world, client):
    project = world["project"]
    Phase.objects.create(project=project, name="Desain", sequence=1)
    Task.objects.create(
        project=project, title="Wireframe", start_date=TODAY, due_date=TODAY + timedelta(days=2)
    )
    url = reverse("projects:project_save_template", args=[project.pk])
    client.force_login(world["pm"])
    assert client.get(url).status_code == 403
    client.force_login(world["admin"])
    client.post(url, {"name": "Desain cepat"})
    template = ProjectTemplate.objects.get(name="Desain cepat")
    assert template.structure_config["tasks"][0]["duration"] == 3
    clone = Project.objects.create(
        name="Clone", code="CLONE", start_date=TODAY, target_end_date=TODAY + timedelta(days=9)
    )
    apply_template(template, clone, world["admin"])
    assert clone.tasks.get().due_date == TODAY + timedelta(days=2)


def test_template_pages_are_admin_only(world, client):
    client.force_login(world["pm"])
    assert client.get(reverse("projects:template_list")).status_code == 403
    client.force_login(world["admin"])
    response = client.post(
        reverse("projects:template_create"),
        {
            "name": "Riset",
            "project_type": "research",
            "outline": OUTLINE,
            "weight_mode": "auto",
            "fields_text": "Sponsor | teks",
            "is_active": "on",
        },
    )
    assert response.status_code == 302
    template = ProjectTemplate.objects.get(name="Riset")
    assert template.custom_fields == [{"key": "sponsor", "label": "Sponsor", "type": "text"}]
    assert "Riset" in client.get(reverse("projects:template_list")).content.decode()


# ------------------------------------------------------- type & custom fields


def test_project_type_and_custom_fields_in_form_list_and_export(world, client):
    project = world["project"]
    project.project_type = "software"
    project.save()
    client.force_login(world["pm"])
    url = reverse("projects:project_custom_fields", args=[project.pk])
    client.post(url, {"definitions": "Nomor kontrak | teks\nNilai | angka"})
    project.refresh_from_db()
    client.post(
        url, {"definitions": "Nomor kontrak | teks\nNilai | angka", "cf_nomor_kontrak": "K-9"}
    )
    project.refresh_from_db()
    assert project.custom_values == {"nomor_kontrak": "K-9"}
    listing = client.get(reverse("projects:project_list")).content.decode()
    assert "Pengembangan perangkat lunak" in listing
    headers, rows = export_rows([project], "summary")
    assert "Jenis" in headers and "Field tambahan" in headers
    assert rows[0][2] == "Pengembangan perangkat lunak" and "K-9" in rows[0][-1]
    assert parse_field_definitions("Tanggal kirim | tanggal")[0]["type"] == "date"
