"""Keep daily observed progress fresh after task writes, without inventing history."""

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.work.models import Task

from . import revisions  # noqa: F401  (registers revision capture signals)
from .models import Project
from .services import record_snapshot, sync_plan_curve


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
        sync_plan_curve(project)
        record_snapshot(project)


@receiver(post_save, sender=Project)
def snapshot_project_change(sender, instance, **kwargs):
    if kwargs.get("raw"):
        return
    record_snapshot(instance)


@receiver(pre_save, sender=Task)
def remember_weight_group(sender, instance, **kwargs):
    if instance.pk and not kwargs.get("raw"):
        instance._weight_group_before = (
            Task.all_objects.filter(pk=instance.pk)
            .values_list("parent_task_id", "archived_at")
            .first()
        )


@receiver(post_save, sender=Task)
def rebalance_weight_group(sender, instance, created=False, **kwargs):
    """Mode bobot otomatis: kelompok sibling dibagi rata setiap isinya berubah."""
    if kwargs.get("raw"):
        return
    project = Project.objects.filter(pk=instance.project_id).only("weight_mode").first()
    if project is None or project.weight_mode != "auto":
        return
    from apps.work.weights import rebalance_if_auto

    before = getattr(instance, "_weight_group_before", None)
    groups = set()
    if created:
        groups.add(instance.parent_task_id)
    elif before is not None:
        old_parent, old_archived = before
        if old_parent != instance.parent_task_id:
            groups.update({old_parent, instance.parent_task_id})
        if bool(old_archived) != bool(instance.archived_at):
            groups.add(instance.parent_task_id)
    for parent_id in groups:
        rebalance_if_auto(project, parent_id)
