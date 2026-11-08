from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from .managers import ArchivableModel


class LifecycleStatus(models.TextChoices):
    """Status keberadaan project (PRD §7.2). Kondisi pelaksanaan ada di ``HealthStatus``."""

    DRAFT = "draft", "Draf"
    PLANNING = "planning", "Perencanaan"
    IN_PROGRESS = "in_progress", "Berjalan"
    ON_HOLD = "on_hold", "Ditahan"
    COMPLETED = "completed", "Selesai"
    CANCELLED = "cancelled", "Dibatalkan"


#: Lifecycle yang sudah tidak berjalan: tidak dihitung overdue, snapshot, atau health.
CLOSED_LIFECYCLE = (LifecycleStatus.COMPLETED, LifecycleStatus.CANCELLED)
#: Lifecycle yang kondisi pelaksanaannya dinilai (health).
ASSESSED_LIFECYCLE = (LifecycleStatus.IN_PROGRESS, LifecycleStatus.ON_HOLD)


class HealthStatus(models.TextChoices):
    """Kondisi pelaksanaan project, dihitung dari data (PRD §7.2, §11.7)."""

    ON_TRACK = "on_track", "Sesuai rencana"
    AT_RISK = "at_risk", "Perlu perhatian"
    DELAYED = "delayed", "Terlambat"
    CRITICAL = "critical", "Kritis"


class PhaseStatus(models.TextChoices):
    NOT_STARTED = "not_started", "Not Started"
    IN_PROGRESS = "in_progress", "In Progress"
    COMPLETED = "completed", "Completed"


class MilestoneStatus(models.TextChoices):
    UPCOMING = "upcoming", "Upcoming"
    IN_PROGRESS = "in_progress", "In Progress"
    COMPLETED = "completed", "Completed"
    DELAYED = "delayed", "Delayed"


class ActivityAction(models.TextChoices):
    PROJECT_CREATED = "project.created", "Project created"
    PROJECT_UPDATED = "project.updated", "Project updated"
    TIMELINE_CHANGED = "timeline.changed", "Timeline changed"
    BASELINE_UPDATED = "baseline.updated", "Baseline updated"
    PROGRESS_UPDATED = "progress.updated", "Progress updated"
    PHASE_ADDED = "phase.added", "Phase added"
    PHASE_UPDATED = "phase.updated", "Phase updated"
    MILESTONE_ADDED = "milestone.added", "Milestone added"
    MILESTONE_COMPLETED = "milestone.completed", "Milestone completed"
    MILESTONE_UPDATED = "milestone.updated", "Milestone updated"
    NOTE_ADDED = "note.added", "Note added"
    NOTE_UPDATED = "note.updated", "Note updated"
    DECISION_ADDED = "decision.added", "Decision added"
    TASK_CREATED = "task.created", "Task created"
    TASK_UPDATED = "task.updated", "Task updated"
    TASK_STATUS = "task.status", "Task status changed"
    TASK_ASSIGNED = "task.assigned", "Task assigned"
    COMMENT_ADDED = "comment.added", "Comment added"
    ISSUE_CREATED = "issue.created", "Issue created"
    ISSUE_ASSIGNED = "issue.assigned", "Issue assigned"
    ISSUE_UPDATED = "issue.updated", "Issue updated"
    ISSUE_RESOLVED = "issue.resolved", "Issue resolved"
    PROJECT_ARCHIVED = "project.archived", "Project archived"
    PROJECT_RESTORED = "project.restored", "Project restored"
    PHASE_ARCHIVED = "phase.archived", "Phase archived"
    PHASE_RESTORED = "phase.restored", "Phase restored"
    TASK_ARCHIVED = "task.archived", "Task archived"
    TASK_RESTORED = "task.restored", "Task restored"
    ISSUE_ARCHIVED = "issue.archived", "Issue archived"
    ISSUE_RESTORED = "issue.restored", "Issue restored"
    HISTORY_RESTORED = "history.restored", "History restored"
    APPROVAL_REQUESTED = "approval.requested", "Approval requested"
    APPROVAL_APPROVED = "approval.approved", "Approval approved"
    APPROVAL_REJECTED = "approval.rejected", "Approval rejected"
    APPROVAL_CANCELLED = "approval.cancelled", "Approval cancelled"
    APPROVAL_POLICY = "approval.policy", "Approval configuration changed"
    CHANGE_REQUEST_UPDATED = "change_request.updated", "Change request updated"
    CHANGE_REQUEST_APPLIED = "change_request.applied", "Change request applied"
    MAJOR_CHANGE = "change.major", "Major change recorded"
    DELIVERABLE_UPDATED = "deliverable.updated", "Deliverable updated"
    DELIVERABLE_ACCEPTED = "deliverable.accepted", "Deliverable accepted"
    DELIVERABLE_REJECTED = "deliverable.rejected", "Deliverable rejected"
    RISK_UPDATED = "risk.updated", "Risk updated"
    RISK_CONVERTED = "risk.converted", "Risk converted to issue"
    STRUCTURE_UPDATED = "structure.updated", "Structure updated"
    WEIGHTS_UPDATED = "weights.updated", "Weights updated"
    TEMPLATE_APPLIED = "template.applied", "Template applied"


