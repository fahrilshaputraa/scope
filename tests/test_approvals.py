"""Fase 5: approval yang dapat dikonfigurasi, review task, Approvals dan My Reviews."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.governance.models import (
    ApprovalMode,
    ApprovalRequest,
    ApprovalStatus,
    ApprovalType,
    StepStatus,
)
from apps.governance.services import (
    actionable_steps,
    decide,
    request_approval,
    save_policy,
    submit_task,
)
from apps.identity.models import Role
from apps.identity.roles import assign_roles, set_active_role
from apps.notifications.models import Notification
from apps.projects.models import (
    ActivityEvent,
    BaselineStatus,
    LifecycleStatus,
    Project,
)
from apps.projects.services import capture_baseline, current_baseline
from apps.work.models import Task, TaskComment, TaskStatus

pytestmark = pytest.mark.django_db
TODAY = timezone.localdate()


def make_user(name, *roles, **extra):
    user = User.objects.create_user(name, password="valid-password", **extra)
    assign_roles(user, list(roles))
    return user


@pytest.fixture
def world():
    pm = make_user("pm", Role.PROJECT_MANAGER)
    worker = make_user("worker", Role.MEMBER)
    peer = make_user("peer", Role.MEMBER)
    owner = make_user("sponsor", Role.OWNER)
    director = make_user("director", Role.OWNER)
    project = Project.objects.create(
        name="Alpha",
        code="ALPHA",
        manager=pm,
        owner=owner,
        lifecycle_status=LifecycleStatus.IN_PROGRESS,
        start_date=TODAY - timedelta(days=10),
        target_end_date=TODAY + timedelta(days=30),
    )
    project.members.add(worker, peer, director)
    return {
        "pm": pm,
        "worker": worker,
        "peer": peer,
        "owner": owner,
        "director": director,
        "project": project,
    }


def dated_task(project, title="Build", **extra):
    return Task.objects.create(
        project=project,
        title=title,
        start_date=TODAY,
        due_date=TODAY + timedelta(days=5),
        **extra,
    )


def enable(project, kind, actor, *approvers, mode=ApprovalMode.SEQUENTIAL, allow_self=False):
    return save_policy(
        project,
        kind,
        enabled=True,
        mode=mode,
        allow_self=allow_self,
        approvers=list(approvers),
        actor=actor,
    )


# --------------------------------------------------------------- defaults


def test_everything_is_off_by_default(world, client):
    project = world["project"]
    dated_task(project)
    baseline = capture_baseline(project, world["pm"])
    assert baseline.status == BaselineStatus.ACTIVE
    task = dated_task(project, "Direct", assignee=world["worker"])
    client.force_login(world["worker"])
    response = client.post(reverse("work:task_status", args=[task.pk]), {"status": "done"})
    assert response.status_code == 200
    task.refresh_from_db()
    assert task.status == TaskStatus.DONE
    assert not ApprovalRequest.objects.exists()


# ------------------------------------------------------------- task review


def test_task_with_reviewer_follows_submit_review_approve(world, client):
    task = dated_task(
        world["project"], assignee=world["worker"], reviewer=world["peer"], status="in_progress"
    )
    client.force_login(world["worker"])
    blocked = client.post(reverse("work:task_status", args=[task.pk]), {"status": "done"})
    assert blocked.status_code == 400
    assert "diperiksa" in blocked.json()["error"]

    response = client.post(reverse("governance:task_submit", args=[task.pk]), {"note": "Siap"})
    assert response.status_code == 302
    task.refresh_from_db()
    assert task.status == TaskStatus.REVIEW
    approval = ApprovalRequest.objects.get(approval_type=ApprovalType.TASK, target_id=task.pk)
    assert approval.note == "Siap"
    assert Notification.objects.filter(recipient=world["peer"], verb="approval.requested").exists()

    client.force_login(world["peer"])
    queue = client.get(reverse("governance:my_reviews"))
    assert task.title in queue.content.decode()
    client.post(reverse("governance:approval_quick", args=[approval.pk]))
    task.refresh_from_db()
    approval.refresh_from_db()
    assert task.status == TaskStatus.DONE and task.progress == 100
    assert approval.status == ApprovalStatus.APPROVED
    assert not actionable_steps(world["peer"]).exists()
    assert task.title not in client.get(reverse("governance:my_reviews")).content.decode()
    assert Notification.objects.filter(recipient=world["worker"], verb="approval.decided").exists()


def test_rejection_requires_reason_and_returns_task_to_work(world, client):
    task = dated_task(
        world["project"], assignee=world["worker"], reviewer=world["peer"], status="in_progress"
    )
    submit_task(task, world["worker"])
    approval = ApprovalRequest.objects.get(target_id=task.pk, approval_type=ApprovalType.TASK)
    step = approval.steps.get()
    with pytest.raises(ValidationError):
        decide(step, world["peer"], False, "  ")
    client.force_login(world["peer"])
    page = reverse("governance:approval_detail", args=[approval.pk])
    response = client.post(page, {"decision": "reject", "reason": ""})
    assert response.status_code == 200 and "wajib" in response.content.decode()
    client.post(page, {"decision": "reject", "reason": "Uji belum lengkap"})
    task.refresh_from_db()
    step.refresh_from_db()
    assert task.status == TaskStatus.IN_PROGRESS
    assert step.status == StepStatus.REJECTED and step.reason == "Uji belum lengkap"
    assert TaskComment.objects.filter(task=task, content__contains="Uji belum lengkap").exists()
    assert ActivityEvent.objects.filter(action="approval.rejected").exists()


def test_reviewer_must_differ_from_assignee_and_assignee_cannot_self_approve(world):
    task = Task(
        project=world["project"],
        title="Self",
        assignee=world["worker"],
        reviewer=world["worker"],
    )
    with pytest.raises(ValidationError) as exc:
        task.full_clean(exclude=["dependencies"])
    assert "reviewer" in exc.value.message_dict
    # Policy aktif tanpa reviewer: PM menjadi pemeriksa, bukan pelaksana.
    enable(world["project"], ApprovalType.TASK, world["pm"])
    task = dated_task(world["project"], "Via policy", assignee=world["worker"])
    approval = submit_task(task, world["worker"])
    assert [s.approver for s in approval.steps.all()] == [world["pm"]]
    with pytest.raises(PermissionDenied):
        decide(approval.steps.get(), world["worker"], True)


def test_moving_task_out_of_review_cancels_pending_request(world, client):
    task = dated_task(
        world["project"], assignee=world["worker"], reviewer=world["peer"], status="in_progress"
    )
    client.force_login(world["worker"])
    client.post(reverse("work:task_status", args=[task.pk]), {"status": "review"})
    approval = ApprovalRequest.objects.get(target_id=task.pk, approval_type=ApprovalType.TASK)
    assert approval.status == ApprovalStatus.PENDING
    client.post(reverse("work:task_status", args=[task.pk]), {"status": "in_progress"})
    approval.refresh_from_db()
    assert approval.status == ApprovalStatus.CANCELLED


# ------------------------------------------------------- sequential/parallel


def test_sequential_baseline_approval(world):
    project = world["project"]
    dated_task(project)
    enable(project, ApprovalType.BASELINE, world["pm"], world["owner"], world["director"])
    baseline = capture_baseline(project, world["pm"])
    assert baseline.status == BaselineStatus.PENDING
    assert current_baseline(project) is None  # kurva otomatis hanya draf sampai disetujui
    approval = ApprovalRequest.objects.get(approval_type=ApprovalType.BASELINE)
    first, second = approval.steps.all()
    assert list(actionable_steps(world["director"])) == []
    with pytest.raises(PermissionDenied):
        decide(second, world["director"], True)
    decide(first, world["owner"], True)
    baseline.refresh_from_db()
    assert baseline.status == BaselineStatus.PENDING
    assert list(actionable_steps(world["director"])) == [second]
    decide(second, world["director"], True)
    baseline.refresh_from_db()
    assert baseline.status == BaselineStatus.ACTIVE and baseline.approved_by == world["director"]
    assert project.baseline_points.exists()
    with pytest.raises(ValidationError):
        # Hanya satu pengajuan baseline yang boleh menunggu.
        capture_baseline(project, world["pm"])
        capture_baseline(project, world["pm"])


def test_parallel_rejection_by_one_approver_rejects_baseline(world):
    project = world["project"]
    dated_task(project)
    enable(
        project,
        ApprovalType.BASELINE,
        world["pm"],
        world["owner"],
        world["director"],
        mode=ApprovalMode.PARALLEL,
    )
    baseline = capture_baseline(project, world["pm"])
    assert {s.request_id for s in actionable_steps(world["director"])} == {
        s.request_id for s in actionable_steps(world["owner"])
    }
    step = actionable_steps(world["director"]).get()
    decide(step, world["director"], False, "Jadwal terlalu padat")
    baseline.refresh_from_db()
    assert baseline.status == BaselineStatus.REJECTED
    assert not actionable_steps(world["owner"]).exists()


def test_self_approval_follows_policy(world):
    project = world["project"]
    assign_roles(world["pm"], [Role.PROJECT_MANAGER, Role.OWNER])
    dated_task(project)
    enable(project, ApprovalType.BASELINE, world["pm"], world["pm"])
    with pytest.raises(ValidationError):
        capture_baseline(project, world["pm"])  # satu-satunya approver adalah pengaju
    enable(project, ApprovalType.BASELINE, world["pm"], world["pm"], allow_self=True)
    baseline = capture_baseline(project, world["pm"])
    step = actionable_steps(world["pm"]).get()
    with pytest.raises(PermissionDenied):
        decide(step, world["pm"], True)  # role aktif PM tidak punya baseline.approve
    set_active_role(world["pm"], Role.OWNER)
    decide(step, world["pm"], True)
    baseline.refresh_from_db()
    assert baseline.status == BaselineStatus.ACTIVE


# ------------------------------------------------------------ plan/closure


def test_plan_approval_gates_project_start(world):
    project = Project.objects.create(
        name="Beta",
        code="BETA",
        manager=world["pm"],
        owner=world["owner"],
        lifecycle_status=LifecycleStatus.PLANNING,
        start_date=TODAY,
        target_end_date=TODAY + timedelta(days=20),
    )
    dated_task(project)
    capture_baseline(project, world["pm"])
    enable(project, ApprovalType.PLAN, world["pm"])
    project.lifecycle_status = LifecycleStatus.IN_PROGRESS
    with pytest.raises(ValidationError) as exc:
        project.full_clean()
    assert "belum disetujui" in str(exc.value)
    approval = request_approval(project, ApprovalType.PLAN, project, world["pm"])
    decide(approval.steps.get(), world["owner"], True)
    project.full_clean()


def test_closure_approval_completes_project(world, client):
    project = world["project"]
    dated_task(project, status=TaskStatus.DONE)
    enable(project, ApprovalType.CLOSURE, world["pm"])
    project.lifecycle_status = LifecycleStatus.COMPLETED
    with pytest.raises(ValidationError):
        project.full_clean()
    project.refresh_from_db()
    client.force_login(world["pm"])
    client.post(reverse("governance:request_closure", args=[project.pk]))
    approval = ApprovalRequest.objects.get(approval_type=ApprovalType.CLOSURE)
    decide(approval.steps.get(), world["owner"], True)
    project.refresh_from_db()
    assert project.lifecycle_status == LifecycleStatus.COMPLETED


# ------------------------------------------------------------------ pages


def test_policy_page_requires_configure_permission_and_logs_change(world, client):
    project = world["project"]
    url = reverse("governance:policy_edit", args=[project.pk, "task"])
    client.force_login(world["worker"])
    assert client.get(url).status_code == 403
    client.force_login(world["pm"])
    assert client.get(url).status_code == 200
    response = client.post(
        url, {"enabled": "on", "mode": "parallel", "approver_1": world["peer"].pk}
    )
    assert response.status_code == 302
    policy = project.approval_policies.get(approval_type="task")
    assert policy.enabled and policy.mode == "parallel"
    assert policy.ordered_approvers() == [world["peer"]]
    assert ActivityEvent.objects.filter(action="approval.policy").exists()
    tab = client.get(reverse("governance:project_approvals", args=[project.pk]))
    assert tab.status_code == 200 and "data-approval-policies" in tab.content.decode()


def test_inbox_and_owner_dashboard_show_pending_decisions(world, client):
    project = world["project"]
    dated_task(project)
    enable(project, ApprovalType.BASELINE, world["pm"])
    capture_baseline(project, world["pm"])
    client.force_login(world["owner"])
    inbox = client.get(reverse("governance:approval_inbox")).content.decode()
    assert "Baseline v1" in inbox
    dashboard = client.get(reverse("projects:dashboard")).content.decode()
    assert "Keputusan tertunda" in dashboard and "Baseline v1" in dashboard
    approval = ApprovalRequest.objects.get()
    client.post(reverse("governance:approval_quick", args=[approval.pk]))
    after = client.get(reverse("governance:approval_inbox")).content.decode()
    queue = after.split("data-approval-queue", 1)[1].split("</section>", 1)[0]
    assert "Baseline v1" not in queue and "Keputusan terakhir Anda" in after


def test_outsider_cannot_open_or_decide(world, client):
    project = world["project"]
    dated_task(project)
    enable(project, ApprovalType.BASELINE, world["pm"])
    capture_baseline(project, world["pm"])
    approval = ApprovalRequest.objects.get()
    stranger = make_user("stranger", Role.OWNER)
    client.force_login(stranger)
    assert client.get(reverse("governance:approval_detail", args=[approval.pk])).status_code == 404
    assert client.post(reverse("governance:approval_quick", args=[approval.pk])).status_code == 404
