"""Mesin persetujuan (PRD §18, BR-APR-001 sampai 006).

Aturan utama:
- Persetujuan hanya berlaku bila ``ApprovalPolicy`` jenis itu diaktifkan di project,
  kecuali pemeriksaan task yang juga aktif bila task punya reviewer, serta penerimaan
  deliverable dan change request yang selalu diputuskan (default oleh Project Owner).
- Otoritas datang dari penunjukan (approver di konfigurasi, reviewer task, reviewer
  deliverable, atau Project Owner). Role aktif juga harus memiliki permission jenisnya.
- Pengaju tidak bisa menyetujui pengajuannya sendiri kecuali konfigurasi mengizinkan.
- Penolakan wajib beralasan; riwayat tidak pernah dihapus.
"""

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.urls import reverse
from django.utils import timezone

from apps.identity.roles import active_role, has_perm

from .models import (
    APPROVAL_PERMISSIONS,
    ApprovalMode,
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalStatus,
    ApprovalStep,
    ApprovalType,
    PolicyApprover,
    StepStatus,
)

MAX_APPROVERS = 3

NO_APPROVER = {
    ApprovalType.PLAN: "Belum ada approver rencana. Atur approver atau tentukan Project Owner.",
    ApprovalType.BASELINE: "Belum ada approver baseline. Atur approver atau tentukan Owner.",
    ApprovalType.TASK: "Task ini belum punya reviewer. Minta PM menentukan reviewer.",
    ApprovalType.DELIVERABLE: "Tentukan reviewer deliverable atau Project Owner terlebih dahulu.",
    ApprovalType.CHANGE_REQUEST: "Tentukan Project Owner atau approver change request dahulu.",
    ApprovalType.CLOSURE: "Belum ada approver penutupan. Atur approver atau tentukan Owner.",
}


# ------------------------------------------------------------------ policy ---


def get_policy(project, approval_type):
    return ApprovalPolicy.objects.filter(project=project, approval_type=approval_type).first()


def is_enabled(project, approval_type) -> bool:
    if project is None or not project.pk:
        return False
    return ApprovalPolicy.objects.filter(
        project=project, approval_type=approval_type, enabled=True
    ).exists()


def policies_for(project) -> list[dict]:
    """Semua jenis persetujuan beserta konfigurasinya (yang belum disimpan = mati)."""
    stored = {
        p.approval_type: p
        for p in ApprovalPolicy.objects.filter(project=project).prefetch_related(
            "approver_rows__user"
        )
    }
    rows = []
    for value, label in ApprovalType.choices:
        policy = stored.get(value)
        rows.append(
            {
                "type": value,
                "label": label,
                "policy": policy,
                "enabled": bool(policy and policy.enabled),
                "approvers": [r.user for r in policy.approver_rows.all()] if policy else [],
            }
        )
    return rows


def approver_candidates(project, approval_type):
    """User aktif di project yang role-nya bisa memutuskan jenis persetujuan ini."""
    from apps.identity.models import RoleDefinition

    permission = APPROVAL_PERMISSIONS[approval_type]
    codes = [r.code for r in RoleDefinition.objects.all() if permission in r.permissions]
    people = Q(member_projects=project) | Q(pk=project.owner_id) | Q(pk=project.manager_id)
    return (
        User.objects.filter(is_active=True)
        .filter(people)
        .filter(Q(memberships__role__code__in=codes) | Q(is_staff=True))
        .distinct()
        .order_by("first_name", "username")
    )


