"""Klasifikasi perubahan, change request, dan deliverable (R6, PRD §14, §17).

Kontrol perubahan per project (``Project.change_control``) default mati. Bila aktif dan
project sudah punya baseline yang berlaku, perubahan major hanya boleh dilakukan saat
ada change request yang sudah disetujui dan belum diterapkan ("jendela perubahan").
Menerapkan change request menutup jendela itu dan membuat versi baseline baru.
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import (
    ApprovalType,
    ChangeClassification,
    ChangeRequest,
    ChangeStatus,
    Deliverable,
    DeliverableStatus,
)
from .services import handler, pending_request, request_approval

#: Field yang perubahannya bersifat major (PRD §17.2). Sisanya minor.
MAJOR_FIELDS = {
    "project": {"target_end_date": "deadline project"},
    "milestone": {"date": "target milestone"},
    "task": {"weight": "bobot pekerjaan"},
    "deliverable": {
        "acceptance_criteria": "kriteria deliverable",
        "due_date": "target deliverable",
    },
}


def classify(entity: str, fields) -> str:
    """``major`` bila salah satu field mengubah scope/baseline, selain itu ``minor``."""
    major = MAJOR_FIELDS.get(entity, {})
    return (
        ChangeClassification.MAJOR
        if any(name in major for name in fields)
        else ChangeClassification.MINOR
    )


def _has_active_baseline(project) -> bool:
    from apps.projects.models import BaselineStatus

    return project.baselines.filter(status=BaselineStatus.ACTIVE).exists()


def change_window_open(project) -> bool:
    return ChangeRequest.objects.filter(project=project, status=ChangeStatus.APPROVED).exists()


def major_change_problem(project, entity, changed_fields) -> str:
    """Pesan penolakan bila perubahan major harus lewat change request, atau string kosong."""
    if project is None or not project.pk or not project.change_control:
        return ""
    if classify(entity, changed_fields) != ChangeClassification.MAJOR:
        return ""
    if not _has_active_baseline(project) or change_window_open(project):
        return ""
    labels = ", ".join(MAJOR_FIELDS[entity][f] for f in changed_fields if f in MAJOR_FIELDS[entity])
    return (
        f"Perubahan {labels} termasuk perubahan major setelah baseline. "
        "Ajukan change request dan tunggu persetujuan sebelum mengubahnya."
    )


def changed_fields(instance, names) -> list[str]:
    """Field di ``names`` yang nilainya berbeda dari yang tersimpan."""
    if not instance.pk:
        return []
    manager = type(instance)._base_manager
    stored = manager.filter(pk=instance.pk).values(*names).first() or {}
    return [name for name in names if stored.get(name) != getattr(instance, name)]


def guard_major_change(instance, entity, project):
    """Dipanggil dari ``clean()`` model: tolak perubahan major tanpa change request."""
    names = list(MAJOR_FIELDS.get(entity, {}))
    fields = changed_fields(instance, names)
    problem = major_change_problem(project, entity, fields) if fields else ""
    if problem:
        raise ValidationError({fields[0]: problem})


def note_major_change(project, entity, label, changes, actor):
    """Catat perubahan major setelah baseline di activity log (BR-WGT-004)."""
    from apps.projects.models import ActivityAction
    from apps.projects.services import record_activity

    if project is None or classify(entity, changes) != ChangeClassification.MAJOR:
        return
    if not _has_active_baseline(project):
        return
    names = ", ".join(MAJOR_FIELDS[entity][f] for f in changes if f in MAJOR_FIELDS[entity])
    record_activity(
        project,
        actor,
        ActivityAction.MAJOR_CHANGE,
        f"Perubahan major pada {label}: {names}.",
        object_repr=label[:200],
    )


# ---------------------------------------------------------- change request ---


def can_submit_change(user, project) -> bool:
    from apps.identity.permissions import can_view_internal
    from apps.identity.roles import has_perm

    return can_view_internal(user) and has_perm(user, "change_request.submit")


@transaction.atomic
def submit_change(change, user):
    """Draft → Submitted. Reason dan impact wajib (BR-CHG-003)."""
    from apps.projects.models import ActivityAction
    from apps.projects.services import record_activity

    if change.status != ChangeStatus.DRAFT:
        raise ValidationError("Hanya change request berstatus Draf yang bisa diajukan.")
    if not change.reason.strip() or not change.impact_assessment.strip():
        raise ValidationError("Alasan dan penilaian dampak wajib diisi.")
    change.status = ChangeStatus.SUBMITTED
    change.submitted_at = timezone.now()
    change.save(update_fields=["status", "submitted_at", "updated_at"])
    request_approval(change.project, ApprovalType.CHANGE_REQUEST, change, user, change.reason)
    record_activity(
        change.project,
        user,
        ActivityAction.CHANGE_REQUEST_UPDATED,
        f'Change request "{change.title}" diajukan ({change.get_classification_display()}).',
        entity=change,
    )
    return change


def start_review(obj, user, approval_type):
    """Approver mulai meninjau: Submitted → Under Review."""
    from apps.projects.models import ActivityAction
    from apps.projects.services import record_activity

    from .services import is_actionable

    request = pending_request(approval_type, obj.pk)
    step = request and request.steps.filter(approver=user, status="pending").first()
    if step is None or not is_actionable(step):
        raise PermissionDenied("Anda bukan approver yang sedang mendapat giliran.")
    if obj.status != "submitted":
        return obj
    obj.status = "under_review"
    obj.save(update_fields=["status", "updated_at"])
    action = (
        ActivityAction.CHANGE_REQUEST_UPDATED
        if approval_type == ApprovalType.CHANGE_REQUEST
        else ActivityAction.DELIVERABLE_UPDATED
    )
    record_activity(obj.project, user, action, f'"{obj}" sedang ditinjau.')
    return obj


@handler(ApprovalType.CHANGE_REQUEST)
def _change_decided(request, change, actor, *, approved, reason):
    change.status = ChangeStatus.APPROVED if approved else ChangeStatus.REJECTED
    change.reviewed_at = timezone.now()
    change.save(update_fields=["status", "reviewed_at", "updated_at"])


@transaction.atomic
def apply_change(change, user):
    """Approved → Applied: terapkan target baru dan buat versi baseline baru (BR-CHG-005)."""
    from apps.identity.permissions import can_manage_project
    from apps.projects.models import ActivityAction
    from apps.projects.services import capture_baseline, record_activity

    if change.status == ChangeStatus.REJECTED:
        raise ValidationError("Change request yang ditolak tidak dapat diterapkan.")
    if change.status != ChangeStatus.APPROVED:
        raise ValidationError("Change request harus disetujui sebelum diterapkan.")
    project = change.project
    if not can_manage_project(user, project):
        raise PermissionDenied("Hanya Project Manager yang dapat menerapkan perubahan.")
    if change.proposed_end_date and change.proposed_end_date != project.target_end_date:
        project.target_end_date = change.proposed_end_date
        project.full_clean()
        project.save()
    had_baseline = _has_active_baseline(project)
    baseline = None
    try:
        baseline = capture_baseline(
            project, user, note=f"CR-{change.pk}: {change.title}", change_request=change
        )
    except ValidationError:
        if had_baseline:
            raise
    change.refresh_from_db(fields=["applied_baseline"])
    change.status = ChangeStatus.APPLIED
    change.applied_by = user
    change.applied_at = timezone.now()
    change.save(update_fields=["status", "applied_by", "applied_at", "updated_at"])
    suffix = f" Baseline v{baseline.version} berlaku." if baseline else ""
    record_activity(
        project,
        user,
        ActivityAction.CHANGE_REQUEST_APPLIED,
        f'Change request "{change.title}" diterapkan.{suffix}',
    )
    return change


def change_tab_context(request, project) -> dict:
    from apps.identity.permissions import can_manage_project

    return {
        "changes": list(
            ChangeRequest.objects.filter(project=project).select_related("requester__pcc_profile")
        ),
        "change_control": project.change_control,
        "change_submit_url": reverse("governance:change_create", args=[project.pk])
        if can_submit_change(request.user, project)
        else "",
        "change_control_url": reverse("governance:change_control", args=[project.pk])
        if can_manage_project(request.user, project)
        else "",
    }


# ------------------------------------------------------------- deliverable ---


def can_manage_deliverables(user, project) -> bool:
    from apps.identity.permissions import can_manage_project
    from apps.identity.roles import has_perm

    return has_perm(user, "deliverable.manage") and can_manage_project(user, project)


def can_submit_deliverable(user, deliverable) -> bool:
    return deliverable.owner_id == user.pk or can_manage_deliverables(user, deliverable.project)


@transaction.atomic
def submit_deliverable(deliverable, user):
    """Draft/Rejected → Submitted; bukti wajib ada sebelum diajukan."""
    from apps.projects.models import ActivityAction
    from apps.projects.services import record_activity

    if not can_submit_deliverable(user, deliverable):
        raise PermissionDenied("Hanya pemilik deliverable atau PM yang dapat mengajukan.")
    if deliverable.status not in (DeliverableStatus.DRAFT, DeliverableStatus.REJECTED):
        raise ValidationError("Deliverable ini sudah diajukan.")
    if not deliverable.evidence.strip():
        raise ValidationError("Isi bukti hasil kerja sebelum mengajukan deliverable.")
    deliverable.status = DeliverableStatus.SUBMITTED
    deliverable.submission_date = timezone.localdate()
    deliverable.save(update_fields=["status", "submission_date", "updated_at"])
    request_approval(deliverable.project, ApprovalType.DELIVERABLE, deliverable, user)
    record_activity(
        deliverable.project,
        user,
        ActivityAction.DELIVERABLE_UPDATED,
        f'Deliverable "{deliverable.name}" diajukan untuk diterima.',
        entity=deliverable,
    )
    return deliverable


@handler(ApprovalType.DELIVERABLE)
def _deliverable_decided(request, deliverable, actor, *, approved, reason):
    from apps.projects.models import ActivityAction
    from apps.projects.services import record_activity

    deliverable.status = DeliverableStatus.ACCEPTED if approved else DeliverableStatus.REJECTED
    deliverable.save(update_fields=["status", "updated_at"])
    record_activity(
        deliverable.project,
        actor,
        ActivityAction.DELIVERABLE_ACCEPTED if approved else ActivityAction.DELIVERABLE_REJECTED,
        f'Deliverable "{deliverable.name}" '
        + ("diterima." if approved else f"ditolak. Alasan: {reason}"),
        entity=deliverable,
    )


def pending_acceptance(user):
    """Deliverable yang menunggu keputusan user (untuk dashboard Owner/Client)."""
    from .services import actionable_steps

    steps = list(actionable_steps(user, [ApprovalType.DELIVERABLE]))
    items = Deliverable.objects.in_bulk([s.request.target_id for s in steps])
    return [
        {"step": s, "deliverable": items[s.request.target_id]}
        for s in steps
        if s.request.target_id in items
    ]
