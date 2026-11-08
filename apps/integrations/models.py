import secrets

from django.conf import settings
from django.db import models

from .crypto import decrypt, encrypt
from .validators import mask_url


class TeamsEvent(models.TextChoices):
    TASK_OVERDUE = "task_overdue", "Task terlambat"
    TASK_BLOCKED = "task_blocked", "Task blocked"
    MILESTONE_DUE = "milestone_due", "Milestone mendekati tanggal"
    MILESTONE_MISSED = "milestone_missed", "Milestone terlewat"
    ISSUE_CRITICAL = "issue_critical", "Issue kritis"
    HEALTH_CHANGED = "health_changed", "Perubahan health project"
    MENTION = "mention", "Mention di komentar"
    DAILY_SUMMARY = "daily_summary", "Ringkasan harian"
    TEST = "test", "Pesan tes"


#: Events a webhook can subscribe to (``TEST`` is always allowed).
SELECTABLE_EVENTS = [choice for choice in TeamsEvent.choices if choice[0] != TeamsEvent.TEST]
DEFAULT_EVENTS = [
    TeamsEvent.TASK_OVERDUE,
    TeamsEvent.TASK_BLOCKED,
    TeamsEvent.MILESTONE_MISSED,
    TeamsEvent.ISSUE_CRITICAL,
    TeamsEvent.HEALTH_CHANGED,
]


class TeamsWebhook(models.Model):
    """One Teams channel endpoint (Incoming Webhook or Workflows webhook).

    ``project`` empty means a workspace-wide (global) webhook that receives the
    events of every active project. The URL itself is a bearer secret, so it is
    stored encrypted and only a short hint is ever rendered.
    """

    project = models.ForeignKey(
        "projects.Project",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="teams_webhooks",
    )
    name = models.CharField(max_length=120)
    url_encrypted = models.TextField()
    url_hint = models.CharField(max_length=200, blank=True)
    events = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_delivery_at = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(max_length=20, blank=True)
    last_error = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["project__name", "name", "pk"]
        verbose_name = "Teams webhook"
        verbose_name_plural = "Teams webhooks"

    def __str__(self):
        scope = self.project.code if self.project_id else "global"
        return f"{self.name} ({scope})"

    @property
    def url(self) -> str:
        return decrypt(self.url_encrypted)

    def set_url(self, value: str) -> None:
        self.url_encrypted = encrypt(value)
        self.url_hint = mask_url(value)

    @property
    def is_global(self) -> bool:
        return self.project_id is None

    def wants(self, event: str) -> bool:
        return event == TeamsEvent.TEST or event in (self.events or [])

    def event_labels(self) -> list[str]:
        labels = dict(TeamsEvent.choices)
        return [labels[event] for event in (self.events or []) if event in labels]


class DeliveryStatus(models.TextChoices):
    PENDING = "pending", "Menunggu"
    SENDING = "sending", "Mengirim"
    SENT = "sent", "Terkirim"
    FAILED = "failed", "Gagal"
    SKIPPED = "skipped", "Dilewati"


class DeliveryLog(models.Model):
    """Queue row and delivery log for one Teams message.

    ``(webhook, dedupe_key)`` is unique, so re-detecting the same event never
    queues a second message. ``sent_at`` is the queue marker, like
    ``Notification.emailed_at``: once set, the row is never sent again.
    """

    webhook = models.ForeignKey(TeamsWebhook, on_delete=models.CASCADE, related_name="deliveries")
    event = models.CharField(max_length=30, choices=TeamsEvent.choices)
    dedupe_key = models.CharField(max_length=255)
    title = models.CharField(max_length=200)
    payload = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20, choices=DeliveryStatus.choices, default=DeliveryStatus.PENDING
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    response_code = models.PositiveSmallIntegerField(null=True, blank=True)
    error = models.CharField(max_length=500, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["webhook", "dedupe_key"], name="teams_delivery_unique_key"
            )
        ]
        indexes = [
            models.Index(fields=["status", "next_attempt_at"], name="teams_delivery_queue_idx"),
        ]

    def __str__(self):
        return f"{self.webhook_id}: {self.event} [{self.status}]"


class ProjectHealthMark(models.Model):
    """Last health seen by the Teams scanner, to detect health changes."""

    project = models.OneToOneField(
        "projects.Project", on_delete=models.CASCADE, related_name="teams_health_mark"
    )
    health = models.CharField(max_length=20, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.project_id}: {self.health or '-'}"


def new_feed_token() -> str:
    return secrets.token_urlsafe(32)


class CalendarFeedToken(models.Model):
    """Secret token for a user's iCalendar subscription URL (resettable)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="calendar_feed"
    )
    token = models.CharField(max_length=64, unique=True, default=new_feed_token)
    created_at = models.DateTimeField(auto_now_add=True)
    last_accessed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"calendar feed {self.user_id}"

    def reset(self):
        self.token = new_feed_token()
        self.last_accessed_at = None
        self.save(update_fields=["token", "last_accessed_at"])


class OutlookConnection(models.Model):
    """Delegated Microsoft Graph token (Calendars.ReadWrite) for one user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="outlook_connection"
    )
    access_token_encrypted = models.TextField(blank=True)
    refresh_token_encrypted = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    scope = models.CharField(max_length=500, blank=True)
    account_email = models.CharField(max_length=254, blank=True)
    connected_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"outlook {self.user_id}"

    @property
    def access_token(self) -> str:
        return decrypt(self.access_token_encrypted)

    @property
    def refresh_token(self) -> str:
        return decrypt(self.refresh_token_encrypted)

    def set_tokens(self, access_token: str, refresh_token: str = "") -> None:
        self.access_token_encrypted = encrypt(access_token)
        if refresh_token:
            self.refresh_token_encrypted = encrypt(refresh_token)

    @property
    def has_calendar_scope(self) -> bool:
        return "calendars.readwrite" in self.scope.lower()


class OutlookEvent(models.Model):
    """Outlook event created by Scope, so a second click updates instead of duplicating."""

    class Target(models.TextChoices):
        TASK = "task", "Task"
        MILESTONE = "milestone", "Milestone"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="outlook_events"
    )
    target_type = models.CharField(max_length=20, choices=Target.choices)
    target_id = models.PositiveBigIntegerField()
    graph_event_id = models.CharField(max_length=500)
    web_link = models.URLField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "target_type", "target_id"], name="outlook_event_unique_target"
            )
        ]

    def __str__(self):
        return f"{self.user_id}: {self.target_type}:{self.target_id}"
