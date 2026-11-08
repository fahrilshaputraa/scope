"""Detect Teams events and queue them.

Two sources share one dedupe key space, so an event found by both never posts
twice:

* ``signals.py`` reacts to rows the existing notification fan-out already
  creates (blocked task, new critical issue) and to comment mentions.
* ``collect_scheduled_events`` runs from the scheduler tick / management
  command for time-based events (overdue, milestones, health, daily summary).
"""

from datetime import timedelta

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags

from apps.notifications.services import user_display
from apps.projects.models import (
    CLOSED_LIFECYCLE,
    HealthStatus,
    Milestone,
    MilestoneStatus,
    Project,
)
from apps.work.models import Issue, IssueStatus, Priority, Task, TaskStatus

from .cards import build_card
from .models import ProjectHealthMark, TeamsEvent, TeamsWebhook
from .teams import enqueue, enqueue_for, teams_enabled

#: Only events this recent are announced, so enabling a webhook does not flood
#: the channel with months-old backlog.
LOOKBACK_DAYS = 7
OPEN_ISSUE_STATUSES = (IssueStatus.OPEN, IssueStatus.IN_PROGRESS, IssueStatus.BLOCKED)
HEALTH_TONES = {
    HealthStatus.ON_TRACK: "good",
    HealthStatus.AT_RISK: "warning",
    HealthStatus.DELAYED: "attention",
    HealthStatus.CRITICAL: "attention",
}


def _date(value) -> str:
    return value.strftime("%d-%m-%Y") if value else "—"


def _project_context(project) -> str:
    return f"Scope · {project.code} · {project.name}"


# ------------------------------------------------------------------ cards ---


def task_overdue_card(task, today):
    days = (today - task.due_date).days
    return build_card(
        f"Task terlambat: {task.title}",
        text=f"Lewat {days} hari dari target selesai.",
        facts=[
            (
                "Dikerjakan oleh",
                user_display(task.assignee) if task.assignee_id else "Belum ditugaskan",
            ),
            ("Target selesai", _date(task.due_date)),
            ("Status", task.get_status_display()),
            ("Progress", f"{task.progress:.0f}%"),
        ],
        url=reverse("work:task_detail", args=[task.pk]),
        tone="attention",
        context=_project_context(task.project),
    )


def task_blocked_card(task, actor=None):
    return build_card(
        f"Task blocked: {task.title}",
        text=task.blocked_reason or "Alasan hambatan belum diisi.",
        facts=[
            (
                "Dikerjakan oleh",
                user_display(task.assignee) if task.assignee_id else "Belum ditugaskan",
            ),
            ("Menunggu", task.blocked_dependency),
            ("Diubah oleh", user_display(actor) if actor else ""),
            ("Target selesai", _date(task.due_date)),
        ],
        url=reverse("work:task_detail", args=[task.pk]),
        tone="attention",
        context=_project_context(task.project),
    )


def milestone_card(milestone, today, missed):
    if missed:
        title = f"Milestone terlewat: {milestone.name}"
        text = f"Terlewat {(today - milestone.date).days} hari dan belum selesai."
        tone = "attention"
    else:
        days = (milestone.date - today).days
        title = f"Milestone mendekati tanggal: {milestone.name}"
        text = "Jatuh hari ini." if days == 0 else f"Jatuh dalam {days} hari."
        tone = "warning"
    return build_card(
        title,
        text=text,
        facts=[
            ("Tanggal", _date(milestone.date)),
            ("Status", milestone.get_status_display()),
            ("Penanggung jawab", user_display(milestone.owner) if milestone.owner_id else ""),
        ],
        url=reverse("projects:project_milestones", args=[milestone.project_id]),
        tone=tone,
        context=_project_context(milestone.project),
    )


def issue_critical_card(issue):
    return build_card(
        f"Issue kritis: {issue.title}",
        text=(issue.description or "")[:500],
        facts=[
            ("Tingkat dampak", issue.get_severity_display()),
            ("Status", issue.get_status_display()),
            (
                "Penanggung jawab",
                user_display(issue.owner) if issue.owner_id else "Belum ditugaskan",
            ),
            ("Jatuh tempo", _date(issue.due_date)),
        ],
        url=reverse("work:issue_update", args=[issue.pk]),
        tone="attention",
        context=_project_context(issue.project),
    )


def health_card(project, old, new):
    labels = dict(HealthStatus.choices)
    return build_card(
        f"Health project berubah: {labels.get(new, new)}",
        text=f"{project.name} berubah dari {labels.get(old, old)} ke {labels.get(new, new)}.",
        facts=[
            ("Project Manager", user_display(project.manager) if project.manager_id else ""),
            ("Target selesai", _date(project.target_end_date)),
        ],
        url=reverse("projects:project_detail", args=[project.pk]),
        tone=HEALTH_TONES.get(new, "default"),
        context=_project_context(project),
    )


