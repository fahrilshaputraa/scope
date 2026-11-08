"""Approval, review, change request, dan deliverable (PRD §14, §17, §18).

Semua persetujuan dibuat sebagai ``ApprovalRequest`` dengan satu atau lebih
``ApprovalStep``. Konfigurasi per project ada di ``ApprovalPolicy`` dan default-nya
mati, sehingga alur lama berjalan tanpa persetujuan sampai PM mengaktifkannya.
"""

from django.conf import settings
from django.db import models


class ApprovalType(models.TextChoices):
    PLAN = "plan", "Rencana project"
    BASELINE = "baseline", "Baseline"
    TASK = "task", "Pemeriksaan task"
    DELIVERABLE = "deliverable", "Penerimaan deliverable"
    CHANGE_REQUEST = "change_request", "Change request"
    CLOSURE = "closure", "Penutupan project"


#: Permission role aktif yang dibutuhkan untuk memutuskan tiap jenis persetujuan.
APPROVAL_PERMISSIONS = {
    ApprovalType.PLAN: "plan.approve",
    ApprovalType.BASELINE: "baseline.approve",
    ApprovalType.TASK: "task.review",
    ApprovalType.DELIVERABLE: "deliverable.accept",
    ApprovalType.CHANGE_REQUEST: "change_request.approve",
    ApprovalType.CLOSURE: "closure.approve",
}


class ApprovalMode(models.TextChoices):
    SEQUENTIAL = "sequential", "Berurutan"
    PARALLEL = "parallel", "Paralel (semua approver)"


class ApprovalPolicy(models.Model):
    """Konfigurasi satu jenis persetujuan pada satu project (BR-APR-001)."""

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="approval_policies"
    )
    approval_type = models.CharField(max_length=20, choices=ApprovalType.choices)
    enabled = models.BooleanField(default=False)
    mode = models.CharField(
        max_length=20, choices=ApprovalMode.choices, default=ApprovalMode.SEQUENTIAL
    )
    allow_self_approval = models.BooleanField(
        default=False, help_text="Izinkan pengaju menyetujui pengajuannya sendiri."
    )
    approvers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through="PolicyApprover", blank=True, related_name="+"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["project", "approval_type"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "approval_type"], name="unique_project_approval_policy"
            )
        ]

    def __str__(self):
        return f"{self.project_id}:{self.approval_type} ({'aktif' if self.enabled else 'mati'})"

    def ordered_approvers(self):
        return [row.user for row in self.approver_rows.select_related("user").order_by("sequence")]


class PolicyApprover(models.Model):
    policy = models.ForeignKey(
        ApprovalPolicy, on_delete=models.CASCADE, related_name="approver_rows"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    sequence = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["sequence", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["policy", "user"], name="unique_policy_approver")
        ]


class ApprovalStatus(models.TextChoices):
    PENDING = "pending", "Menunggu keputusan"
    APPROVED = "approved", "Disetujui"
    REJECTED = "rejected", "Ditolak"
    CANCELLED = "cancelled", "Dibatalkan"


class StepStatus(models.TextChoices):
    PENDING = "pending", "Menunggu"
    APPROVED = "approved", "Disetujui"
    REJECTED = "rejected", "Ditolak"
    SKIPPED = "skipped", "Tidak diperlukan"


class ApprovalRequest(models.Model):
    """Satu pengajuan persetujuan. Riwayatnya tidak dihapus (BR-APR-005)."""

    #: Notifikasi pengajuan hanya untuk approver dan pengaju, bukan pengikut project.
    notify_watchers = False
    notification_target = "approval"

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="approval_requests"
    )
    approval_type = models.CharField(max_length=20, choices=ApprovalType.choices)
    target_id = models.PositiveBigIntegerField()
    target_repr = models.CharField(max_length=200, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    requested_role = models.CharField(max_length=20, blank=True, default="")
    mode = models.CharField(
        max_length=20, choices=ApprovalMode.choices, default=ApprovalMode.SEQUENTIAL
    )
    allow_self_approval = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["approval_type", "target_id", "status"], name="approval_target_idx"
            )
        ]

    def __str__(self):
        return f"{self.get_approval_type_display()}: {self.target_repr}"

    @property
    def is_pending(self):
        return self.status == ApprovalStatus.PENDING


class ApprovalStep(models.Model):
    """Keputusan satu approver. Alasan wajib bila menolak (BR-APR-004)."""

    request = models.ForeignKey(ApprovalRequest, on_delete=models.CASCADE, related_name="steps")
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="approval_steps"
    )
    sequence = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=20, choices=StepStatus.choices, default=StepStatus.PENDING)
    reason = models.TextField(blank=True)
    active_role = models.CharField(max_length=20, blank=True, default="")
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["sequence", "pk"]

    def __str__(self):
        return f"step {self.sequence} of {self.request_id} by {self.approver_id}"


class ChangeClassification(models.TextChoices):
    MINOR = "minor", "Minor"
    MAJOR = "major", "Major"


class ChangeStatus(models.TextChoices):
    DRAFT = "draft", "Draf"
    SUBMITTED = "submitted", "Diajukan"
    UNDER_REVIEW = "under_review", "Sedang ditinjau"
    APPROVED = "approved", "Disetujui"
    REJECTED = "rejected", "Ditolak"
    APPLIED = "applied", "Diterapkan"


class ChangeRequest(models.Model):
    """Pengajuan perubahan scope/jadwal (PRD §17.3, BR-CHG-002 sampai 006)."""

    notification_target = "change_request"

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="change_requests"
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    reason = models.TextField()
    impact_assessment = models.TextField()
    schedule_impact = models.TextField(blank=True)
    scope_impact = models.TextField(blank=True)
    classification = models.CharField(
        max_length=10, choices=ChangeClassification.choices, default=ChangeClassification.MAJOR
    )
    proposed_end_date = models.DateField(
        null=True, blank=True, help_text="Target selesai project yang baru bila disetujui."
    )
    status = models.CharField(
        max_length=20, choices=ChangeStatus.choices, default=ChangeStatus.DRAFT
    )
    applied_baseline = models.ForeignKey(
        "projects.Baseline",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="change_requests",
    )
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    applied_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"CR-{self.pk}: {self.title}"


class DeliverableStatus(models.TextChoices):
    DRAFT = "draft", "Draf"
    SUBMITTED = "submitted", "Diajukan"
    UNDER_REVIEW = "under_review", "Sedang ditinjau"
    ACCEPTED = "accepted", "Diterima"
    REJECTED = "rejected", "Ditolak"


class Deliverable(models.Model):
    """Output pekerjaan yang diserahkan dan diterima (PRD §14, §26.12)."""

    notification_target = "deliverable"

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="deliverables"
    )
    task = models.ForeignKey(
        "work.Task", null=True, blank=True, on_delete=models.SET_NULL, related_name="deliverables"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    acceptance_criteria = models.TextField()
    evidence = models.TextField(
        blank=True, help_text="Tautan dokumen, lokasi berkas, atau ringkasan bukti hasil kerja."
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_deliverables",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_deliverables",
    )
    due_date = models.DateField(null=True, blank=True)
    submission_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=DeliverableStatus.choices, default=DeliverableStatus.DRAFT
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_date", "id"]

    def __str__(self):
        return self.name

    def clean(self):
        from django.core.exceptions import ValidationError

        super().clean()
        if self.task_id and self.project_id and self.task.project_id != self.project_id:
            raise ValidationError({"task": "Pilih task dari project yang sama."})
        if self.project_id:
            from .changes import guard_major_change

            guard_major_change(self, "deliverable", self.project)