@transaction.atomic
def save_policy(project, approval_type, *, enabled, mode, allow_self, approvers, actor):
    """Simpan konfigurasi dan catat perubahannya (PRD §18.4)."""
    from apps.projects.models import ActivityAction
    from apps.projects.services import record_activity

    policy, _ = ApprovalPolicy.objects.get_or_create(project=project, approval_type=approval_type)
    before = (
        policy.enabled,
        policy.mode,
        policy.allow_self_approval,
        [u.pk for u in policy.ordered_approvers()],
    )
    policy.enabled, policy.mode, policy.allow_self_approval = enabled, mode, allow_self
    policy.updated_by = actor
    policy.save()
    policy.approver_rows.all().delete()
    unique = []
    for user in approvers:
        if user is not None and user.pk not in {u.pk for u in unique}:
            unique.append(user)
    PolicyApprover.objects.bulk_create(
        PolicyApprover(policy=policy, user=user, sequence=index)
        for index, user in enumerate(unique[:MAX_APPROVERS], start=1)
    )
    after = (enabled, mode, allow_self, [u.pk for u in unique])
    if before != after:
        names = ", ".join(_name(u) for u in unique) or "default"
        state = "aktif" if enabled else "mati"
        record_activity(
            project,
            actor,
            ActivityAction.APPROVAL_POLICY,
            f"Konfigurasi {ApprovalType(approval_type).label.lower()}: {state}, "
            f"{ApprovalMode(mode).label.lower()}, self-approval "
            f"{'diizinkan' if allow_self else 'dilarang'}, approver {names}.",
        )
    return policy


# --------------------------------------------------------------- targets ---


def target_model(approval_type):
    from apps.projects.models import Baseline, Project
    from apps.work.models import Task

    from .models import ChangeRequest, Deliverable

    return {
        ApprovalType.PLAN: Project,
        ApprovalType.CLOSURE: Project,
        ApprovalType.BASELINE: Baseline,
        ApprovalType.TASK: Task,
        ApprovalType.DELIVERABLE: Deliverable,
        ApprovalType.CHANGE_REQUEST: ChangeRequest,
    }.get(approval_type)


def target_of(request):
    model = target_model(request.approval_type)
    if model is None:
        return None
    manager = getattr(model, "all_objects", model._default_manager)
    return manager.filter(pk=request.target_id).first()


def target_url(request) -> str:
    kind = request.approval_type
    if kind == ApprovalType.TASK:
        return reverse("work:task_detail", args=[request.target_id])
    if kind == ApprovalType.DELIVERABLE:
        return reverse("governance:deliverable_detail", args=[request.target_id])
    if kind == ApprovalType.CHANGE_REQUEST:
        return reverse("governance:change_detail", args=[request.target_id])
    if kind == ApprovalType.BASELINE:
        return reverse("projects:project_timeline", args=[request.project_id])
    return reverse("governance:project_approvals", args=[request.project_id])


def _repr(target) -> str:
    from apps.projects.models import Baseline, Project

    if isinstance(target, Project):
        return f"{target.code} — {target.name}"[:200]
    if isinstance(target, Baseline):
        return f"Baseline v{target.version}"
    return str(getattr(target, "title", None) or getattr(target, "name", None) or target)[:200]


def _name(user) -> str:
    from apps.notifications.services import user_display

    return user_display(user)


def default_approvers(project, approval_type, target) -> list:
    policy = get_policy(project, approval_type)
    enabled = bool(policy and policy.enabled)
    listed = policy.ordered_approvers() if policy else []
    if approval_type == ApprovalType.TASK:
        if target.reviewer_id:
            return [target.reviewer]
        if enabled and listed:
            return listed
        return [project.manager] if project.manager_id else []
    if approval_type == ApprovalType.DELIVERABLE:
        if enabled and listed:
            return listed
        person = target.reviewer if target.reviewer_id else project.owner
        return [person] if person else []
    if enabled and listed:
        return listed
    return [project.owner] if project.owner_id else []


# -------------------------------------------------------------- requests ---


def pending_request(approval_type, target_id):
    return (
        ApprovalRequest.objects.filter(
            approval_type=approval_type, target_id=target_id, status=ApprovalStatus.PENDING
        )
        .order_by("-created_at")
        .first()
    )