def mention_card(task_or_label, project, author, mentioned, url, snippet):
    return build_card(
        f"{user_display(author)} menyebut {user_display(mentioned)}",
        text=strip_tags(snippet or "")[:500],
        facts=[("Di", task_or_label)],
        url=url,
        tone="accent",
        context=_project_context(project),
    )


def _project_counts(project, today):
    tasks = Task.objects.filter(project=project, archived_at__isnull=True)
    return {
        "overdue": tasks.filter(due_date__lt=today).exclude(status=TaskStatus.DONE).count(),
        "blocked": tasks.filter(status=TaskStatus.BLOCKED).count(),
        "due_week": tasks.filter(due_date__gte=today, due_date__lte=today + timedelta(days=7))
        .exclude(status=TaskStatus.DONE)
        .count(),
        "critical": Issue.objects.filter(
            project=project, severity=Priority.CRITICAL, status__in=OPEN_ISSUE_STATUSES
        ).count(),
    }


def daily_summary_card(webhook, projects, today):
    labels = dict(HealthStatus.choices)
    if webhook.project_id:
        project = webhook.project
        counts = _project_counts(project, today)
        milestones = Milestone.objects.filter(
            project=project, date__gte=today, date__lte=today + timedelta(days=7)
        ).exclude(status=MilestoneStatus.COMPLETED)
        return build_card(
            f"Ringkasan harian {_date(today)}",
            facts=[
                ("Health", labels.get(project.health_status, "Belum dinilai")),
                ("Task terlambat", str(counts["overdue"])),
                ("Task blocked", str(counts["blocked"])),
                ("Jatuh tempo 7 hari", str(counts["due_week"])),
                ("Issue kritis terbuka", str(counts["critical"])),
            ],
            items=[f"Milestone {m.name} · {_date(m.date)}" for m in milestones[:5]],
            url=reverse("projects:project_detail", args=[project.pk]),
            context=_project_context(project),
        )
    lines = []
    for project in projects[:15]:
        counts = _project_counts(project, today)
        lines.append(
            f"{project.code} · {labels.get(project.health_status, 'Belum dinilai')} · "
            f"{counts['overdue']} terlambat · {counts['blocked']} blocked · "
            f"{counts['critical']} issue kritis"
        )
    return build_card(
        f"Ringkasan harian portfolio {_date(today)}",
        text=f"{len(projects)} project aktif." if projects else "Tidak ada project aktif.",
        items=lines,
        url=reverse("projects:dashboard"),
    )


# ------------------------------------------------------------- scheduler ---


def _active_projects():
    return Project.objects.exclude(lifecycle_status__in=CLOSED_LIFECYCLE)


def _subscribed_projects(event, hooks):
    """Projects with at least one webhook (project or global) for ``event``."""
    wanted = [hook for hook in hooks if hook.wants(event)]
    if not wanted:
        return Project.objects.none()
    if any(hook.is_global for hook in wanted):
        return _active_projects()
    return _active_projects().filter(pk__in={hook.project_id for hook in wanted})


def collect_scheduled_events(now=None) -> int:
    """Queue time-based events. Idempotent: the dedupe keys stop re-queuing."""
    if not teams_enabled():
        return 0
    hooks = list(TeamsWebhook.objects.filter(is_active=True).select_related("project"))
    if not hooks:
        return 0
    now = now or timezone.now()
    today = timezone.localdate(now)
    since = today - timedelta(days=LOOKBACK_DAYS)
    queued = 0

    projects = _subscribed_projects(TeamsEvent.TASK_OVERDUE, hooks)
    overdue = (
        Task.objects.filter(project__in=projects, due_date__lt=today, due_date__gte=since)
        .exclude(status=TaskStatus.DONE)
        .select_related("project", "assignee")
    )
    for task in overdue:
        queued += len(
            enqueue(
                TeamsEvent.TASK_OVERDUE,
                task.project,
                f"task_overdue:{task.pk}:{task.due_date.isoformat()}",
                lambda task=task: task_overdue_card(task, today),
            )
        )

    due_days = int(getattr(settings, "TEAMS_MILESTONE_DUE_DAYS", 3))
    projects = _subscribed_projects(TeamsEvent.MILESTONE_DUE, hooks)
    upcoming = (
        Milestone.objects.filter(
            project__in=projects, date__gte=today, date__lte=today + timedelta(days=due_days)
        )
        .exclude(status=MilestoneStatus.COMPLETED)
        .select_related("project", "owner")
    )
    for milestone in upcoming:
        queued += len(
            enqueue(
                TeamsEvent.MILESTONE_DUE,
                milestone.project,
                f"milestone_due:{milestone.pk}:{milestone.date.isoformat()}",
                lambda m=milestone: milestone_card(m, today, missed=False),
            )
        )

    projects = _subscribed_projects(TeamsEvent.MILESTONE_MISSED, hooks)
    missed = (
        Milestone.objects.filter(project__in=projects, date__lt=today, date__gte=since)
        .exclude(status=MilestoneStatus.COMPLETED)
        .select_related("project", "owner")
    )
    for milestone in missed:
        queued += len(
            enqueue(
                TeamsEvent.MILESTONE_MISSED,
                milestone.project,
                f"milestone_missed:{milestone.pk}:{milestone.date.isoformat()}",
                lambda m=milestone: milestone_card(m, today, missed=True),
            )
        )

    projects = _subscribed_projects(TeamsEvent.ISSUE_CRITICAL, hooks)
    critical = Issue.objects.filter(
        project__in=projects,
        severity=Priority.CRITICAL,
        status__in=OPEN_ISSUE_STATUSES,
        created_at__gte=now - timedelta(days=LOOKBACK_DAYS),
    ).select_related("project", "owner")
    for issue in critical:
        queued += len(queue_critical_issue(issue))

    queued += _collect_health(_subscribed_projects(TeamsEvent.HEALTH_CHANGED, hooks), now)
    queued += _collect_daily_summaries(hooks, now, today)
    return queued


