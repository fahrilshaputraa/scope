"""Fase 6: klasifikasi perubahan, change request, baseline revision, deliverable."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.governance.changes import (
    apply_change,
    classify,
    start_review,
    submit_change,
    submit_deliverable,
)
from apps.governance.models import (
    ApprovalRequest,
    ApprovalType,
    ChangeRequest,
    ChangeStatus,
    Deliverable,
    DeliverableStatus,
)
from apps.governance.services import decide
from apps.identity.models import Role
from apps.identity.roles import assign_roles
from apps.projects.models import (
    ActivityEvent,
    BaselineStatus,
    LifecycleStatus,
    Milestone,
    Project,
)
from apps.projects.services import capture_baseline
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
    worker = make_user("worker", Role.MEMBER)
    owner = make_user("sponsor", Role.OWNER)
    client_user = make_user("klien", Role.CLIENT)
    project = Project.objects.create(
        name="Alpha",
        code="ALPHA",
        manager=pm,
        owner=owner,
        lifecycle_status=LifecycleStatus.IN_PROGRESS,
        start_date=TODAY - timedelta(days=5),
        target_end_date=TODAY + timedelta(days=30),
    )
    project.members.add(worker, client_user)
    task = Task.objects.create(
        project=project,
        title="Build",
        start_date=TODAY,
        due_date=TODAY + timedelta(days=10),
        assignee=worker,
    )
    return {
        "pm": pm,
        "worker": worker,
        "owner": owner,
        "client": client_user,
        "project": project,
        "task": task,
    }


def make_change(world, **extra):
    return ChangeRequest.objects.create(
        project=world["project"],
        requester=world["pm"],
        title="Mundurkan go-live",
        reason="Vendor terlambat",
        impact_assessment="Go-live mundur dua minggu",
        **extra,
    )


# -------------------------------------------------------------- classification


def test_classification_of_fields():
    assert classify("project", ["description"]) == "minor"
    assert classify("project", ["target_end_date"]) == "major"
    assert classify("milestone", ["date"]) == "major"
    assert classify("task", ["title", "weight"]) == "major"


def test_change_control_off_allows_major_change_but_records_it(world):
    project = world["project"]
    capture_baseline(project, world["pm"])
    project.target_end_date += timedelta(days=7)
    project.full_clean()
    project.save()
    assert ActivityEvent.objects.filter(action="change.major").exists()


def test_change_control_blocks_major_change_until_change_request_approved(world):
    project = world["project"]
    capture_baseline(project, world["pm"])
    project.change_control = True
    project.save()
    milestone = Milestone.objects.create(project=project, name="Go-live", date=TODAY)
    milestone.date = TODAY + timedelta(days=3)
    with pytest.raises(ValidationError) as exc:
        milestone.full_clean()
    assert "change request" in str(exc.value)
    project.description = "Koreksi teks"  # minor tetap boleh
    project.full_clean()
    task = world["task"]
    task.weight = 5
    with pytest.raises(ValidationError):
        task.full_clean(exclude=["dependencies"])
    change = make_change(world)
    submit_change(change, world["pm"])
    approval = ApprovalRequest.objects.get(approval_type=ApprovalType.CHANGE_REQUEST)
    decide(approval.steps.get(), world["owner"], True)
    milestone.full_clean()  # jendela perubahan terbuka setelah disetujui


# -------------------------------------------------------------- workflow


def test_change_request_full_workflow_creates_new_baseline(world, client):
    project = world["project"]
    first = capture_baseline(project, world["pm"])
    client.force_login(world["pm"])
    response = client.post(
        reverse("governance:change_create", args=[project.pk]),
        {
            "title": "Tambah modul laporan",
            "reason": "Permintaan client",
            "impact_assessment": "Tambah 7 hari",
            "proposed_end_date": (TODAY + timedelta(days=37)).isoformat(),
            "classification": "major",
        },
    )
    change = ChangeRequest.objects.get()
    assert response.status_code == 302 and change.status == ChangeStatus.DRAFT
    client.post(reverse("governance:change_submit", args=[change.pk]))
    change.refresh_from_db()
    assert change.status == ChangeStatus.SUBMITTED
    with pytest.raises(PermissionDenied):
        start_review(change, world["pm"], ApprovalType.CHANGE_REQUEST)
    start_review(change, world["owner"], ApprovalType.CHANGE_REQUEST)
    change.refresh_from_db()
    assert change.status == ChangeStatus.UNDER_REVIEW
    approval = ApprovalRequest.objects.get(approval_type=ApprovalType.CHANGE_REQUEST)
    decide(approval.steps.get(), world["owner"], True)
    change.refresh_from_db()
    assert change.status == ChangeStatus.APPROVED
    client.post(reverse("governance:change_apply", args=[change.pk]))
    change.refresh_from_db()
    project.refresh_from_db()
    first.refresh_from_db()
    assert change.status == ChangeStatus.APPLIED
    assert project.target_end_date == TODAY + timedelta(days=37)
    assert change.applied_baseline.version == 2
    assert change.applied_baseline.status == BaselineStatus.ACTIVE
    assert first.status == BaselineStatus.SUPERSEDED  # versi lama tetap tersimpan
    page = client.get(reverse("governance:change_detail", args=[change.pk]))
    assert "Diterapkan" in page.content.decode()


def test_rejected_change_cannot_be_applied(world):
    change = make_change(world)
    submit_change(change, world["pm"])
    approval = ApprovalRequest.objects.get()
    decide(approval.steps.get(), world["owner"], False, "Tidak sesuai kontrak")
    change.refresh_from_db()
    assert change.status == ChangeStatus.REJECTED
    with pytest.raises(ValidationError):
        apply_change(change, world["pm"])


def test_change_request_requires_reason_and_impact(world):
    change = make_change(world)
    change.impact_assessment = " "
    with pytest.raises(ValidationError):
        submit_change(change, world["pm"])


def test_change_request_permissions(world, client):
    client.force_login(world["worker"])  # Member tidak punya change_request.submit
    url = reverse("governance:change_create", args=[world["project"].pk])
    assert client.get(url).status_code == 403
    client.force_login(world["client"])
    change = make_change(world)
    assert client.get(reverse("governance:change_detail", args=[change.pk])).status_code == 403


# ------------------------------------------------------------- deliverable


def test_deliverable_accepted_by_owner(world, client):
    project = world["project"]
    client.force_login(world["pm"])
    client.post(
        reverse("governance:deliverable_create", args=[project.pk]),
        {
            "name": "Dokumen desain",
            "task": world["task"].pk,
            "acceptance_criteria": "Disetujui arsitek",
            "owner": world["worker"].pk,
        },
    )
    item = Deliverable.objects.get()
    assert item.status == DeliverableStatus.DRAFT
    with pytest.raises(ValidationError):
        submit_deliverable(item, world["worker"])  # bukti belum ada
    client.force_login(world["worker"])
    client.post(
        reverse("governance:deliverable_edit", args=[item.pk]),
        {"evidence": "https://example.test/desain.pdf"},
    )
    client.post(reverse("governance:deliverable_submit", args=[item.pk]))
    item.refresh_from_db()
    assert item.status == DeliverableStatus.SUBMITTED and item.submission_date == TODAY
    approval = ApprovalRequest.objects.get(approval_type=ApprovalType.DELIVERABLE)
    assert approval.steps.get().approver == world["owner"]
    client.force_login(world["owner"])
    client.post(
        reverse("governance:approval_detail", args=[approval.pk]),
        {"decision": "approve", "reason": ""},
    )
    item.refresh_from_db()
    assert item.status == DeliverableStatus.ACCEPTED
    tab = client.get(reverse("governance:project_deliverables", args=[project.pk]))
    assert "Dokumen desain" in tab.content.decode()


def test_client_reviewer_rejects_deliverable_with_reason(world):
    item = Deliverable.objects.create(
        project=world["project"],
        name="Laporan UAT",
        acceptance_criteria="Semua skenario lulus",
        evidence="Lampiran UAT",
        owner=world["worker"],
        reviewer=world["client"],
    )
    submit_deliverable(item, world["worker"])
    step = ApprovalRequest.objects.get().steps.get()
    assert step.approver == world["client"]
    with pytest.raises(ValidationError):
        decide(step, world["client"], False, "")
    decide(step, world["client"], False, "Dua skenario gagal")
    item.refresh_from_db()
    assert item.status == DeliverableStatus.REJECTED
    submit_deliverable(item, world["worker"])  # boleh diajukan ulang
    item.refresh_from_db()
    assert item.status == DeliverableStatus.SUBMITTED


def test_member_without_permission_cannot_add_deliverable(world, client):
    client.force_login(world["worker"])
    url = reverse("governance:deliverable_create", args=[world["project"].pk])
    assert client.get(url).status_code == 403
