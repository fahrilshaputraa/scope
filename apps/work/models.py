from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.projects.managers import ArchivableModel

from .progress import weighted_progress


class TaskStatus(models.TextChoices):
    BACKLOG = "backlog", "Backlog"
    TODO = "todo", "To Do"
    IN_PROGRESS = "in_progress", "In Progress"
    BLOCKED = "blocked", "Blocked"
    REVIEW = "review", "Review"
    DONE = "done", "Done"


#: Urutan kolom Kanban (PRD §18)
KANBAN_COLUMNS = [
    TaskStatus.BACKLOG,
    TaskStatus.TODO,
    TaskStatus.IN_PROGRESS,
    TaskStatus.BLOCKED,
    TaskStatus.REVIEW,
    TaskStatus.DONE,
]

TASK_STATUS_LABELS = {
    TaskStatus.BACKLOG: "Belum dijadwalkan",
    TaskStatus.TODO: "Siap dikerjakan",
    TaskStatus.IN_PROGRESS: "Sedang dikerjakan",
    TaskStatus.BLOCKED: "Terhambat",
    TaskStatus.REVIEW: "Menunggu pemeriksaan",
    TaskStatus.DONE: "Selesai",
}


class Priority(models.TextChoices):
    CRITICAL = "critical", "Critical"
    HIGH = "high", "High"
    MEDIUM = "medium", "Medium"
    LOW = "low", "Low"


class IssueStatus(models.TextChoices):
    OPEN = "open", "Open"
    IN_PROGRESS = "in_progress", "In Progress"
    BLOCKED = "blocked", "Blocked"
    RESOLVED = "resolved", "Resolved"
    CLOSED = "closed", "Closed"


#: Status yang dianggap masih terbuka
OPEN_ISSUE_STATUSES = [IssueStatus.OPEN, IssueStatus.IN_PROGRESS, IssueStatus.BLOCKED]


