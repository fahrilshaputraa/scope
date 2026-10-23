"""Map existing ActivityEvent rows to in-app notifications.

Fan-out lives here instead of in every view, so new activity call sites only
need to pass the affected ``target`` to ``record_activity``.
"""

from django.urls import reverse

from apps.projects.models import ActivityAction, Milestone, Project
from apps.work.models import TASK_STATUS_LABELS, Issue, Task

from .services import notify, today_token, user_display


def _actor_name(actor):
    return user_display(actor)


def _project_code(project):
    return project.code if project is not None else ""


def dispatch_activity(event, target=None, dedupe_token=""):
    """Create notifications for the activity event, if the action is covered."""
    if target is None:
        return []
    actor = event.actor
    actor_name = _actor_name(actor)
    today = today_token()

    if event.action == ActivityAction.PROJECT_UPDATED and isinstance(target, Project):
        return notify(
            actor,
            "project.updated",
            target,
            title=f"Project diperbarui: {target.name}",
            body=(
                f"{actor_name} memperbarui detail atau jadwal {_project_code(target)}."
            ),
            url=reverse("projects:project_detail", args=[target.pk]),
            dedupe_suffix=f"updated:{today}",
        )

    if event.action == ActivityAction.TASK_CREATED and isinstance(target, Task):
        project = target.project
        return notify(
            actor,
            "task.created",
            target,
            title=f"Tugas baru: {target.title}",
            body=f'{actor_name} menambahkan tugas di {_project_code(project)}.',
            url=reverse("work:task_detail", args=[target.pk]),
            dedupe_suffix=f"created:{target.pk}",
        )

    if event.action == ActivityAction.TASK_ASSIGNED and isinstance(target, Task):
        assignee = target.assignee
        assignee_name = user_display(assignee) if assignee else "belum ditugaskan"
        return notify(
            actor,
            "task.assigned",
            target,
            title=f"Penugasan tugas: {target.title}",
            body=f'{actor_name} memperbarui penugasan "{target.title}" ke {assignee_name}.',
            url=reverse("work:task_detail", args=[target.pk]),
            dedupe_suffix=f"assigned:{target.assignee_id}:{today}",
        )

    if event.action == ActivityAction.TASK_STATUS and isinstance(target, Task):
        label = TASK_STATUS_LABELS.get(target.status, target.get_status_display())
        return notify(
            actor,
            "task.status",
            target,
            title=f"Status tugas berubah: {target.title}",
            body=f'Status "{target.title}" sekarang {label}.',
            url=reverse("work:task_detail", args=[target.pk]),
            dedupe_suffix=f"status:{target.status}:{today}",
        )

    if event.action == ActivityAction.TIMELINE_CHANGED and isinstance(target, Task):
        start = target.start_date.isoformat() if target.start_date else "—"
        due = target.due_date.isoformat() if target.due_date else "—"
        return notify(
            actor,
            "task.dates",
            target,
            title=f"Jadwal tugas berubah: {target.title}",
            body=f"{start} → {due}.",
            url=reverse("work:task_detail", args=[target.pk]),
            dedupe_suffix=f"dates:{start}:{due}",
        )

    if event.action == ActivityAction.COMMENT_ADDED and isinstance(target, Task):
        return notify(
            actor,
            "comment.added",
            target,
            title=f"Komentar baru: {target.title}",
            body=event.message,
            url=reverse("work:task_detail", args=[target.pk]),
            dedupe_suffix=f"comment:{dedupe_token or event.pk}",
        )

    if event.action == ActivityAction.ISSUE_CREATED and isinstance(target, Issue):
        return notify(
            actor,
            "issue.created",
            target,
            title=f"Issue baru: {target.title}",
            body=(
                f'{actor_name} melaporkan issue di {_project_code(target.project)} '
                f"({target.get_severity_display()})."
            ),
            url=reverse("work:issue_update", args=[target.pk]),
            dedupe_suffix=f"created:{target.pk}",
        )

    if event.action == ActivityAction.ISSUE_ASSIGNED and isinstance(target, Issue):
        owner_name = user_display(target.owner) if target.owner_id else "belum ditugaskan"
        return notify(
            actor,
            "issue.assigned",
            target,
            title=f"Penugasan issue: {target.title}",
            body=f'{actor_name} memperbarui penanggung jawab "{target.title}" ke {owner_name}.',
            url=reverse("work:issue_update", args=[target.pk]),
            dedupe_suffix=f"assigned:{target.owner_id}:{today}",
        )

    if event.action == ActivityAction.ISSUE_UPDATED and isinstance(target, Issue):
        due = target.due_date.isoformat() if target.due_date else "—"
        return notify(
            actor,
            "issue.updated",
            target,
            title=f"Jadwal issue berubah: {target.title}",
            body=f"Jatuh tempo baru: {due}.",
            url=reverse("work:issue_update", args=[target.pk]),
            dedupe_suffix=f"due:{due}",
        )

    if event.action == ActivityAction.MILESTONE_COMPLETED and isinstance(target, Milestone):
        return notify(
            actor,
            "milestone.completed",
            target,
            title=f"Milestone selesai: {target.name}",
            body=f'{_project_code(target.project)} · {target.date.isoformat()}.',
            url=reverse("projects:project_milestones", args=[target.project_id]),
            dedupe_suffix=f"completed:{target.pk}",
        )

    return []
