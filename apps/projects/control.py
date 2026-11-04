"""Pemantauan dan kontrol pelaksanaan project (PRD §6.2, §10.2, §12.5).

Pengecualian task yang perlu ditindaklanjuti PM: terlambat, terhambat, menunggu
review, terlambat mulai, dan menyimpang dari baseline.
"""

from django.db.models import F, Q
from django.utils import timezone

from apps.work.models import Task, TaskStatus

NOT_STARTED = (TaskStatus.BACKLOG, TaskStatus.TODO)

FLAG_LABELS = {
    "overdue": "Terlambat",
    "blocked": "Terhambat",
    "review": "Menunggu review",
    "late_start": "Terlambat mulai",
    "deviation": "Melewati baseline",
    "not_started": "Belum dimulai",
    "done": "Selesai",
}
FLAGS = tuple(FLAG_LABELS)

#: Tanda yang menunjukkan masalah (dipakai untuk ringkasan dan Project Control).
EXCEPTION_FLAGS = ("overdue", "blocked", "review", "late_start", "deviation")


def flag_filter(flag: str, today=None) -> Q:
    today = today or timezone.localdate()
    if flag == "overdue":
        return Q(due_date__lt=today) & ~Q(status=TaskStatus.DONE)
    if flag == "blocked":
        return Q(status=TaskStatus.BLOCKED)
    if flag == "review":
        return Q(status=TaskStatus.REVIEW)
    if flag == "late_start":
        return Q(start_date__lt=today, status__in=NOT_STARTED)
    if flag == "deviation":
        return Q(due_date__isnull=False, baseline_end_date__isnull=False) & Q(
            due_date__gt=F("baseline_end_date")
        )
    if flag == "not_started":
        return Q(status__in=NOT_STARTED)
    if flag == "done":
        return Q(status=TaskStatus.DONE)
    return Q()


def task_flags(task, today=None) -> list[str]:
    """Tanda yang berlaku untuk satu task (urut sesuai ``FLAGS``)."""
    today = today or timezone.localdate()
    active = []
    if task.status == TaskStatus.DONE:
        return ["done"]
    if task.due_date and task.due_date < today:
        active.append("overdue")
    if task.status == TaskStatus.BLOCKED:
        active.append("blocked")
    if task.status == TaskStatus.REVIEW:
        active.append("review")
    if task.start_date and task.start_date < today and task.status in NOT_STARTED:
        active.append("late_start")
    if task.due_date and task.baseline_end_date and task.due_date > task.baseline_end_date:
        active.append("deviation")
    if task.status in NOT_STARTED:
        active.append("not_started")
    return [flag for flag in FLAGS if flag in active]


def flag_counts(tasks, flags=FLAGS) -> dict[str, int]:
    today = timezone.localdate()
    return {flag: tasks.filter(flag_filter(flag, today)).count() for flag in flags}


def exception_total(counts: dict[str, int]) -> int:
    return sum(counts.get(flag, 0) for flag in ("overdue", "blocked", "review"))


def project_tasks(project):
    return Task.objects.filter(project=project).select_related(
        "assignee", "phase", "parent_task"
    )