def latest_request(approval_type, target_id):
    return (
        ApprovalRequest.objects.filter(approval_type=approval_type, target_id=target_id)
        .order_by("-created_at", "-pk")
        .first()
    )


def requests_for(approval_type, target_id):
    return (
        ApprovalRequest.objects.filter(approval_type=approval_type, target_id=target_id)
        .prefetch_related("steps__approver__pcc_profile")
        .select_related("requested_by__pcc_profile")
        .order_by("-created_at", "-pk")
    )


def _excluded_for_self(approval_type, target, requester) -> set:
    excluded = {requester.pk} if requester is not None else set()
    if approval_type == ApprovalType.TASK:
        if target.assignee_id:
            excluded.add(target.assignee_id)
        excluded.update(target.collaborators.values_list("pk", flat=True))
    return excluded


@transaction.atomic
def request_approval(project, approval_type, target, requester, note=""):
    """Buat pengajuan beserta langkah approver-nya. Idempoten bila masih menunggu."""
    from apps.projects.models import ActivityAction
    from apps.projects.services import record_activity

    existing = pending_request(approval_type, target.pk)
    if existing is not None:
        return existing
    policy = get_policy(project, approval_type)
    allow_self = bool(policy and policy.allow_self_approval)
    mode = policy.mode if policy and policy.enabled else ApprovalMode.SEQUENTIAL
    people = []
    for user in default_approvers(project, approval_type, target):
        if user is not None and user.is_active and user.pk not in {p.pk for p in people}:
            people.append(user)
    if not allow_self:
        excluded = _excluded_for_self(approval_type, target, requester)
        people = [user for user in people if user.pk not in excluded]
    if not people:
        raise ValidationError(NO_APPROVER[approval_type])
    request = ApprovalRequest.objects.create(
        project=project,
        approval_type=approval_type,
        target_id=target.pk,
        target_repr=_repr(target),
        requested_by=requester,
        requested_role=active_role(requester) if requester is not None else "",
        mode=mode,
        allow_self_approval=allow_self,
        note=(note or "").strip(),
    )
    ApprovalStep.objects.bulk_create(
        ApprovalStep(request=request, approver=user, sequence=index)
        for index, user in enumerate(people, start=1)
    )
    record_activity(
        project,
        requester,
        ActivityAction.APPROVAL_REQUESTED,
        f"{request.get_approval_type_display()} diajukan: {request.target_repr}. "
        f"Approver: {', '.join(_name(u) for u in people)}.",
        reason=request.note,
        entity=target,
    )
    _notify_turn(request, requester)
    return request


def _earlier_pending():
    return ApprovalStep.objects.filter(
        request=OuterRef("request"),
        sequence__lt=OuterRef("sequence"),
        status=StepStatus.PENDING,
    )


def actionable_steps(user, approval_types=None):
    """Langkah yang menunggu keputusan user sekarang (giliran sudah tiba)."""
    from apps.identity.permissions import visible_projects

    if not getattr(user, "is_authenticated", False):
        return ApprovalStep.objects.none()
    steps = (
        ApprovalStep.objects.filter(
            approver=user,
            status=StepStatus.PENDING,
            request__status=ApprovalStatus.PENDING,
            request__project__in=visible_projects(user),
        )
        .filter(Q(request__mode=ApprovalMode.PARALLEL) | ~Exists(_earlier_pending()))
        .select_related("request__project", "request__requested_by__pcc_profile")
        .order_by("request__created_at", "pk")
    )
    if approval_types is not None:
        steps = steps.filter(request__approval_type__in=list(approval_types))
    return steps


def is_actionable(step) -> bool:
    if step.status != StepStatus.PENDING or step.request.status != ApprovalStatus.PENDING:
        return False
    if step.request.mode == ApprovalMode.PARALLEL:
        return True
    return not step.request.steps.filter(
        sequence__lt=step.sequence, status=StepStatus.PENDING
    ).exists()