class ProjectType(models.TextChoices):
    GENERAL = "general", "Umum"
    SOFTWARE = "software", "Pengembangan perangkat lunak"
    INFRASTRUCTURE = "infrastructure", "Infrastruktur"
    IMPLEMENTATION = "implementation", "Implementasi untuk client"
    RESEARCH = "research", "Riset dan kajian"
    OPERATIONAL = "operational", "Operasional dan perbaikan proses"


class WeightMode(models.TextChoices):
    AUTO = "auto", "Otomatis dibagi rata"
    MANUAL = "manual", "Diatur manual"


class Project(ArchivableModel):
    """Project utama (PRD §31)."""

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=40, unique=True)
    description = models.TextField(blank=True)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_projects",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_projects",
        help_text="Penanggung jawab outcome project (Project Owner).",
    )
    workspace = models.ForeignKey(
        "identity.Workspace",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="projects",
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="member_projects",
        through="ProjectMembership",
    )
    team = models.CharField(max_length=100, blank=True)
    start_date = models.DateField()
    target_end_date = models.DateField()
    actual_end_date = models.DateField(null=True, blank=True)
    lifecycle_status = models.CharField(
        max_length=20, choices=LifecycleStatus.choices, default=LifecycleStatus.PLANNING
    )
    cancellation_reason = models.TextField(
        blank=True, help_text="Wajib diisi saat project dibatalkan."
    )
    current_phase = models.ForeignKey(
        "Phase",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    # Manual PM adjustment untuk actual progress (PRD §10.4); NULL = hitung dari task.
    progress_override = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    public_token = models.UUIDField(default=uuid4, unique=True, editable=False)
    is_public = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    public_expires_at = models.DateTimeField(null=True, blank=True)
    public_password_hash = models.CharField(max_length=255, blank=True, default="")
    public_hide_task_titles = models.BooleanField(default=False)
    change_control = models.BooleanField(
        default=False,
        help_text="Bila aktif, perubahan major setelah baseline harus melalui change request.",
    )
    project_type = models.CharField(
        max_length=30, choices=ProjectType.choices, default=ProjectType.GENERAL
    )
    custom_fields = models.JSONField(
        default=list, blank=True, help_text="Definisi field tambahan: key, label, type."
    )
    custom_values = models.JSONField(default=dict, blank=True)
    progress_config = models.JSONField(
        default=dict, blank=True, help_text="Persentase metode status-based per status."
    )
    weight_mode = models.CharField(
        max_length=10, choices=WeightMode.choices, default=WeightMode.MANUAL
    )
    template = models.ForeignKey(
        "ProjectTemplate", null=True, blank=True, on_delete=models.SET_NULL, related_name="projects"
    )
    template_version = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} — {self.name}"

    def clean(self):
        super().clean()
        if self.start_date and self.target_end_date and self.target_end_date < self.start_date:
            raise ValidationError({"target_end_date": "Tanggal akhir harus setelah tanggal mulai."})
        if self.current_phase_id and self.current_phase.project_id != self.pk:
            raise ValidationError({"current_phase": "Phase harus berasal dari project yang sama."})
        from apps.governance.changes import guard_major_change

        guard_major_change(self, "project", self)
        self._validate_lifecycle()

    def _validate_lifecycle(self):
        """Aturan status project (PRD §7.3, BR-PROJ-003 sampai 007)."""
        from .services import closure_requirements, planning_requirements

        previous = None
        if self.pk:
            previous = (
                Project.all_objects.filter(pk=self.pk)
                .values_list("lifecycle_status", flat=True)
                .first()
            )
        status = self.lifecycle_status
        if previous is None and status not in (LifecycleStatus.DRAFT, LifecycleStatus.PLANNING):
            raise ValidationError(
                {"lifecycle_status": "Project baru harus dimulai dari Draf atau Perencanaan."}
            )
        if status == previous:
            return
        if status == LifecycleStatus.IN_PROGRESS:
            unmet = planning_requirements(self)
            if unmet:
                raise ValidationError(
                    {"lifecycle_status": "Belum bisa berjalan: " + "; ".join(unmet) + "."}
                )
        elif status == LifecycleStatus.COMPLETED:
            unmet = closure_requirements(self)
            if unmet:
                raise ValidationError(
                    {"lifecycle_status": "Belum bisa diselesaikan: " + "; ".join(unmet) + "."}
                )
            from apps.governance.services import closure_gate

            gate = closure_gate(self)
            if gate:
                raise ValidationError({"lifecycle_status": gate})
        elif status == LifecycleStatus.CANCELLED and not self.cancellation_reason.strip():
            raise ValidationError({"cancellation_reason": "Alasan pembatalan wajib diisi."})

    # --- Progress (dihitung live, PRD §10/§11/§12/§32) ---

    @property
    def planned_progress(self):
        """Planned progress (%) pada hari ini dari baseline points. None bila belum ada baseline."""
        from .services import planned_progress_on

        return planned_progress_on(self)

    @property
    def actual_progress(self):
        """Actual progress (%) berdasarkan weighted task, atau override PM."""
        from .services import actual_progress

        return actual_progress(self)

    @property
    def variance(self):
        from .services import variance

        return variance(self)

    @property
    def variance_level(self):
        from .services import variance_level

        return variance_level(self)

    @property
    def is_overdue(self):
        from django.utils import timezone

        if self.lifecycle_status in CLOSED_LIFECYCLE:
            return False
        return self.target_end_date < timezone.localdate()

    @property
    def next_milestone(self):
        # Python atas ``all()``: tanpa query tambahan bila milestone sudah di-prefetch.
        pending = [m for m in self.milestones.all() if m.status != MilestoneStatus.COMPLETED]
        return min(pending, key=lambda m: (m.date, m.pk), default=None)

    @property
    def effective_current_phase(self):
        """Phase aktif: explicit current_phase, atau derive dari phase yang belum selesai."""
        if self.current_phase_id:
            return self.current_phase
        phases = sorted(self.phases.all(), key=lambda p: (p.sequence, p.pk))
        active = [p for p in phases if p.status != PhaseStatus.COMPLETED]
        return active[0] if active else (phases[-1] if phases else None)

    @property
    def health_status(self):
        """Kondisi pelaksanaan (HealthStatus) atau None bila belum dinilai."""
        from .services import health_status

        return health_status(self)

    def get_health_status_display(self):
        value = self.health_status
        return HealthStatus(value).label if value else "—"

    def health(self):
        """Ringkasan project health untuk Overview (PRD §9.1)."""
        from .services import project_health

        return project_health(self)