def _collect_health(projects, now) -> int:
    queued = 0
    marks = {
        mark.project_id: mark for mark in ProjectHealthMark.objects.filter(project__in=projects)
    }
    for project in projects.select_related("manager"):
        current = project.health_status or ""
        mark = marks.get(project.pk)
        if mark is None:
            ProjectHealthMark.objects.create(project=project, health=current)
            continue  # first observation is the baseline, not a change
        if mark.health == current:
            continue
        previous = mark.health
        mark.health = current
        mark.save(update_fields=["health", "updated_at"])
        if not previous or not current:
            continue
        stamp = timezone.localtime(now).strftime("%Y%m%d%H")
        queued += len(
            enqueue(
                TeamsEvent.HEALTH_CHANGED,
                project,
                f"health_changed:{project.pk}:{previous}:{current}:{stamp}",
                lambda p=project, a=previous, b=current: health_card(p, a, b),
            )
        )
    return queued


def _collect_daily_summaries(hooks, now, today) -> int:
    hour = int(getattr(settings, "TEAMS_DAILY_SUMMARY_HOUR", 8))
    if timezone.localtime(now).hour < hour:
        return 0
    queued = 0
    portfolio = None
    for hook in hooks:
        if not hook.wants(TeamsEvent.DAILY_SUMMARY):
            continue
        if hook.is_global and portfolio is None:
            portfolio = list(_active_projects().select_related("manager").order_by("code"))
        row = enqueue_for(
            hook,
            TeamsEvent.DAILY_SUMMARY,
            f"daily_summary:{today.isoformat()}",
            daily_summary_card(hook, portfolio or [], today),
        )
        queued += 1 if row is not None else 0
    return queued


# ---------------------------------------------------------- event-driven ---


def queue_critical_issue(issue) -> list:
    return enqueue(
        TeamsEvent.ISSUE_CRITICAL,
        issue.project,
        f"issue_critical:{issue.pk}",
        lambda: issue_critical_card(issue),
    )


def queue_blocked_task(task, dedupe_suffix: str, actor=None) -> list:
    return enqueue(
        TeamsEvent.TASK_BLOCKED,
        task.project,
        f"task_blocked:{task.pk}:{dedupe_suffix}",
        lambda: task_blocked_card(task, actor),
    )


def queue_task_mention(mention) -> list:
    comment = mention.task_comment
    task = comment.task
    return enqueue(
        TeamsEvent.MENTION,
        task.project,
        f"mention:task_comment:{comment.pk}:{mention.user_id}",
        lambda: mention_card(
            f"Task {task.title}",
            task.project,
            comment.author,
            mention.user,
            reverse("work:task_detail", args=[task.pk]),
            comment.content,
        ),
    )


def queue_comment_mention(mention) -> list:
    comment = mention.comment
    project = comment.project
    return enqueue(
        TeamsEvent.MENTION,
        project,
        f"mention:comment:{comment.pk}:{mention.user_id}",
        lambda: mention_card(
            f"Komentar {comment.get_target_type_display()}",
            project,
            comment.author,
            mention.user,
            reverse("projects:project_detail", args=[project.pk]),
            comment.content,
        ),
    )


__all__ = [
    "collect_scheduled_events",
    "queue_blocked_task",
    "queue_comment_mention",
    "queue_critical_issue",
    "queue_task_mention",
]