def decision_problem(step, user) -> str:
    """Alasan user tidak bisa memutuskan langkah ini sekarang, atau string kosong."""
    request = step.request
    if step.approver_id != user.pk:
        return "Anda bukan approver untuk pengajuan ini."
    if not is_actionable(step):
        return "Pengajuan ini sudah diputuskan atau belum giliran Anda."
    permission = APPROVAL_PERMISSIONS[request.approval_type]
    if not has_perm(user, permission):
        return "Role aktif Anda tidak memiliki izin untuk keputusan ini. Ganti role lalu coba lagi."
    if not request.allow_self_approval and request.requested_by_id == user.pk:
        return "Self-approval tidak diizinkan oleh konfigurasi project."
    return ""


@transaction.atomic
def decide(step, user, approve: bool, reason: str = ""):
    """Catat keputusan satu approver dan selesaikan pengajuan bila sudah final."""
    from apps.projects.models import ActivityAction
    from apps.projects.services import record_activity

    step = (
        ApprovalStep.objects.select_for_update().select_related("request__project").get(pk=step.pk)
    )
    request = step.request
    problem = decision_problem(step, user)
    if problem:
        raise PermissionDenied(problem)
    reason = (reason or "").strip()
    if not approve and not reason:
        raise ValidationError("Alasan penolakan wajib diisi.")
    now = timezone.now()
    step.status = StepStatus.APPROVED if approve else StepStatus.REJECTED
    step.reason = reason
    step.decided_at = now
    step.active_role = active_role(user)
    step.save(update_fields=["status", "reason", "decided_at", "active_role"])
    label = f'{request.get_approval_type_display()} "{request.target_repr}"'
    if not approve:
        request.steps.filter(status=StepStatus.PENDING).update(status=StepStatus.SKIPPED)
        request.status, request.decided_at = ApprovalStatus.REJECTED, now
        request.save(update_fields=["status", "decided_at"])
        record_activity(
            request.project,
            user,
            ActivityAction.APPROVAL_REJECTED,
            f"{label} ditolak oleh {_name(user)}. Alasan: {reason}",
            reason=reason,
            entity=target_of(request),
        )
        _finalize(request, user, approved=False, reason=reason)
        _notify_result(request, user, reason)
        return request
    if request.steps.filter(status=StepStatus.PENDING).exists():
        record_activity(
            request.project,
            user,
            ActivityAction.APPROVAL_APPROVED,
            f"{label} disetujui {_name(user)} (tahap {step.sequence}); menunggu approver lain.",
            reason=reason,
            entity=target_of(request),
        )
        _notify_turn(request, user)
        return request
    request.status, request.decided_at = ApprovalStatus.APPROVED, now
    request.save(update_fields=["status", "decided_at"])
    record_activity(
        request.project,
        user,
        ActivityAction.APPROVAL_APPROVED,
        f"{label} disetujui oleh {_name(user)}." + (f" Catatan: {reason}" if reason else ""),
        reason=reason,
        entity=target_of(request),
    )
    _finalize(request, user, approved=True, reason=reason)
    _notify_result(request, user, reason)
    return request


@transaction.atomic
def cancel_pending(approval_type, target_id, actor, reason="Pengajuan ditarik."):
    from apps.projects.models import ActivityAction
    from apps.projects.services import record_activity

    cancelled = 0
    for request in ApprovalRequest.objects.filter(
        approval_type=approval_type, target_id=target_id, status=ApprovalStatus.PENDING
    ).select_related("project"):
        request.steps.filter(status=StepStatus.PENDING).update(status=StepStatus.SKIPPED)
        request.status, request.decided_at = ApprovalStatus.CANCELLED, timezone.now()
        request.save(update_fields=["status", "decided_at"])
        record_activity(
            request.project,
            actor,
            ActivityAction.APPROVAL_CANCELLED,
            f'{request.get_approval_type_display()} "{request.target_repr}" dibatalkan. {reason}',
            reason=reason,
            entity=target_of(request),
        )
        cancelled += 1
    return cancelled


