"""Keep daily observed progress fresh after task writes, without inventing history."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.work.models import Task

from .models import Project
from .services import record_snapshot


@receiver(post_save, sender=Task)
@receiver(post_delete, sender=Task)
def snapshot_task_change(sender, instance, **kwargs):
    origin = kwargs.get("origin")
    if isinstance(origin, Project) or getattr(origin, "model", None) is Project:
        return
    if kwargs.get("raw"):
        return
    project = Project.objects.filter(pk=instance.project_id).first()
    if project:
        record_snapshot(project)


@receiver(post_save, sender=Project)
def snapshot_project_change(sender, instance, **kwargs):
    if kwargs.get("raw"):
        return
    record_snapshot(instance)
