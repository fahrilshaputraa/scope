"""Gantt data and scheduling rules (roadmap G1-G9).

One payload shape feeds every Gantt (project schedule, portfolio, public page,
presentation). Scheduling rules live here so the drag endpoint, the bulk
endpoints and their tests share exactly one definition of a valid schedule.
Only the current schedule (``start_date``/``due_date``) is ever changed; the
baseline columns are written by ``capture_baseline`` alone.
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from django.urls import reverse
from django.utils import timezone

from .models import TASK_STATUS_LABELS, Task, TaskStatus
from .progress import weighted_progress

ONE = timedelta(days=1)
MAX_BULK = 200


def _iso(value):
    return value.isoformat() if value else None


def short_date(value):
    months = "Jan Feb Mar Apr Mei Jun Jul Agu Sep Okt Nov Des".split()
    return f"{value.day} {months[value.month - 1]} {value.year}" if value else "—"


def person(user):
    return (user.get_full_name() or user.username) if user else ""


def parse_day(raw):
    """Accept ISO (2026-11-08) and Indonesian day-first dates (08/11/2026, 8-11-26)."""
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(raw)


# ------------------------------------------------------------------ rules ---


@dataclass
class Plan:
    """Proposed schedule for a project: ``changes`` maps task id -> (start, end)."""

    tasks: dict
    changes: dict = field(default_factory=dict)
    extra_links: set = field(default_factory=set)

    @classmethod
    def load(cls, project):
        tasks = {
            t.pk: t
            for t in project.tasks.select_related("parent_task").prefetch_related(
                "dependencies", "successors"
            )
        }
        return cls(tasks)

    def dates(self, task):
        return self.changes.get(task.pk, (task.start_date, task.due_date))

    def children(self, task):
        return [t for t in self.tasks.values() if t.parent_task_id == task.pk]

    def predecessors(self, task):
        found = [d for d in task.dependencies.all() if d.pk in self.tasks]
        found += [self.tasks[a] for a, b in self.extra_links if b == task.pk and a in self.tasks]
        return found

    def successors(self, task):
        found = [s for s in task.successors.all() if s.pk in self.tasks]
        found += [self.tasks[b] for a, b in self.extra_links if a == task.pk and b in self.tasks]
        return found

    def move(self, task, start, end, *, carry_children=True):
        """Propose new dates; a pure move of an activity carries its details along."""
        old_start, old_end = self.dates(task)
        self.changes[task.pk] = (start, end)
        if not carry_children or not (old_start and old_end and start and end):
            return
        delta = start - old_start
        if delta and end - old_end == delta:
            for child in self.children(task):
                c_start, c_end = self.dates(child)
                if c_start and c_end:
                    self.changes[child.pk] = (c_start + delta, c_end + delta)

    def problems(self):
        """Rule violations caused by the proposed changes, as (code, message, task)."""
        found = []
        for pk in self.changes:
            task = self.tasks[pk]
            start, end = self.dates(task)
            if (start, end) == (task.start_date, task.due_date) and not self.extra_links:
                continue
            if task.status == TaskStatus.DONE:
                found.append(
                    ("done", f'Task "{task.title}" sudah selesai; jadwalnya dikunci.', task)
                )
                continue
            if not start or not end:
                found.append(("dates", "Tanggal mulai dan selesai wajib diisi.", task))
                continue
            if end < start:
                found.append(("order", "Tanggal selesai tidak boleh sebelum tanggal mulai.", task))
                continue
            parent = self.tasks.get(task.parent_task_id)
            if parent:
                p_start, p_end = self.dates(parent)
                if p_start and p_end and (start < p_start or end > p_end):
                    found.append(
                        (
                            "parent",
                            f'Detail "{task.title}" harus berada di dalam rentang activity '
                            f'"{parent.title}" ({short_date(p_start)} – {short_date(p_end)}).',
                            task,
                        )
                    )
            for child in self.children(task):
                c_start, c_end = self.dates(child)
                if c_start and c_end and (c_start < start or c_end > end):
                    found.append(
                        (
                            "children",
                            f'Rentang "{task.title}" harus mencakup detail "{child.title}" '
                            f"({short_date(c_start)} – {short_date(c_end)}).",
                            task,
                        )
                    )
                    break
            for before in self.predecessors(task):
                b_start, b_end = self.dates(before)
                if b_end and start <= b_end:
                    found.append(
                        (
                            "dependency",
                            f'"{task.title}" baru bisa dimulai setelah "{before.title}" '
                            f"selesai ({short_date(b_end)}).",
                            task,
                        )
                    )
            for after in self.successors(task):
                if after.pk in self.changes:
                    continue  # its own check reports the conflict
                a_start, _ = self.dates(after)
                if a_start and a_start <= end:
                    found.append(
                        (
                            "successor",
                            f'Task penerus "{after.title}" dimulai {short_date(a_start)}, '
                            f'sebelum "{task.title}" selesai.',
                            after,
                        )
                    )
        return found

    def shift_successors(self):
        """Push conflicting successors later, keeping durations. Returns blocking problems."""
        queue = list(self.changes)
        guard = 0
        while queue and guard < 5000:
            guard += 1
            task = self.tasks[queue.pop(0)]
            _, end = self.dates(task)
            if not end:
                continue
            for after in self.successors(task):
                a_start, a_end = self.dates(after)
                if not (a_start and a_end) or a_start > end:
                    continue
                if after.status == TaskStatus.DONE:
                    return [
                        (
                            "done",
                            f'Task penerus "{after.title}" sudah selesai sehingga tidak bisa '
                            "digeser.",
                            after,
                        )
                    ]
                delta = end - a_start + ONE
                self.move(after, a_start + delta, a_end + delta)
                queue.append(after.pk)
                queue.extend(c.pk for c in self.children(after))
        return []

    def impact(self, primary_ids=()):
        rows = []
        for pk, (start, end) in self.changes.items():
            task = self.tasks[pk]
            if (start, end) == (task.start_date, task.due_date):
                continue
            rows.append(
                {
                    "id": pk,
                    "title": task.title,
                    "old_start": _iso(task.start_date),
                    "old_end": _iso(task.due_date),
                    "start": _iso(start),
                    "end": _iso(end),
                    "primary": pk in primary_ids,
                }
            )
        return rows

    def apply(self, actor, project, *, reason="Jadwal", notify_ids=()):
        """Persist changed dates with per-task activity entries. Baselines are untouched."""
        from apps.projects.models import ActivityAction
        from apps.projects.services import record_activity

        changed = []
        for pk, (start, end) in self.changes.items():
            task = self.tasks[pk]
            if (start, end) == (task.start_date, task.due_date):
                continue
            old = (task.start_date, task.due_date)
            task.start_date, task.due_date = start, end
            task.save(update_fields=["start_date", "due_date", "updated_at"])
            record_activity(
                project,
                actor,
                ActivityAction.TIMELINE_CHANGED,
                f'{reason} task "{task.title}": {short_date(old[0])} – {short_date(old[1])} '
                f"→ {short_date(start)} – {short_date(end)}.",
                target=task if pk in notify_ids else None,
            )
            changed.append(
                {
                    "id": pk,
                    "start": _iso(start),
                    "end": _iso(end),
                    "old_start": _iso(old[0]),
                    "old_end": _iso(old[1]),
                }
            )
        return changed


def creates_cycle(predecessor, successor):
    """True when ``successor`` already (transitively) precedes ``predecessor``."""
    stack, seen = [predecessor.pk], set()
    while stack:
        current = stack.pop()
        if current == successor.pk:
            return True
        if current in seen:
            continue
        seen.add(current)
        stack.extend(
            pk
            for pk in Task._base_manager.filter(pk=current).values_list(
                "dependencies__pk", flat=True
            )
            if pk
        )
    return False


def dependency_problem(predecessor, successor):
    if predecessor.project_id != successor.project_id:
        return "Dependency hanya bisa dibuat antar task dalam project yang sama."
    if predecessor.pk == successor.pk:
        return "Task tidak bisa bergantung pada dirinya sendiri."
    if predecessor.pk in (successor.parent_task_id,) or successor.pk in (
        predecessor.parent_task_id,
    ):
        return "Activity dan detailnya sudah terhubung; dependency tidak diperlukan."
    if successor.dependencies.filter(pk=predecessor.pk).exists():
        return "Dependency ini sudah ada."
    if creates_cycle(predecessor, successor):
        return (
            f'Dependency ditolak: "{successor.title}" sudah menjadi prasyarat '
            f'"{predecessor.title}" sehingga akan membentuk siklus.'
        )
    if (
        successor.status in (TaskStatus.IN_PROGRESS, TaskStatus.REVIEW, TaskStatus.DONE)
        and predecessor.status != TaskStatus.DONE
    ):
        return (
            f'"{successor.title}" sudah berjalan; prasyarat yang belum selesai tidak bisa '
            "ditambahkan."
        )
    return ""


# ------------------------------------------------------------- bulk input ---

_SPLIT = re.compile(r"\s*[|\t;]\s*")


def parse_lines(text):
    """Turn pasted text into rows. Format per line: ``judul | mulai | selesai | pelaksana``."""
    rows = []
    for number, raw in enumerate((text or "").splitlines(), 1):
        line = raw.strip().lstrip("-*•").strip()
        if not line:
            continue
        parts = _SPLIT.split(line)
        rows.append(
            {
                "line": number,
                "title": parts[0] if parts else "",
                "start": parts[1] if len(parts) > 1 else "",
                "end": parts[2] if len(parts) > 2 else "",
                "assignee": parts[3] if len(parts) > 3 else "",
            }
        )
    return rows


def match_assignee(value, candidates):
    if value in (None, ""):
        return None
    if isinstance(value, int) or str(value).isdigit():
        return next((u for u in candidates if u.pk == int(value)), False)
    needle = str(value).strip().lstrip("@").casefold()
    for user in candidates:
        if needle in (user.username.casefold(), person(user).casefold()):
            return user
    hits = [u for u in candidates if needle and needle in person(u).casefold()]
    return hits[0] if len(hits) == 1 else False


# ---------------------------------------------------------------- payload ---


def _status_label(task):
    return TASK_STATUS_LABELS.get(task.status, task.status)


def _planned(start, end, today):
    if not (start and end):
        return None
    duration = max((end - start).days + 1, 1)
    return round(min(100, max(0, ((today - start).days + 1) / duration * 100)), 1)


def project_payload(project, user=None, *, public=False, titles=None):
    """JSON-ready Gantt payload for one project (tasks grouped by phase)."""
    from apps.identity.permissions import can_execute_task, can_manage_project

    from .assignment import assignable_users

    editable = bool(user and not public and can_manage_project(user, project))
    today = timezone.localdate()
    tasks = list(
        project.tasks.select_related("assignee", "phase", "parent_task").prefetch_related(
            "dependencies", "collaborators", "subtasks"
        )
    )
    tasks.sort(key=lambda t: (t.start_date is None, t.start_date or date.max, t.order, t.pk))
    children = {}
    for task in tasks:
        if task.parent_task_id:
            children.setdefault(task.parent_task_id, []).append(task)
    roots_by_phase = {}
    for task in tasks:
        if not task.parent_task_id:
            roots_by_phase.setdefault(task.phase_id, []).append(task)

    def task_row(task, parent_key, depth):
        lock = ""
        if task.status == TaskStatus.DONE:
            lock = "Task selesai; jadwal dikunci."
        row = {
            "id": f"t{task.pk}",
            "task": task.pk,
            "kind": "task",
            "parent": parent_key,
            "depth": depth,
            "title": titles.get(task.pk, task.title) if titles else task.title,
            "start": _iso(task.start_date),
            "end": _iso(task.due_date),
            "baseStart": _iso(task.baseline_start_date),
            "baseEnd": _iso(task.baseline_end_date),
            "progress": float(task.display_progress),
            "planned": _planned(
                task.baseline_start_date or task.start_date,
                task.baseline_end_date or task.due_date,
                today,
            ),
            "status": task.status,
            "statusLabel": _status_label(task),
            "overdue": task.is_overdue,
            "hasChildren": bool(children.get(task.pk)),
            "phase": task.phase_id,
            "subtask": bool(task.parent_task_id),
            "editable": editable and not lock,
            "lock": lock,
        }
        if not public:
            row["assignee"] = task.assignee_id
            row["assigneeName"] = task.assignee_names if task.assignee_id else ""
            row["url"] = reverse("work:task_detail", args=[task.pk])
            if user and can_execute_task(user, task):
                row["updateUrl"] = reverse("work:task_update", args=[task.pk]) + "?mode=update"
        return row

    rows = []
    phases = list(project.phases.all())
    groups = [(p.pk, p.name) for p in phases]
    if roots_by_phase.get(None) or not groups:
        groups.append((None, "Tanpa phase"))
    for phase_id, name in groups:
        roots = roots_by_phase.get(phase_id, [])
        key = f"ph{phase_id or 0}"
        dated = [t for t in roots if t.start_date and t.due_date]
        rows.append(
            {
                "id": key,
                "kind": "phase",
                "parent": None,
                "depth": 0,
                "phase": phase_id,
                "title": name,
                "start": _iso(min(t.start_date for t in dated)) if dated else None,
                "end": _iso(max(t.due_date for t in dated)) if dated else None,
                "progress": float(weighted_progress(roots)) if roots else 0.0,
                "count": len(roots),
                "editable": editable,
            }
        )
        for root in roots:
            rows.append(task_row(root, key, 1))
            for child in children.get(root.pk, []):
                rows.append(task_row(child, f"t{root.pk}", 2))
    milestones = list(project.milestones.all())
    if milestones:
        rows.append(
            {
                "id": "ms",
                "kind": "group",
                "parent": None,
                "depth": 0,
                "title": "Milestone",
                "count": len(milestones),
            }
        )
        for m in milestones:
            rows.append(
                {
                    "id": f"m{m.pk}",
                    "kind": "milestone",
                    "parent": "ms",
                    "depth": 1,
                    "title": m.name,
                    "start": _iso(m.date),
                    "end": _iso(m.date),
                    "status": m.status,
                    "statusLabel": m.get_status_display(),
                }
            )
    links = [
        {"from": dep.pk, "to": task.pk}
        for task in tasks
        for dep in task.dependencies.all()
        if not dep.archived_at
    ]
    columns = [
        {"key": "start", "label": "Mulai", "type": "date"},
        {"key": "end", "label": "Selesai", "type": "date"},
    ]
    if not public:
        columns.append({"key": "assignee", "label": "Pelaksana", "type": "person"})
    columns.append({"key": "progress", "label": "Progress", "type": "percent"})
    payload = {
        "mode": "project",
        "label": f"Jadwal {project.name}",
        "today": today.isoformat(),
        "start": _iso(project.start_date),
        "end": _iso(project.target_end_date),
        "editable": editable,
        "rows": rows,
        "links": links,
        "columns": columns,
    }
    if editable:
        people = list(assignable_users(project))
        payload["assignees"] = [{"id": u.pk, "name": person(u)} for u in people]
        payload["urls"] = {
            "data": reverse("work:gantt_data", args=[project.pk]),
            "dates": reverse("work:task_dates", args=[0]),
            "create": reverse("work:gantt_create", args=[project.pk]),
            "duplicate": reverse("work:gantt_duplicate", args=[project.pk]),
            "sequence": reverse("work:gantt_sequence", args=[project.pk]),
            "bulkDates": reverse("work:gantt_bulk_dates", args=[project.pk]),
            "dependency": reverse("work:gantt_dependency", args=[project.pk]),
            "undoCreate": reverse("work:gantt_undo_create", args=[project.pk]),
            "patch": reverse("work:gantt_patch", args=[project.pk, 0]),
            "edit": reverse("work:task_update", args=[0]),
        }
    return payload


def portfolio_payload(projects):
    """Read-only portfolio Gantt: one summary row per project, phases and milestones below."""
    from apps.projects.services import actual_progress, planned_progress_on

    today = timezone.localdate()
    projects = list(projects)
    # ``with_project_metrics`` prefetches phases and milestones; .all() reuses that cache.
    phases = {p.pk: sorted(p.phases.all(), key=lambda ph: (ph.sequence, ph.pk)) for p in projects}
    milestones = {p.pk: sorted(p.milestones.all(), key=lambda m: (m.date, m.pk)) for p in projects}
    rows = []
    for p in projects:
        planned = planned_progress_on(p)
        rows.append(
            {
                "id": f"p{p.pk}",
                "kind": "project",
                "parent": None,
                "depth": 0,
                "title": f"{p.name}",
                "code": p.code,
                "start": _iso(p.start_date),
                "end": _iso(p.target_end_date),
                "progress": float(actual_progress(p)),
                "planned": float(planned) if planned is not None else None,
                "status": p.lifecycle_status,
                "statusLabel": p.get_lifecycle_status_display(),
                "url": reverse("projects:project_timeline", args=[p.pk]),
                "count": len(phases.get(p.pk, [])) + len(milestones.get(p.pk, [])),
            }
        )
        for phase in phases.get(p.pk, []):
            rows.append(
                {
                    "id": f"ph{phase.pk}",
                    "kind": "phase",
                    "parent": f"p{p.pk}",
                    "depth": 1,
                    "title": phase.name,
                    "start": _iso(phase.start_date),
                    "end": _iso(phase.end_date),
                    "status": phase.status,
                    "statusLabel": phase.get_status_display(),
                }
            )
        for m in milestones.get(p.pk, []):
            rows.append(
                {
                    "id": f"m{m.pk}",
                    "kind": "milestone",
                    "parent": f"p{p.pk}",
                    "depth": 1,
                    "title": m.name,
                    "start": _iso(m.date),
                    "end": _iso(m.date),
                    "status": m.status,
                    "statusLabel": m.get_status_display(),
                }
            )
    dates = [d for p in projects for d in (p.start_date, p.target_end_date) if d]
    return {
        "mode": "portfolio",
        "label": "Jadwal semua project",
        "today": today.isoformat(),
        "start": _iso(min(dates)) if dates else None,
        "end": _iso(max(dates)) if dates else None,
        "editable": False,
        "rows": rows,
        "links": [],
        "collapsed": [f"p{p.pk}" for p in projects] if len(projects) > 8 else [],
        "columns": [
            {"key": "start", "label": "Mulai", "type": "date"},
            {"key": "end", "label": "Target", "type": "date"},
            {"key": "progress", "label": "Aktual", "type": "percent"},
            {"key": "planned", "label": "Rencana", "type": "percent"},
        ],
    }