# ------------------------------------------------------------- handlers ---

HANDLERS = {}


def handler(approval_type):
    def register(func):
        HANDLERS[approval_type] = func
        return func

    return register


def _finalize(request, actor, *, approved, reason):
    func = HANDLERS.get(request.approval_type)
    target = target_of(request)
    if func is not None and target is not None:
        func(request, target, actor, approved=approved, reason=reason)


@handler(ApprovalType.TASK)
def _task_decided(request, task, actor, *, approved, reason):
    from apps.projects.models import ActivityAction
    from apps.projects.services import record_activity
    from apps.work.models import TaskComment, TaskStatus

    if approved:
        task.status = TaskStatus.DONE
        task.save()
        record_activity(
            task.project,
            actor,
            ActivityAction.TASK_STATUS,
            f'Task "{task.title}" disetujui reviewer dan selesai.',
            target=task,
        )
        return
    task.status = TaskStatus.IN_PROGRESS
    task.save()
    TaskComment.objects.create(
        task=task, author=actor, content=f"Hasil pemeriksaan ditolak. Alasan: {reason}"
    )
    record_activity(
        task.project,
        actor,
        ActivityAction.TASK_STATUS,
        f'Task "{task.title}" dikembalikan ke Sedang dikerjakan setelah ditolak reviewer.',
        target=task,
    )


@handler(ApprovalType.BASELINE)
def _baseline_decided(request, baseline, actor, *, approved, reason):
    from apps.projects.models import BaselineStatus
    from apps.projects.services import activate_baseline

    if baseline.status != BaselineStatus.PENDING:
        return
    if approved:
        activate_baseline(baseline, actor)
    else:
        baseline.status = BaselineStatus.REJECTED
        baseline.save(update_fields=["status"])


@handler(ApprovalType.CLOSURE)
def _closure_decided(request, project, actor, *, approved, reason):
    from apps.projects.models import ActivityAction, LifecycleStatus
    from apps.projects.services import closure_requirements, record_activity

    if not approved or project.lifecycle_status == LifecycleStatus.COMPLETED:
        return
    if closure_requirements(project):
        record_activity(
            project,
            actor,
            ActivityAction.PROJECT_UPDATED,
            "Penutupan disetujui; lengkapi syarat penutupan lalu ubah status menjadi Selesai.",
        )
        return
    project.lifecycle_status = LifecycleStatus.COMPLETED
    project.actual_end_date = project.actual_end_date or timezone.localdate()
    project.full_clean()
    project.save()
    record_activity(
        project,
        actor,
        ActivityAction.PROJECT_UPDATED,
        f'Project "{project.name}" ditutup setelah penutupan disetujui.',
        target=project,
    )


# ------------------------------------------------------- project helpers ---


def plan_approved(project) -> bool:
    return ApprovalRequest.objects.filter(
        project=project, approval_type=ApprovalType.PLAN, status=ApprovalStatus.APPROVED
    ).exists()


def closure_approved(project) -> bool:
    latest = latest_request(ApprovalType.CLOSURE, project.pk)
    return bool(latest and latest.status == ApprovalStatus.APPROVED)


def planning_gate(project) -> list[str]:
    """Syarat tambahan sebelum project berjalan bila persetujuan rencana aktif."""
    if project.pk and is_enabled(project, ApprovalType.PLAN) and not plan_approved(project):
        return ["rencana project belum disetujui"]
    return []


def closure_gate(project) -> str:
    if project.pk and is_enabled(project, ApprovalType.CLOSURE) and not closure_approved(project):
        return "Penutupan project harus disetujui terlebih dahulu (tab Persetujuan)."
    return ""


# ----------------------------------------------------------- task review ---


def task_needs_review(task) -> bool:
    return bool(task.reviewer_id) or is_enabled(task.project, ApprovalType.TASK)


