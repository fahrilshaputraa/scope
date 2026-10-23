from django.conf import settings
from django.db import models
from django.utils import timezone


class ArchivedQuerySet(models.QuerySet):
    def active(self):
        return self.filter(archived_at__isnull=True)

    def archived(self):
        return self.filter(archived_at__isnull=False)


class ArchivedManager(models.Manager.from_queryset(ArchivedQuerySet)):
    """Default manager: archived rows are invisible unless explicitly requested."""

    def get_queryset(self):
        return super().get_queryset().filter(archived_at__isnull=True)


class ArchivableModel(models.Model):
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    objects = ArchivedManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    @property
    def is_archived(self):
        return self.archived_at is not None

    def archive(self, user=None, at=None):
        if self.archived_at:
            return False
        self.archived_at = at or timezone.now()
        self.archived_by = user if getattr(user, "is_authenticated", False) else None
        self.save(update_fields=["archived_at", "archived_by"])
        return True

    def restore(self):
        if not self.archived_at:
            return False
        self.archived_at = None
        self.archived_by = None
        self.save(update_fields=["archived_at", "archived_by"])
        return True
