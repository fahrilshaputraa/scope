"""Kalkulasi progress & health project (PRD §10–§12, §32–§34)."""

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from apps.work.progress import weighted_progress

from .models import ActivityAction, ActivityEvent, ProgressSnapshot, Project, ProjectStatus

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
    return list(project.tasks.filter(parent_task__isnull=True).prefetch_related("subtasks"))


def actual_progress(project) -> Decimal:
    """Actual progress (%) — weighted task (PRD §32), atau override PM (PRD §10.4)."""
    if project.progress_override is not None:
        return project.progress_override
    return weighted_progress(_eligible_tasks(project))


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
    risks = project.risks.filter(status="open")
    risky_count = risks.count()
    top_severity = next((s for s in severity_rank if risks.filter(severity=s).exists()), None)

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


def projects_due_for_snapshot(on_date: date | None = None):
    """Active projects that do not have a snapshot yet for ``on_date``.

    Archived projects are excluded by the default manager. Completed and
    cancelled projects are not considered active.
    """
    on_date = on_date or timezone.localdate()
    existing = ProgressSnapshot.objects.filter(date=on_date).values("project_id")
    return Project.objects.exclude(
        status__in=[ProjectStatus.COMPLETED, ProjectStatus.CANCELLED]
    ).exclude(pk__in=existing)


def snapshot_due_projects(on_date: date | None = None) -> int:
    """Capture ``on_date`` for every due project; safe to run repeatedly.

    ``record_snapshot`` upserts on ``(project, date)`` so concurrent workers
    cannot create duplicate rows for the same calendar day.
    """
    on_date = on_date or timezone.localdate()
    count = 0
    for project in projects_due_for_snapshot(on_date).iterator():
        record_snapshot(project, on_date)
        count += 1
    return count


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


def timeline_data(project):
    """Data shared by full timeline and overview; dates are inclusive."""
    from datetime import timedelta

    tasks = list(
        project.tasks.select_related("assignee", "phase", "parent_task")
        .prefetch_related("dependencies", "collaborators", "subtasks")
        .order_by("phase__sequence", "start_date", "id")
    )
    # Keep each activity directly followed by its details, regardless of their dates.
    children = {}
    for task in tasks:
        if task.parent_task_id:
            children.setdefault(task.parent_task_id, []).append(task)
    ordered = []
    for task in tasks:
        if task.parent_task_id is None:
            ordered.extend([task, *children.get(task.pk, [])])
    included = {task.pk for task in ordered}
    tasks = ordered + [task for task in tasks if task.pk not in included]
    milestones = list(project.milestones.all())
    dates = [project.start_date, project.target_end_date]
    for task in tasks:
        dates.extend(
            d
            for d in [
                task.start_date,
                task.due_date,
                task.baseline_start_date,
                task.baseline_end_date,
            ]
            if d
        )
    dates.extend(m.date for m in milestones)
    start, end = min(dates), max(dates)
    span = max((end - start).days + 1, 1)

    def geometry(first, last):
        return {
            "left": round((first - start).days / span * 100, 3),
            "width": round(((last - first).days + 1) / span * 100, 3),
        }

    today = timezone.localdate()
    rows = []
    previous_phase = object()
    for task in tasks:
        first = task.start_date or project.start_date
        last = task.due_date or first
        baseline = (
            geometry(task.baseline_start_date, task.baseline_end_date)
            if task.baseline_start_date and task.baseline_end_date
            else None
        )
        plan_start = task.baseline_start_date or task.start_date
        plan_end = task.baseline_end_date or task.due_date
        expected = None
        if plan_start and plan_end:
            duration = max((plan_end - plan_start).days + 1, 1)
            expected = round(min(100, max(0, ((today - plan_start).days + 1) / duration * 100)), 2)
        rows.append(
            {
                "task": task,
                **geometry(first, last),
                "baseline": baseline,
                "planned_percent": expected,
                "plan_source": "Rencana awal"
                if task.baseline_start_date and task.baseline_end_date
                else "Jadwal saat ini",
                "undated": not (task.start_date and task.due_date),
                "phase_heading": task.phase_id != previous_phase,
            }
        )
        previous_phase = task.phase_id
    mini_rows = []
    for phase in project.phases.all():
        phase_tasks = [t for t in tasks if t.phase_id == phase.pk]
        if not phase_tasks:
            continue
        first = min(t.start_date or project.start_date for t in phase_tasks)
        last = max(t.due_date or t.start_date or project.start_date for t in phase_tasks)
        roots = [t for t in phase_tasks if t.parent_task_id is None]
        progress = weighted_progress(roots)
        mini_rows.append({"name": phase.name, "progress": progress, **geometry(first, last)})
    if any(t.phase_id is None for t in tasks):
        ungrouped = [t for t in tasks if t.phase_id is None]
        mini_rows.append(
            {
                "name": "Tanpa phase",
                "progress": 0,
                **geometry(
                    min(t.start_date or project.start_date for t in ungrouped),
                    max(t.due_date or t.start_date or project.start_date for t in ungrouped),
                ),
            }
        )
    today = timezone.localdate()
    return {
        "mini_timeline_rows": mini_rows,
        "tasks": tasks,
        "timeline_rows": rows,
        "timeline_start": start,
        "timeline_end": end,
        "timeline_today": round((today - start).days / span * 100, 3)
        if start <= today <= end
        else None,
        "timeline_ticks": [
            {
                "date": start + timedelta(days=round(i * (span - 1) / 6)),
                "left": round(i / 6 * 100, 3),
            }
            for i in range(7)
        ],
        "timeline_milestones": [
            {"milestone": m, "left": round((m.date - start).days / span * 100, 3)}
            for m in milestones
        ],
    }


