from django.conf import settings
from django.db import models


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

TASK_STATUS_LABELS = dict(TaskStatus.choices)


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

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="tasks"
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
    status = models.CharField(
        max_length=20, choices=TaskStatus.choices, default=TaskStatus.TODO
    )
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    progress = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    weight = models.DecimalField(max_digits=6, decimal_places=2, default=1)
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

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="issues"
    )
    task = models.ForeignKey(
        Task, null=True, blank=True, on_delete=models.SET_NULL, related_name="issues"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    severity = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(
        max_length=20, choices=IssueStatus.choices, default=IssueStatus.OPEN
    )
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
