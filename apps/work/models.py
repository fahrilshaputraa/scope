from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


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


class Task(models.Model):
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
        for name in ("phase", "milestone", "parent_task"):
            obj = getattr(self, name) if getattr(self, name + "_id") else None
            if obj and obj.project_id != self.project_id:
                errors[name] = "Pilih data dari project yang sama."
        if self.pk and self.parent_task_id == self.pk:
            errors["parent_task"] = "Task tidak dapat menjadi induk dirinya sendiri."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.status == TaskStatus.DONE:
            self.progress = 100
            self.completed_at = self.completed_at or timezone.now()
        else:
            self.completed_at = None
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"progress", "completed_at"}
        super().save(*args, **kwargs)

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
        """Progress tampilan: task done dianggap 100%."""
        if self.is_done:
            return 100
        return self.progress


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


class Issue(models.Model):
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