class ProjectRole(models.TextChoices):
    MEMBER = "member", "Anggota"
    CLIENT = "client", "Client / Stakeholder"


class ProjectMembership(models.Model):
    """Keanggotaan user pada project beserta perannya (PRD §26.6)."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_memberships"
    )
    project_role = models.CharField(
        max_length=20, choices=ProjectRole.choices, default=ProjectRole.MEMBER
    )
    status = models.CharField(max_length=20, default="active")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["joined_at", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["project", "user"], name="unique_project_member")
        ]

    def __str__(self):
        return f"{self.user_id} in {self.project_id} ({self.project_role})"


class Phase(ArchivableModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="phases")
    name = models.CharField(max_length=200)
    sequence = models.PositiveIntegerField(default=1)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=PhaseStatus.choices, default=PhaseStatus.NOT_STARTED
    )

    class Meta:
        ordering = ["sequence", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "sequence"],
                condition=models.Q(archived_at__isnull=True),
                name="unique_active_phase_sequence",
            )
        ]

    def __str__(self):
        return f"P{self.sequence} — {self.name}"

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "Tanggal selesai phase harus setelah mulai."})

    @property
    def progress(self):
        """Weighted progress task dalam phase ini (%)."""
        from apps.work.progress import weighted_progress

        return weighted_progress(
            self.tasks.filter(parent_task__isnull=True).prefetch_related("subtasks"), empty=None
        )

    def archive(self, user=None, at=None):
        if self.archived_at:
            return False
        at = at or timezone.now()
        super().archive(user=user, at=at)
        from apps.work.models import Task

        for task in Task.all_objects.filter(
            phase=self, parent_task__isnull=True, archived_at__isnull=True
        ):
            task.archive(user=user, at=at)
        Project.all_objects.filter(pk=self.project_id, current_phase=self).update(
            current_phase=None
        )
        return True

    def restore(self):
        if not self.archived_at:
            return False
        at = self.archived_at
        super().restore()
        from apps.work.models import Task

        for task in Task.all_objects.filter(phase=self, parent_task__isnull=True, archived_at=at):
            task.restore()
        return True


class Milestone(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="milestones")
    name = models.CharField(max_length=200)
    date = models.DateField()
    status = models.CharField(
        max_length=20, choices=MilestoneStatus.choices, default=MilestoneStatus.UPCOMING
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "id"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.project_id:
            from apps.governance.changes import guard_major_change

            guard_major_change(self, "milestone", self.project)


class ProgressBaselinePoint(models.Model):
    """Titik planned progress baseline (PRD §11) — membentuk planned progress curve."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="baseline_points")
    date = models.DateField()
    planned_percent = models.DecimalField(
        max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    label = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["date"]
        unique_together = [("project", "date")]

    def __str__(self):
        return f"{self.date} → {self.planned_percent}%"


class BaselineStatus(models.TextChoices):
    ACTIVE = "active", "Berlaku"
    SUPERSEDED = "superseded", "Digantikan"
    PENDING = "pending", "Menunggu persetujuan"
    REJECTED = "rejected", "Ditolak"


class Baseline(models.Model):
    """Versi baseline project (PRD §11.5, §12.4). Versi lama tidak pernah dihapus.

    ``baseline_data`` adalah snapshot beku: jadwal task, bobot, phase, milestone,
    dan kurva planned progress pada saat baseline dibuat.
    """

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="baselines")
    version = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20, choices=BaselineStatus.choices, default=BaselineStatus.ACTIVE
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=300, blank=True)
    baseline_data = models.JSONField(default=dict)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Approver terakhir bila baseline melalui persetujuan.",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-version"]
        unique_together = [("project", "version")]

    def __str__(self):
        return f"{self.project.code} baseline v{self.version}"

    @property
    def label(self):
        return f"v{self.version}"