def reviewer_problem(task) -> str:
    """Reviewer tidak boleh pelaksana task kecuali self-approval diizinkan (BR-APR-003)."""
    if not task.reviewer_id or not task.project_id:
        return ""
    doers = {task.assignee_id}
    if task.pk:
        doers.update(task.collaborators.values_list("pk", flat=True))
    if task.reviewer_id not in doers:
        return ""
    policy = get_policy(task.project, ApprovalType.TASK)
    if policy and policy.allow_self_approval:
        return ""
    return "Reviewer harus berbeda dari pelaksana task."


@transaction.atomic
def submit_task(task, user, note=""):
    """Assignee mengirim hasil kerja untuk diperiksa (PRD §18.3 langkah 2–3)."""
    from apps.identity.permissions import can_execute_task
    from apps.projects.models import ActivityAction
    from apps.projects.services import record_activity
    from apps.work.models import TaskStatus

    if not can_execute_task(user, task):
        raise PermissionDenied("Hanya pelaksana task yang dapat mengirim untuk diperiksa.")
    if task.is_done:
        raise ValidationError("Task sudah selesai.")
    if not task_needs_review(task):
        raise ValidationError("Task ini tidak memerlukan pemeriksaan. Tandai selesai langsung.")
    if task.dependencies.exclude(status=TaskStatus.DONE).exists():
        raise ValidationError("Selesaikan dependency task terlebih dahulu.")
    old = task.get_status_display()
    task.status = TaskStatus.REVIEW
    task.full_clean(exclude=["dependencies"])
    task.save()
    request = request_approval(task.project, ApprovalType.TASK, task, user, note)
    if old != task.get_status_display():
        record_activity(
            task.project,
            user,
            ActivityAction.TASK_STATUS,
            f'Task "{task.title}" dikirim untuk diperiksa ({old} → In Review).',
            target=task,
        )
    return request


def task_review_context(task) -> dict:
    requests = list(requests_for(ApprovalType.TASK, task.pk)[:5])
    return {
        "review_needed": task_needs_review(task),
        "review_requests": requests,
        "review_pending": next((r for r in requests if r.is_pending), None),
    }


def sync_task_review(task, old_status, actor):
    """Status diubah lewat papan/form: buat atau batalkan pengajuan pemeriksaan."""
    from apps.work.models import TaskStatus

    if task.status == old_status:
        return None
    if task.status == TaskStatus.REVIEW and task_needs_review(task):
        return request_approval(task.project, ApprovalType.TASK, task, actor)
    if old_status == TaskStatus.REVIEW:
        cancel_pending(ApprovalType.TASK, task.pk, actor, "Task ditarik dari pemeriksaan.")
    return None


# ------------------------------------------------------------ notifications ---


def _notify_turn(request, actor):
    from apps.notifications.services import notify

    waiting = [
        step.approver
        for step in request.steps.select_related("approver").filter(status=StepStatus.PENDING)
        if is_actionable(step)
    ]
    if not waiting:
        return
    notify(
        actor,
        "approval.requested",
        request,
        recipients=waiting,
        title=f"Perlu keputusan: {request.get_approval_type_display()} — {request.target_repr}",
        body=request.note or f"Diajukan oleh {_name(request.requested_by)}.",
        url=reverse("governance:approval_detail", args=[request.pk]),
        dedupe_suffix=f"turn:{request.steps.filter(status=StepStatus.APPROVED).count()}",
        project=request.project,
        allow_management=True,
    )


def _notify_result(request, actor, reason):
    from apps.notifications.services import notify

    if request.requested_by is None:
        return
    verdict = "disetujui" if request.status == ApprovalStatus.APPROVED else "ditolak"
    notify(
        actor,
        "approval.decided",
        request,
        recipients=[request.requested_by],
        title=f"{request.get_approval_type_display()} {verdict}: {request.target_repr}",
        body=reason,
        url=reverse("governance:approval_detail", args=[request.pk]),
        dedupe_suffix=request.status,
        project=request.project,
    )
