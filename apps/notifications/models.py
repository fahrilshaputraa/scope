from django.conf import settings
from django.db import models
from django.utils import timezone


class NotificationTarget(models.TextChoices):
    PROJECT = "project", "Project"
    TASK = "task", "Task"
    ISSUE = "issue", "Issue"
    MILESTONE = "milestone", "Milestone"


class Notification(models.Model):
    """In-app notification for one recipient."""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    verb = models.CharField(max_length=60)
    target_type = models.CharField(max_length=20, choices=NotificationTarget.choices)
    target_id = models.PositiveBigIntegerField(null=True, blank=True)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    url = models.CharField(max_length=500, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    dedupe_key = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["recipient", "read_at", "-created_at"],
                name="notif_recipient_read_idx",
            ),
            models.Index(
                fields=["recipient", "-created_at"],
                name="notif_recipient_created_idx",
            ),
        ]

    def __str__(self):
        return f"{self.recipient_id}: {self.title}"

    @property
    def is_read(self):
        return self.read_at is not None

    def mark_read(self):
        if self.read_at is None:
            self.read_at = timezone.now()
            self.save(update_fields=["read_at"])

    def mark_unread(self):
        if self.read_at is not None:
            self.read_at = None
            self.save(update_fields=["read_at"])


class DigestFrequency(models.TextChoices):
    OFF = "off", "Mati"
    DAILY = "daily", "Harian"
    WEEKLY = "weekly", "Mingguan"


class NotificationPreference(models.Model):
    """Per-user delivery preference. Email and digest are wired in B2."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preference",
    )
    in_app = models.BooleanField(default=True)
    email = models.BooleanField(default=False)
    digest = models.CharField(
        max_length=10,
        choices=DigestFrequency.choices,
        default=DigestFrequency.OFF,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Notification preference"
        verbose_name_plural = "Notification preferences"

    def __str__(self):
        return f"{self.user_id}: in_app={self.in_app} email={self.email} digest={self.digest}"
