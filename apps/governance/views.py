"""Halaman approval, review, dan konfigurasi persetujuan (R5.4–R5.6)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.identity.permissions import can_manage_project, can_view_internal, visible_projects
from apps.identity.roles import has_perm
from apps.work.models import Task, TaskStatus

from .forms import ApprovalPolicyForm, DecisionForm, NoteForm
from .models import (
    ApprovalRequest,
    ApprovalStatus,
    ApprovalStep,
    ApprovalType,
    StepStatus,
)
from .services import (
    actionable_steps,
    cancel_pending,
    decide,
    decision_problem,
    get_policy,
    is_enabled,
    policies_for,
    request_approval,
    save_policy,
    submit_task,
    target_url,
)

NON_TASK = [t for t in ApprovalType.values if t != ApprovalType.TASK]


def _project(request, pk):
    from apps.projects.services import with_project_metrics

    return get_object_or_404(with_project_metrics(visible_projects(request.user)), pk=pk)


def can_configure(user, project) -> bool:
    return has_perm(user, "approval.configure") and can_manage_project(user, project)


def _safe_next(request, fallback):
    from django.utils.http import url_has_allowed_host_and_scheme

    target = request.POST.get("next") or ""
    if url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return reverse(fallback) if not fallback.startswith("/") else fallback


def _rows(steps):
    return [
        {"step": step, "request": step.request, "url": target_url(step.request)} for step in steps
    ]


# ------------------------------------------------------------------ queues ---


@login_required
def approval_inbox(request):
    """Antrean persetujuan milik user (selain pemeriksaan task)."""
    steps = list(actionable_steps(request.user, NON_TASK))
    mine = (
        ApprovalRequest.objects.filter(
            requested_by=request.user,
            status=ApprovalStatus.PENDING,
            approval_type__in=NON_TASK,
        )
        .select_related("project")
        .prefetch_related("steps__approver__pcc_profile")
    )
    return render(
        request,
        "governance/inbox.html",
        {
            "rows": _rows(steps),
            "mine": [{"request": r, "url": target_url(r)} for r in mine],
            "decided": ApprovalStep.objects.filter(approver=request.user)
            .exclude(status__in=[StepStatus.PENDING, StepStatus.SKIPPED])
            .exclude(request__approval_type=ApprovalType.TASK)
            .select_related("request__project")
            .order_by("-decided_at")[:10],
        },
    )


@login_required
def my_reviews(request):
    """Task yang menunggu pemeriksaan saya, dan task saya yang sedang diperiksa."""
    steps = list(actionable_steps(request.user, [ApprovalType.TASK]))
    tasks = {
        t.pk: t
        for t in Task.objects.filter(pk__in=[s.request.target_id for s in steps]).select_related(
            "assignee__pcc_profile", "project"
        )
    }
    rows = [
        {**row, "task": tasks.get(row["request"].target_id)}
        for row in _rows(steps)
        if row["request"].target_id in tasks
    ]
    waiting = (
        Task.objects.filter(status=TaskStatus.REVIEW, project__in=visible_projects(request.user))
        .filter(assignee=request.user)
        .select_related("project", "reviewer__pcc_profile")
        .order_by("due_date", "pk")
    )
    return render(request, "governance/reviews.html", {"rows": rows, "waiting": waiting})


# ------------------------------------------------------------------ detail ---


def _visible_request(request, pk):
    approval = get_object_or_404(
        ApprovalRequest.objects.select_related("project", "requested_by__pcc_profile"),
        pk=pk,
        project__in=visible_projects(request.user),
    )
    involved = (
        approval.requested_by_id == request.user.pk
        or approval.steps.filter(approver=request.user).exists()
    )
    if not (involved or can_view_internal(request.user)):
        raise Http404
    return approval


@login_required
def approval_detail(request, pk):
    approval = _visible_request(request, pk)
    steps = list(approval.steps.select_related("approver__pcc_profile"))
    mine = next(
        (s for s in steps if s.approver_id == request.user.pk and s.status == StepStatus.PENDING),
        None,
    )
    problem = decision_problem(mine, request.user) if mine else ""
    form = DecisionForm(request.POST or None)
    if request.method == "POST":
        if mine is None:
            raise PermissionDenied
        if form.is_valid():
            approve = form.cleaned_data["decision"] == "approve"
            try:
                decide(mine, request.user, approve, form.cleaned_data["reason"])
            except PermissionDenied as exc:
                messages.error(request, str(exc) or "Anda tidak dapat memutuskan pengajuan ini.")
            except ValidationError as exc:
                messages.error(request, " ".join(exc.messages))
            else:
                messages.success(
                    request, "Keputusan disimpan." if approve else "Pengajuan ditolak."
                )
                return redirect(_safe_next(request, "governance:approval_inbox"))
            return redirect("governance:approval_detail", pk=approval.pk)
    return render(
        request,
        "governance/detail.html",
        {
            "approval": approval,
            "steps": steps,
            "my_step": mine,
            "problem": problem,
            "form": form,
            "target_url": target_url(approval),
            "can_cancel": approval.is_pending
            and (
                approval.requested_by_id == request.user.pk
                or can_manage_project(request.user, approval.project)
            ),
        },
    )


@login_required
@require_POST
def approval_quick(request, pk):
    """Setujui langsung dari antrean (menolak tetap lewat halaman detail karena butuh alasan)."""
    approval = _visible_request(request, pk)
    step = approval.steps.filter(approver=request.user, status=StepStatus.PENDING).first()
    if step is None:
        raise PermissionDenied
    try:
        decide(step, request.user, True, "")
    except PermissionDenied as exc:
        messages.error(request, str(exc))
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, f"{approval.get_approval_type_display()} disetujui.")
    fallback = (
        "governance:my_reviews"
        if approval.approval_type == ApprovalType.TASK
        else "governance:approval_inbox"
    )
    return redirect(_safe_next(request, fallback))


@login_required
@require_POST
def approval_cancel(request, pk):
    approval = _visible_request(request, pk)
    if not approval.is_pending or not (
        approval.requested_by_id == request.user.pk
        or can_manage_project(request.user, approval.project)
    ):
        raise PermissionDenied
    cancel_pending(approval.approval_type, approval.target_id, request.user)
    if approval.approval_type == ApprovalType.TASK:
        task = Task.objects.filter(pk=approval.target_id, status=TaskStatus.REVIEW).first()
        if task:
            task.status = TaskStatus.IN_PROGRESS
            task.save()
    if approval.approval_type == ApprovalType.BASELINE:
        from apps.projects.models import Baseline, BaselineStatus

        Baseline.objects.filter(pk=approval.target_id, status=BaselineStatus.PENDING).update(
            status=BaselineStatus.REJECTED
        )
    messages.success(request, "Pengajuan dibatalkan.")
    return redirect("governance:approval_detail", pk=approval.pk)


# ----------------------------------------------------------- project tab ---


@login_required
def project_approvals(request, pk):
    from apps.projects.views import project_context

    project = _project(request, pk)
    if not can_view_internal(request.user):
        raise PermissionDenied
    history = (
        ApprovalRequest.objects.filter(project=project)
        .select_related("requested_by__pcc_profile")
        .prefetch_related("steps__approver__pcc_profile")
        .order_by("-created_at")
    )
    pending = [r for r in history if r.is_pending]
    context = {
        **project_context(request, project, "approvals"),
        "policies": policies_for(project),
        "pending": [{"request": r, "url": target_url(r)} for r in pending],
        "history": [{"request": r, "url": target_url(r)} for r in history if not r.is_pending][:30],
        "can_configure": can_configure(request.user, project),
        "plan_enabled": is_enabled(project, ApprovalType.PLAN),
        "closure_enabled": is_enabled(project, ApprovalType.CLOSURE),
    }
    context.update(_change_context(request, project))
    return render(request, "governance/project_approvals.html", context)


def _change_context(request, project):
    """Diisi oleh tahap change request (R6) bila model tersedia."""
    try:
        from .changes import change_tab_context
    except ImportError:  # pragma: no cover - sebelum R6
        return {}
    return change_tab_context(request, project)


@login_required
def policy_edit(request, pk, approval_type):
    project = _project(request, pk)
    if approval_type not in ApprovalType.values:
        raise Http404
    if not can_configure(request.user, project):
        raise PermissionDenied
    policy = get_policy(project, approval_type)
    form = ApprovalPolicyForm(
        request.POST or None, project=project, approval_type=approval_type, policy=policy
    )
    if request.method == "POST" and form.is_valid():
        save_policy(
            project,
            approval_type,
            enabled=form.cleaned_data["enabled"],
            mode=form.cleaned_data["mode"],
            allow_self=form.cleaned_data["allow_self_approval"],
            approvers=form.approvers(),
            actor=request.user,
        )
        messages.success(request, "Konfigurasi persetujuan disimpan.")
        return redirect("governance:project_approvals", pk=project.pk)
    return render(
        request,
        "governance/form.html",
        {
            "form": form,
            "project": project,
            "title": ApprovalType(approval_type).label,
            "subtitle": f"{project.name} · konfigurasi persetujuan",
            "back_url": reverse("governance:project_approvals", args=[project.pk]),
        },
    )


def _submit_project_request(request, pk, approval_type, ready, success):
    project = _project(request, pk)
    if not can_manage_project(request.user, project):
        raise PermissionDenied
    # Kembali ke halaman asal (mis. checklist Siap berjalan di Ringkasan).
    back = redirect(_safe_next(request, reverse("governance:project_approvals", args=[project.pk])))
    if not is_enabled(project, approval_type):
        messages.error(request, "Persetujuan jenis ini belum diaktifkan untuk project.")
        return back
    unmet = ready(project)
    if unmet:
        messages.error(request, "Belum bisa diajukan: " + "; ".join(unmet) + ".")
        return back
    form = NoteForm(request.POST)
    note = form.cleaned_data["note"] if form.is_valid() else ""
    try:
        request_approval(project, approval_type, project, request.user, note)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return back
    messages.success(request, success)
    return back


@login_required
@require_POST
def request_plan(request, pk):
    def ready(project):
        return [] if project.tasks.exists() else ["belum ada task"]

    return _submit_project_request(
        request, pk, ApprovalType.PLAN, ready, "Rencana project diajukan untuk disetujui."
    )


@login_required
@require_POST
def request_closure(request, pk):
    from apps.projects.services import closure_requirements

    return _submit_project_request(
        request,
        pk,
        ApprovalType.CLOSURE,
        closure_requirements,
        "Penutupan project diajukan untuk disetujui.",
    )


# ---------------------------------------------------------------- task ---


@login_required
@require_POST
def task_submit(request, pk):
    task = get_object_or_404(
        Task.objects.select_related("project", "reviewer"),
        pk=pk,
        project__in=visible_projects(request.user),
    )
    form = NoteForm(request.POST)
    note = form.cleaned_data["note"] if form.is_valid() else ""
    try:
        submit_task(task, request.user, note)
    except PermissionDenied as exc:
        messages.error(request, str(exc) or "Anda tidak dapat mengirim task ini.")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Task dikirim untuk diperiksa.")
    return redirect("work:task_detail", pk=task.pk)