def capture_baseline(project, actor):
    """Freeze task dates and derive a weighted cumulative planned curve."""
    from django.db import transaction

    from .models import ProgressBaselinePoint

    with transaction.atomic():
        tasks = list(project.tasks.filter(parent_task__isnull=True))
        if not tasks or any(not t.start_date or not t.due_date for t in tasks):
            from django.core.exceptions import ValidationError

            raise ValidationError(
                "Isi tanggal mulai dan selesai seluruh task utama sebelum menyimpan baseline."
            )
        total = sum(t.weight for t in tasks)
        if total <= 0:
            from django.core.exceptions import ValidationError

            raise ValidationError("Total bobot task harus lebih besar dari nol.")
        # Preserve baseline for subtasks too, but only root tasks affect cumulative progress.
        all_tasks = list(project.tasks.all())
        for task in all_tasks:
            task.baseline_start_date, task.baseline_end_date = task.start_date, task.due_date
        project.tasks.model.objects.bulk_update(
            all_tasks, ["baseline_start_date", "baseline_end_date"]
        )
        first = min(t.start_date for t in tasks) - timezone.timedelta(days=1)
        last = max(t.due_date for t in tasks)
        points = []
        for i in range((last - first).days + 1):
            day = first + timezone.timedelta(days=i)
            value = Decimal("0")
            for task in tasks:
                fraction = max(
                    Decimal(0),
                    min(
                        Decimal(1),
                        Decimal((day - task.start_date).days + 1)
                        / Decimal((task.due_date - task.start_date).days + 1),
                    ),
                )
                value += fraction * task.weight / total * 100
            points.append(
                ProgressBaselinePoint(
                    project=project, date=day, planned_percent=value.quantize(_DP)
                )
            )
        project.baseline_points.all().delete()
        ProgressBaselinePoint.objects.bulk_create(points)
        project._prefetched_objects_cache = {}
        record_snapshot(project)
        record_activity(
            project,
            actor,
            ActivityAction.BASELINE_UPDATED,
            "Baseline timeline dan weighted planned progress disimpan.",
        )