class ProgressSnapshot(models.Model):
    """Snapshot progress harian untuk historical chart (PRD §34)."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="snapshots")
    date = models.DateField()
    planned_progress = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    actual_progress = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    variance = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    baseline = models.ForeignKey(
        Baseline, null=True, blank=True, on_delete=models.SET_NULL, related_name="snapshots"
    )
    health_status = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date"]
        unique_together = [("project", "date")]

    def __str__(self):
        return f"{self.date}: {self.planned_progress}% / {self.actual_progress}%"


class Note(models.Model):
    """Project notes (PRD §23): meeting, requirement, decision context, dll."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="notes")
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    tags = models.CharField(max_length=200, blank=True, help_text="Comma-separated tags")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]


class Decision(models.Model):
    """Decision Log (PRD §24)."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="decisions")
    title = models.CharField(max_length=200)
    decision = models.TextField()
    context = models.TextField(blank=True)
    reason = models.TextField(blank=True)
    impact = models.TextField(blank=True)
    decision_maker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    related_issue = models.ForeignKey(
        "work.Issue",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="decisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if self.related_issue_id and self.project_id:
            if self.related_issue.project_id != self.project_id:
                raise ValidationError({"related_issue": "Pilih issue dari project yang sama."})


class ActivityEvent(models.Model):
    """Activity log project (PRD §25)."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="activities")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    action = models.CharField(max_length=40, choices=ActivityAction.choices)
    active_role = models.CharField(max_length=20, blank=True, default="")
    message = models.CharField(max_length=300)
    object_repr = models.CharField(max_length=200, blank=True)
    entity_type = models.CharField(max_length=30, blank=True, default="")
    entity_id = models.PositiveBigIntegerField(null=True, blank=True)
    reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"], name="activity_entity_idx"),
        ]

    def __str__(self):
        return f"[{self.action}] {self.message}"


