"""Halaman change request dan deliverable (R6)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.identity.permissions import can_manage_project, can_view_internal, visible_projects

from .changes import (
    apply_change,
    can_manage_deliverables,
    can_submit_change,
    can_submit_deliverable,
    start_review,
    submit_change,
    submit_deliverable,
)
from .forms import ChangeControlForm, ChangeRequestForm, DeliverableForm, EvidenceForm
from .models import (
    ApprovalType,
    ChangeRequest,
    ChangeStatus,
    Deliverable,
    DeliverableStatus,
    StepStatus,
)
from .services import is_actionable, pending_request, requests_for
from .views import _project


def _form_page(request, form, project, title, back_url, submit_label="Simpan", extra=None):
    return render(
        request,
        "governance/form.html",
        {
            "form": form,
            "project": project,
            "title": title,
            "subtitle": project.name,
            "back_url": back_url,
            "submit_label": submit_label,
            **(extra or {}),
        },
    )


def _my_turn(approval_type, obj, user):
    request = pending_request(approval_type, obj.pk)
    if request is None:
        return None
    step = request.steps.filter(approver=user, status=StepStatus.PENDING).first()
    return request if step is not None and is_actionable(step) else None


def _run(request, action, success):
    try:
        action()
    except PermissionDenied as exc:
        messages.error(request, str(exc) or "Anda tidak berhak melakukan aksi ini.")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, success)


# --------------------------------------------------------- change request ---


def _change(request, pk):
    change = get_object_or_404(
        ChangeRequest.objects.select_related("project", "requester__pcc_profile"),
        pk=pk,
        project__in=visible_projects(request.user),
    )
    if not can_view_internal(request.user):
        raise PermissionDenied
    return change


def _can_edit_change(user, change):
    return change.status == ChangeStatus.DRAFT and (
        change.requester_id == user.pk or can_manage_project(user, change.project)
    )


@login_required
def change_create(request, pk):
    project = _project(request, pk)
    if not can_submit_change(request.user, project):
        raise PermissionDenied
    form = ChangeRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        change = form.save(commit=False)
        change.project, change.requester = project, request.user
        change.save()
        from apps.projects.models import ActivityAction
        from apps.projects.services import record_activity

        record_activity(
            project,
            request.user,
            ActivityAction.CHANGE_REQUEST_UPDATED,
            f'Change request "{change.title}" dibuat sebagai draf.',
        )
        if "submit_now" in request.POST:
            _run(request, lambda: submit_change(change, request.user), "Change request diajukan.")
        else:
            messages.success(request, "Draf change request disimpan.")
        return redirect("governance:change_detail", pk=change.pk)
    return _form_page(
        request,
        form,
        project,
        "Ajukan perubahan",
        reverse("governance:project_approvals", args=[project.pk]),
        "Simpan draf",
    )


@login_required
def change_edit(request, pk):
    change = _change(request, pk)
    if not _can_edit_change(request.user, change):
        raise PermissionDenied
    form = ChangeRequestForm(request.POST or None, instance=change)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Change request disimpan.")
        return redirect("governance:change_detail", pk=change.pk)
    return _form_page(
        request,
        form,
        change.project,
        f"Edit CR-{change.pk}",
        reverse("governance:change_detail", args=[change.pk]),
    )


@login_required
def change_detail(request, pk):
    change = _change(request, pk)
    turn = _my_turn(ApprovalType.CHANGE_REQUEST, change, request.user)
    return render(
        request,
        "governance/change_detail.html",
        {
            "change": change,
            "project": change.project,
            "approvals": requests_for(ApprovalType.CHANGE_REQUEST, change.pk),
            "can_edit": _can_edit_change(request.user, change),
            "can_apply": change.status == ChangeStatus.APPROVED
            and can_manage_project(request.user, change.project),
            "my_turn": turn,
        },
    )


@login_required
@require_POST
def change_submit(request, pk):
    change = _change(request, pk)
    if not _can_edit_change(request.user, change):
        raise PermissionDenied
    _run(request, lambda: submit_change(change, request.user), "Change request diajukan.")
    return redirect("governance:change_detail", pk=change.pk)


@login_required
@require_POST
def change_review(request, pk):
    change = _change(request, pk)
    _run(
        request,
        lambda: start_review(change, request.user, ApprovalType.CHANGE_REQUEST),
        "Change request ditandai sedang ditinjau.",
    )
    return redirect("governance:change_detail", pk=change.pk)


@login_required
@require_POST
def change_apply(request, pk):
    change = _change(request, pk)
    _run(request, lambda: apply_change(change, request.user), "Perubahan diterapkan.")
    return redirect("governance:change_detail", pk=change.pk)


@login_required
def change_control(request, pk):
    from apps.projects.models import ActivityAction
    from apps.projects.services import record_activity

    project = _project(request, pk)
    if not can_manage_project(request.user, project):
        raise PermissionDenied
    form = ChangeControlForm(
        request.POST or None, initial={"change_control": project.change_control}
    )
    if request.method == "POST" and form.is_valid():
        value = form.cleaned_data["change_control"]
        if value != project.change_control:
            project.change_control = value
            project.save(update_fields=["change_control", "updated_at"])
            record_activity(
                project,
                request.user,
                ActivityAction.APPROVAL_POLICY,
                "Kontrol perubahan " + ("diaktifkan." if value else "dimatikan."),
            )
        messages.success(request, "Kontrol perubahan disimpan.")
        return redirect("governance:project_approvals", pk=project.pk)
    return _form_page(
        request,
        form,
        project,
        "Kontrol perubahan",
        reverse("governance:project_approvals", args=[project.pk]),
    )


# ------------------------------------------------------------ deliverable ---


def _deliverable(request, pk):
    return get_object_or_404(
        Deliverable.objects.select_related(
            "project", "task", "owner__pcc_profile", "reviewer__pcc_profile"
        ),
        pk=pk,
        project__in=visible_projects(request.user),
    )


@login_required
def project_deliverables(request, pk):
    from apps.projects.views import project_context

    project = _project(request, pk)
    items = list(
        project.deliverables.select_related("task", "owner__pcc_profile", "reviewer__pcc_profile")
    )
    counts = {value: 0 for value in DeliverableStatus.values}
    for item in items:
        counts[item.status] += 1
    return render(
        request,
        "governance/deliverables.html",
        {
            **project_context(request, project, "deliverables"),
            "deliverables": items,
            "counts": counts,
            "can_add": can_manage_deliverables(request.user, project),
        },
    )


@login_required
def deliverable_create(request, pk):
    project = _project(request, pk)
    if not can_manage_deliverables(request.user, project):
        raise PermissionDenied
    initial = {}
    if request.GET.get("task"):
        initial["task"] = request.GET["task"]
    form = DeliverableForm(request.POST or None, project=project, initial=initial)
    if request.method == "POST" and form.is_valid():
        item = form.save()
        from apps.projects.models import ActivityAction
        from apps.projects.services import record_activity

        record_activity(
            project,
            request.user,
            ActivityAction.DELIVERABLE_UPDATED,
            f'Deliverable "{item.name}" ditambahkan.',
        )
        messages.success(request, "Deliverable disimpan.")
        return redirect("governance:project_deliverables", pk=project.pk)
    return _form_page(
        request,
        form,
        project,
        "Tambah deliverable",
        reverse("governance:project_deliverables", args=[project.pk]),
    )


@login_required
def deliverable_edit(request, pk):
    from apps.projects.models import ActivityAction
    from apps.projects.services import record_activity

    item = _deliverable(request, pk)
    manage = can_manage_deliverables(request.user, item.project)
    if not (manage or item.owner_id == request.user.pk):
        raise PermissionDenied
    if item.status in (DeliverableStatus.SUBMITTED, DeliverableStatus.UNDER_REVIEW):
        messages.error(request, "Deliverable sedang ditinjau dan tidak dapat diubah.")
        return redirect("governance:deliverable_detail", pk=item.pk)
    form_class = DeliverableForm if manage else EvidenceForm
    kwargs = {"project": item.project} if manage else {}
    form = form_class(request.POST or None, instance=item, **kwargs)
    if request.method == "POST" and form.is_valid():
        form.save()
        record_activity(
            item.project,
            request.user,
            ActivityAction.DELIVERABLE_UPDATED,
            f'Deliverable "{item.name}" diperbarui.',
        )
        messages.success(request, "Deliverable disimpan.")
        return redirect("governance:deliverable_detail", pk=item.pk)
    return _form_page(
        request,
        form,
        item.project,
        item.name,
        reverse("governance:deliverable_detail", args=[item.pk]),
    )


@login_required
def deliverable_detail(request, pk):
    item = _deliverable(request, pk)
    return render(
        request,
        "governance/deliverable_detail.html",
        {
            "item": item,
            "project": item.project,
            "approvals": requests_for(ApprovalType.DELIVERABLE, item.pk),
            "can_edit": (
                can_manage_deliverables(request.user, item.project)
                or item.owner_id == request.user.pk
            )
            and item.status not in (DeliverableStatus.SUBMITTED, DeliverableStatus.UNDER_REVIEW),
            "can_submit": can_submit_deliverable(request.user, item)
            and item.status in (DeliverableStatus.DRAFT, DeliverableStatus.REJECTED),
            "my_turn": _my_turn(ApprovalType.DELIVERABLE, item, request.user),
        },
    )


@login_required
@require_POST
def deliverable_submit(request, pk):
    item = _deliverable(request, pk)
    _run(request, lambda: submit_deliverable(item, request.user), "Deliverable diajukan.")
    return redirect("governance:deliverable_detail", pk=item.pk)


@login_required
@require_POST
def deliverable_review(request, pk):
    item = _deliverable(request, pk)
    _run(
        request,
        lambda: start_review(item, request.user, ApprovalType.DELIVERABLE),
        "Deliverable ditandai sedang ditinjau.",
    )
    return redirect("governance:deliverable_detail", pk=item.pk)
