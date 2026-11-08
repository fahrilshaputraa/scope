"""iCalendar (RFC 5545) feeds: per-user subscription and per-project download.

Every item is an all-day event on its due date. Access always goes through
``visible_projects`` so a feed never exposes a project the user cannot open.
"""

from datetime import UTC, timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags

from apps.identity.permissions import can_view_internal, visible_projects
from apps.notifications.delivery import absolute_url
from apps.projects.models import Milestone, MilestoneStatus
from apps.work.models import Issue, IssueStatus, Task, TaskStatus

PRODID = "-//Scope//Project Control Center//ID"
#: Keep the feed small: recent past plus the whole future.
PAST_DAYS = 60
OPEN_ISSUES = (IssueStatus.OPEN, IssueStatus.IN_PROGRESS, IssueStatus.BLOCKED)


def escape_text(value) -> str:
    text = strip_tags(str(value or ""))
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def fold(line: str) -> str:
    """Fold to 75 octets per RFC 5545 §3.1 without splitting UTF-8 sequences."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts = []
    current = b""
    limit = 75
    for char in line:
        encoded = char.encode("utf-8")
        if len(current) + len(encoded) > limit:
            parts.append(current.decode("utf-8"))
            current = b""
            limit = 74  # continuation lines start with one space
        current += encoded
    parts.append(current.decode("utf-8"))
    return "\r\n ".join(parts)


def _uid_host() -> str:
    return urlsplit(getattr(settings, "SITE_URL", "")).hostname or "scope.local"


def _event(uid, day, summary, description, url, categories, stamp, status=""):
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}@{_uid_host()}",
        f"DTSTAMP:{stamp}",
        f"DTSTART;VALUE=DATE:{day.strftime('%Y%m%d')}",
        f"DTEND;VALUE=DATE:{(day + timedelta(days=1)).strftime('%Y%m%d')}",
        f"SUMMARY:{escape_text(summary)}",
        f"DESCRIPTION:{escape_text(description)}",
        f"URL:{absolute_url(url)}",
        f"CATEGORIES:{escape_text(categories)}",
        "TRANSP:TRANSPARENT",
    ]
    if status:
        lines.append(f"STATUS:{status}")
    lines.append("END:VEVENT")
    return lines


def task_event(task, stamp):
    done = task.status == TaskStatus.DONE
    prefix = "[Selesai] " if done else ""
    return _event(
        f"scope-task-{task.pk}",
        task.due_date,
        f"{prefix}{task.title} ({task.project.code})",
        f"Task di {task.project.name}. Status: {task.get_status_display()}.",
        reverse("work:task_detail", args=[task.pk]),
        "Task",
        stamp,
        "CONFIRMED",
    )


def milestone_event(milestone, stamp):
    done = milestone.status == MilestoneStatus.COMPLETED
    prefix = "[Selesai] " if done else ""
    return _event(
        f"scope-milestone-{milestone.pk}",
        milestone.date,
        f"{prefix}Milestone: {milestone.name} ({milestone.project.code})",
        f"Milestone {milestone.project.name}. Status: {milestone.get_status_display()}.",
        reverse("projects:project_milestones", args=[milestone.project_id]),
        "Milestone",
        stamp,
    )


def issue_event(issue, stamp):
    return _event(
        f"scope-issue-{issue.pk}",
        issue.due_date,
        f"Issue: {issue.title} ({issue.project.code})",
        f"Issue {issue.get_severity_display()} di {issue.project.name}. "
        f"Status: {issue.get_status_display()}.",
        reverse("work:issue_update", args=[issue.pk]),
        "Issue",
        stamp,
    )


def render_calendar(name: str, events) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape_text(name)}",
        f"X-WR-TIMEZONE:{settings.TIME_ZONE}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT1H",
        "X-PUBLISHED-TTL:PT1H",
    ]
    for event_lines in events:
        lines.extend(event_lines)
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(line) for line in lines) + "\r\n"


def _stamp() -> str:
    return timezone.now().astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def user_feed(user) -> str:
    """Tasks assigned to the user, milestones of visible projects, and the user's issues."""
    stamp = _stamp()
    since = timezone.localdate() - timedelta(days=PAST_DAYS)
    projects = visible_projects(user)
    tasks = (
        Task.objects.filter(project__in=projects, due_date__gte=since)
        .filter(_assigned(user))
        .select_related("project")
        .distinct()
        .order_by("due_date", "pk")
    )
    milestones = (
        Milestone.objects.filter(project__in=projects, date__gte=since)
        .select_related("project")
        .order_by("date", "pk")
    )
    events = [task_event(task, stamp) for task in tasks]
    events += [milestone_event(milestone, stamp) for milestone in milestones]
    if can_view_internal(user):
        issues = (
            Issue.objects.filter(
                project__in=projects,
                owner=user,
                due_date__gte=since,
                status__in=OPEN_ISSUES,
            )
            .select_related("project")
            .order_by("due_date", "pk")
        )
        events += [issue_event(issue, stamp) for issue in issues]
    return render_calendar("Scope · Jadwal saya", events)


def project_feed(project, user) -> str:
    stamp = _stamp()
    tasks = (
        Task.objects.filter(project=project, due_date__isnull=False)
        .select_related("project")
        .order_by("due_date", "pk")
    )
    milestones = Milestone.objects.filter(project=project).select_related("project")
    events = [task_event(task, stamp) for task in tasks]
    events += [milestone_event(milestone, stamp) for milestone in milestones.order_by("date")]
    if can_view_internal(user):
        issues = Issue.objects.filter(
            project=project, due_date__isnull=False, status__in=OPEN_ISSUES
        ).select_related("project")
        events += [issue_event(issue, stamp) for issue in issues.order_by("due_date")]
    return render_calendar(f"Scope · {project.code} {project.name}", events)


def _assigned(user):
    from django.db.models import Q

    return Q(assignee=user) | Q(collaborators=user)