class RevisionEntity(models.TextChoices):
    PROJECT = "project", "Project"
    TASK = "task", "Task"
    MILESTONE = "milestone", "Milestone"
    ISSUE = "issue", "Issue"
    RISK = "risk", "Risk"
    DELIVERABLE = "deliverable", "Deliverable"
    CHANGE_REQUEST = "change_request", "Change request"


class RevisionAction(models.TextChoices):
    CREATED = "created", "Dibuat"
    UPDATED = "updated", "Diperbarui"
    RESTORED = "restored", "Dipulihkan"


class Revision(models.Model):
    """Field-level history untuk project, task, milestone, issue, dan risk."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="revisions")
    entity = models.CharField(max_length=20, choices=RevisionEntity.choices)
    object_id = models.PositiveBigIntegerField()
    object_repr = models.CharField(max_length=200, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    action = models.CharField(
        max_length=20, choices=RevisionAction.choices, default=RevisionAction.UPDATED
    )
    active_role = models.CharField(max_length=20, blank=True, default="")
    changes = models.JSONField(default=dict, blank=True)
    summary = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["entity", "object_id", "-created_at"],
                name="rev_entity_object_created_idx",
            )
        ]

    def __str__(self):
        return f"[{self.action}] {self.entity}:{self.object_id}"


#: Skala probability dan impact 1–5 (PRD §16.1).
RISK_SCALE = [
    (1, "1 — Sangat rendah"),
    (2, "2 — Rendah"),
    (3, "3 — Sedang"),
    (4, "4 — Tinggi"),
    (5, "5 — Sangat tinggi"),
]
#: Pemetaan ``severity`` lama ke probability/impact (migrasi 0017, didokumentasikan di roadmap).
SEVERITY_TO_SCALE = {"low": (2, 2), "medium": (3, 3), "high": (4, 4), "critical": (5, 5)}


def risk_level(score: int) -> str:
    """Tingkat risiko dari skor 1–25: rendah ≤4, sedang ≤9, tinggi ≤16, kritis ≥17."""
    if score >= 17:
        return "critical"
    if score >= 10:
        return "high"
    if score >= 5:
        return "medium"
    return "low"


class Risk(models.Model):
    """Risiko: potensi kejadian (PRD §16). ``severity`` diturunkan dari skor."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="risks")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    probability = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=RISK_SCALE,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    impact = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=RISK_SCALE,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    score = models.PositiveSmallIntegerField(default=9, editable=False)
    severity = models.CharField(
        max_length=20,
        choices=[("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")],
        default="medium",
        editable=False,
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ("open", "Open"),
            ("mitigated", "Mitigated"),
            ("closed", "Closed"),
            ("converted", "Menjadi masalah"),
        ],
        default="open",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    mitigation = models.TextField(blank=True)
    review_date = models.DateField(null=True, blank=True)
    issue = models.ForeignKey(
        "work.Issue",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="source_risks",
        help_text="Issue hasil konversi saat risiko benar-benar terjadi.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["review_date", "id"]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        errors = {}
        if not self.owner_id:
            errors["owner"] = "Risiko harus memiliki penanggung jawab."
        if not (self.mitigation or "").strip():
            errors["mitigation"] = "Tuliskan rencana mitigasi."
        if not self.review_date:
            errors["review_date"] = "Tentukan tanggal tinjau risiko."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.probability is None or self.impact is None:
            fallback = SEVERITY_TO_SCALE.get(self.severity, (3, 3))
            self.probability = self.probability or fallback[0]
            self.impact = self.impact or fallback[1]
        self.score = self.probability * self.impact
        self.severity = risk_level(self.score)
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {
                "probability",
                "impact",
                "score",
                "severity",
            }
        super().save(*args, **kwargs)

    @property
    def is_open(self):
        return self.status == "open"


class WorkPackage(models.Model):
    """Pengelompokan pekerjaan opsional di dalam phase (PRD §8.2, §26.9)."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="work_packages")
    phase = models.ForeignKey(
        "Phase", null=True, blank=True, on_delete=models.SET_NULL, related_name="work_packages"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    sequence = models.PositiveIntegerField(default=1)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sequence", "id"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "Tanggal selesai harus setelah tanggal mulai."})
        if self.phase_id and self.project_id and self.phase.project_id != self.project_id:
            raise ValidationError({"phase": "Pilih phase dari project yang sama."})


class ProjectTemplate(models.Model):
    """Template project (PRD §5.3, §26.7). Project menyalin isinya saat dibuat.

    Mengubah template tidak mengubah project yang sudah dibuat darinya.
    """

    workspace = models.ForeignKey(
        "identity.Workspace", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    project_type = models.CharField(max_length=30, default="general")
    structure_config = models.JSONField(default=dict, blank=True)
    workflow_config = models.JSONField(default=dict, blank=True)
    progress_config = models.JSONField(default=dict, blank=True)
    approval_config = models.JSONField(default=list, blank=True)
    custom_fields = models.JSONField(default=list, blank=True)
    weight_mode = models.CharField(max_length=10, default="auto")
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class PlanningImport(models.Model):
    """Remember imported planning files so retrying doesn't duplicate work."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="planning_imports")
    fingerprint = models.CharField(max_length=64)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    summary = models.JSONField(default=dict)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "fingerprint"], name="unique_project_plan_import"
            )
        ]


class BoardColumn(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="board_columns")
    title = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "pk"]

    def __str__(self):
        return self.title


class FeedbackCard(models.Model):
    """Discussion content, deliberately separate from weighted project tasks."""

    column = models.ForeignKey(BoardColumn, on_delete=models.CASCADE, related_name="feedback_cards")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=[("open", "Perlu dibahas"), ("agreed", "Disepakati"), ("done", "Selesai")],
        default="open",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    due_date = models.DateField(null=True, blank=True)
    linked_task = models.ForeignKey(
        "work.Task", null=True, blank=True, on_delete=models.SET_NULL, related_name="feedback_cards"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "pk"]

    def clean(self):
        super().clean()
        if (
            self.linked_task_id
            and self.column_id
            and self.linked_task.project_id != self.column.project_id
        ):
            raise ValidationError({"linked_task": "Pilih task dari project yang sama."})


class PresentationConfig(models.Model):
    project = models.OneToOneField(
        Project, on_delete=models.CASCADE, related_name="presentation_config"
    )
    sections = models.JSONField(default=list, blank=True)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
