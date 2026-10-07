"""Kalkulasi progress & health project (PRD §10–§12, §32–§34)."""

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from .models import ActivityAction, ActivityEvent, ProgressSnapshot

_DP = Decimal("0.01")


def planned_progress_on(project, on_date: date | None = None) -> Decimal | None:
    """Planned progress (%) dari baseline curve pada tanggal tertentu (PRD §11).

    Linear interpolation antar baseline points.
    None bila baseline belum diisi.
    """
    points = list(project.baseline_points.all())
    if not points:
        return None
    on_date = on_date or timezone.localdate()
    if on_date <= points[0].date:
        return points[0].planned_percent
    if on_date >= points[-1].date:
        return points[-1].planned_percent
    for prev, nxt in zip(points, points[1:], strict=False):
        if prev.date <= on_date <= nxt.date:
            span = (nxt.date - prev.date).days
            if span == 0:
                return nxt.planned_percent
            fraction = Decimal((on_date - prev.date).days) / Decimal(span)
            value = prev.planned_percent + (nxt.planned_percent - prev.planned_percent) * fraction
            return value.quantize(_DP)
    return points[-1].planned_percent


def _eligible_tasks(project):
    """Task yang dihitung ke actual progress (tanpa subtask), pakai prefetch cache bila ada."""
    cached = getattr(project, "_prefetched_objects_cache", {})
    if "tasks" in cached:
        return [t for t in cached["tasks"] if t.parent_task_id is None]
    return list(project.tasks.filter(parent_task__isnull=True))


def actual_progress(project) -> Decimal:
    """Actual progress (%) — weighted task (PRD §32), atau override PM (PRD §10.4)."""
    if project.progress_override is not None:
        return project.progress_override
    total_weight = Decimal("0")
    weighted = Decimal("0")
    for task in _eligible_tasks(project):
        total_weight += task.weight
        weighted += task.progress * task.weight
    if total_weight <= 0:
        return Decimal("0.00")
    return (weighted / total_weight).quantize(_DP)


def variance(project) -> Decimal | None:
    """Variance = Actual − Planned (PRD §10.2). None bila baseline belum ada."""
    planned = planned_progress_on(project)
    if planned is None:
        return None
    return (actual_progress(project) - planned).quantize(_DP)


class VarianceLevel:
    AHEAD = "ahead"
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    DELAYED = "delayed"
    UNKNOWN = "unknown"

    LABELS = {
        AHEAD: "Ahead",
        ON_TRACK: "On Track",
        AT_RISK: "At Risk",
        DELAYED: "Delayed",
        UNKNOWN: "No Baseline",
    }


def variance_level(project) -> str:
    """Level dari variance memakai threshold configurable (PRD §10.3).

    v >  0                     → ahead
    v >  AT_RISK_THRESHOLD     → on_track   (default: >= -1%)
    v >= DELAYED_THRESHOLD     → at_risk    (default: >= -5%)
    else                       → delayed
    """
    v = variance(project)
    if v is None:
        return VarianceLevel.UNKNOWN
    if v > 0:
        return VarianceLevel.AHEAD
    if v > Decimal(settings.PROGRESS_AT_RISK_THRESHOLD):
        return VarianceLevel.ON_TRACK
    if v >= Decimal(settings.PROGRESS_DELAYED_THRESHOLD):
        return VarianceLevel.AT_RISK
    return VarianceLevel.DELAYED


def project_health(project) -> dict:
    """Project health summary untuk Overview (PRD §9.1)."""
    from apps.work.models import Issue, IssueStatus

    level = variance_level(project)
    if project.is_overdue:
        schedule = "delayed"
    elif level in (VarianceLevel.AHEAD, VarianceLevel.ON_TRACK, VarianceLevel.UNKNOWN):
        schedule = "on_track"
    elif level == VarianceLevel.AT_RISK:
        schedule = "at_risk"
    else:
        schedule = "delayed"

    open_issues = Issue.objects.filter(
        project=project,
        status__in=[IssueStatus.OPEN, IssueStatus.IN_PROGRESS, IssueStatus.BLOCKED],
    )
    severity_rank = ["critical", "high", "medium", "low"]
    top_severity = None
    for severity in severity_rank:
        if open_issues.filter(severity=severity).exists():
            top_severity = severity
            break
    risky_count = open_issues.filter(severity__in=["critical", "high"]).count()

    return {
        "schedule": schedule,
        "progress": actual_progress(project),
        "planned": planned_progress_on(project),
        "variance": variance(project),
        "variance_level": level,
        "open_issues": open_issues.count(),
        "critical_issues": open_issues.filter(severity="critical").count(),
        "risk_count": risky_count,
        "risk_top_severity": top_severity,
    }


def record_snapshot(project, on_date: date | None = None) -> ProgressSnapshot:
    """Simpan/overwrite snapshot progress pada tanggal tertentu (PRD §34)."""
    on_date = on_date or timezone.localdate()
    planned = planned_progress_on(project, on_date)
    actual = actual_progress(project)
    var = None if planned is None else (actual - planned).quantize(_DP)
    snapshot, _ = ProgressSnapshot.objects.update_or_create(
        project=project,
        date=on_date,
        defaults={
            "planned_progress": planned,
            "actual_progress": actual,
            "variance": var,
        },
    )
    return snapshot


def record_activity(project, actor, action: str, message: str, object_repr: str = ""):
    """Catat activity log project (PRD §25)."""
    if action not in ActivityAction.values:
        raise ValueError(f"Unknown activity action: {action}")
    return ActivityEvent.objects.create(
        project=project,
        actor=actor,
        action=action,
        message=message[:300],
        object_repr=object_repr[:200],
    )
