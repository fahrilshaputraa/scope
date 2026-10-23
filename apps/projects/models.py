from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from .managers import ArchivableModel


class ProjectStatus(models.TextChoices):
    PLANNING = "planning", "Planning"
    ON_TRACK = "on_track", "On Track"
    AT_RISK = "at_risk", "At Risk"
    DELAYED = "delayed", "Delayed"
    COMPLETED = "completed", "Completed"
    ON_HOLD = "on_hold", "On Hold"
    CANCELLED = "cancelled", "Cancelled"


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
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="member_projects"
    )
    team = models.CharField(max_length=100, blank=True)
    start_date = models.DateField()
    target_end_date = models.DateField()
    actual_end_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=ProjectStatus.choices, default=ProjectStatus.PLANNING
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

        if self.status in (ProjectStatus.COMPLETED, ProjectStatus.CANCELLED):
            return False
        return self.target_end_date < timezone.localdate()

    @property
    def next_milestone(self):
        return self.milestones.exclude(status=MilestoneStatus.COMPLETED).order_by("date").first()

    @property
    def effective_current_phase(self):
        """Phase aktif: explicit current_phase, atau derive dari phase yang belum selesai."""
        if self.current_phase_id:
            return self.current_phase
        return (
            self.phases.exclude(status=PhaseStatus.COMPLETED).order_by("sequence").first()
            or self.phases.order_by("-sequence").first()
        )

    def health(self):
        """Ringkasan project health untuk Overview (PRD §9.1)."""
        from .services import project_health

        return project_health(self)


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

        for task in Task.all_objects.filter(
            phase=self, parent_task__isnull=True, archived_at=at
        ):
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


class ProgressSnapshot(models.Model):
    """Snapshot progress harian untuk historical chart (PRD §34)."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="snapshots")
    date = models.DateField()
    planned_progress = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    actual_progress = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    variance = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


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
    message = models.CharField(max_length=300)
    object_repr = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"[{self.action}] {self.message}"


class RevisionEntity(models.TextChoices):
    PROJECT = "project", "Project"
    TASK = "task", "Task"
    MILESTONE = "milestone", "Milestone"
    ISSUE = "issue", "Issue"
    RISK = "risk", "Risk"


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


class Risk(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="risks")
    title = models.CharField(max_length=200)
    severity = models.CharField(
        max_length=20,
        choices=[("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")],
        default="medium",
    )
    status = models.CharField(
        max_length=20,
        choices=[("open", "Open"), ("mitigated", "Mitigated"), ("closed", "Closed")],
        default="open",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    mitigation = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_date", "id"]

    def __str__(self):
        return self.title


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