class Task(ArchivableModel):
    """Task project (PRD §17). Weight dipakai untuk weighted actual progress (§32)."""

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="tasks")
    board_column = models.ForeignKey(
        "projects.BoardColumn",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks",
    )
    phase = models.ForeignKey(
        "projects.Phase", null=True, blank=True, on_delete=models.SET_NULL, related_name="tasks"
    )
    milestone = models.ForeignKey(
        "projects.Milestone",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks",
    )
    parent_task = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="subtasks"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_tasks",
    )
    collaborators = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="collaborating_tasks"
    )
    status = models.CharField(max_length=20, choices=TaskStatus.choices, default=TaskStatus.TODO)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    baseline_start_date = models.DateField(null=True, blank=True)
    baseline_end_date = models.DateField(null=True, blank=True)
    dependencies = models.ManyToManyField(
        "self", symmetrical=False, blank=True, related_name="successors"
    )
    progress = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    weight = models.DecimalField(
        max_digits=6, decimal_places=2, default=1, validators=[MinValueValidator(0)]
    )
    labels = models.CharField(max_length=200, blank=True, help_text="Comma-separated labels")
    order = models.PositiveIntegerField(default=0, help_text="Manual ordering untuk Next Up")
    # Blocked (PRD §22)
    blocked_reason = models.TextField(blank=True)
    blocked_dependency = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["order", "due_date", "id"]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if self.board_column_id and self.board_column.project_id != self.project_id:
            raise ValidationError({"board_column": "Kolom harus berasal dari project yang sama."})
        errors = {}
        if self.start_date and self.due_date and self.due_date < self.start_date:
            errors["due_date"] = "Tanggal selesai harus setelah tanggal mulai."
        if (
            self.baseline_start_date
            and self.baseline_end_date
            and self.baseline_end_date < self.baseline_start_date
        ):
            errors["baseline_end_date"] = "Baseline selesai harus setelah baseline mulai."
        if self.status == TaskStatus.BLOCKED and not self.blocked_reason.strip():
            errors["blocked_reason"] = "Jelaskan hambatan sebelum memblokir task."
        self._validate_hierarchy()
        self._validate_completion()
        for name in ("phase", "milestone"):
            obj = getattr(self, name) if getattr(self, name + "_id") else None
            if obj and obj.project_id != self.project_id:
                errors[name] = "Pilih data dari project yang sama."
        if errors:
            raise ValidationError(errors)

    def _validate_hierarchy(self):
        if not self.parent_task_id:
            return
        parent = self.parent_task
        if parent.project_id != self.project_id:
            raise ValidationError({"parent_task": "Pilih activity dari project yang sama."})
        if parent.pk == self.pk or parent.parent_task_id:
            raise ValidationError(
                {"parent_task": "Detail activity hanya boleh memiliki satu induk."}
            )
        if self.pk and self.subtasks.exists():
            raise ValidationError(
                {"parent_task": "Activity yang memiliki detail tidak bisa menjadi detail."}
            )
        self.phase_id = parent.phase_id

    def _validate_completion(self):
        if self.pk and not self.parent_task_id and self.status == TaskStatus.DONE:
            if any(not child.is_done for child in self.subtasks.all()):
                raise ValidationError(
                    {"status": "Selesaikan seluruh detail activity terlebih dahulu."}
                )

    @property
    def has_details(self):
        return bool(self.pk and not self.parent_task_id and self.subtasks.all())

    def save(self, *args, **kwargs):
        self._validate_hierarchy()
        self._validate_completion()
        if self.status == TaskStatus.DONE:
            self.progress = 100
            self.completed_at = self.completed_at or timezone.now()
        else:
            self.completed_at = None
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {
                "progress",
                "completed_at",
                "phase",
            }
        super().save(*args, **kwargs)
        # Keep inherited grouping consistent when an activity moves to another phase.
        if not self.parent_task_id:
            self.subtasks.exclude(phase_id=self.phase_id).update(phase_id=self.phase_id)
        if self.parent_task_id and not self.is_done:
            Task.objects.filter(pk=self.parent_task_id, status=TaskStatus.DONE).update(
                status=TaskStatus.IN_PROGRESS, completed_at=None, updated_at=timezone.now()
            )

    @property
    def assignee_names(self):
        people = ([self.assignee] if self.assignee_id else []) + list(self.collaborators.all())
        return (
            " · ".join(user.get_full_name() or user.username for user in people)
            or "Belum ditugaskan"
        )

    @property
    def schedule_deviation(self):
        if self.due_date and self.baseline_end_date:
            return (self.due_date - self.baseline_end_date).days
        return None

    @property
    def is_blocked(self):
        return self.status == TaskStatus.BLOCKED

    @property
    def is_done(self):
        return self.status == TaskStatus.DONE

    @property
    def is_overdue(self):
        from django.utils import timezone

        if not self.due_date or self.is_done:
            return False
        return self.due_date < timezone.localdate()

    @property
    def label_list(self):
        return [lab.strip() for lab in self.labels.split(",") if lab.strip()]

    @property
    def display_progress(self):
        """Detail progress rolls up locally; only root weights count toward the project."""
        children = list(self.subtasks.all()) if self.pk and not self.parent_task_id else []
        if children:
            return weighted_progress(children)
        if self.is_done:
            return 100
        return self.progress

    def archive(self, user=None, at=None):
        if self.archived_at:
            return False
        at = at or timezone.now()
        super().archive(user=user, at=at)
        Task.all_objects.filter(parent_task=self, archived_at__isnull=True).update(
            archived_at=at, archived_by=self.archived_by
        )
        return True

    def restore(self):
        if not self.archived_at:
            return False
        at = self.archived_at
        super().restore()
        Task.all_objects.filter(parent_task=self, archived_at=at).update(
            archived_at=None, archived_by=None
        )
        from apps.projects.models import Phase

        if self.phase_id and Phase.all_objects.filter(
            pk=self.phase_id, archived_at__isnull=False
        ).exists():
            self.phase = None
            self.save(update_fields=["phase"])
        return True


class TaskComment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment on {self.task_id}"


class Mention(models.Model):
    """A user explicitly mentioned with ``@username`` in a task comment."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mentions",
    )
    task_comment = models.ForeignKey(
        TaskComment,
        on_delete=models.CASCADE,
        related_name="mentions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["task_comment", "user"],
                name="mention_unique_comment_user",
            )
        ]

    def __str__(self):
        return f"@{self.user_id} on comment {self.task_comment_id}"


class Issue(ArchivableModel):
    """Issue / hambatan project (PRD §21)."""

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="issues")
    task = models.ForeignKey(
        Task, null=True, blank=True, on_delete=models.SET_NULL, related_name="issues"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    severity = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=IssueStatus.choices, default=IssueStatus.OPEN)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_issues",
    )
    due_date = models.DateField(null=True, blank=True)
    resolution = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def is_open(self):
        return self.status in OPEN_ISSUE_STATUSES


class TaskAttachment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="attachments")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    file = models.FileField(upload_to="task-attachments/%Y/%m/")
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
