"""JSON endpoints behind the interactive Gantt (roadmap G4-G7 and quick planning).

Every endpoint answers ``{"ok": true, ...}`` or ``{"ok": false, "error": "..."}`` with
an HTTP status the client can act on: 400 invalid input or rule violation, 403 not
the project's PM/Admin, 404 outside the user's projects, 409 successor conflict.
"""

import json
from datetime import timedelta
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Max
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.identity.permissions import can_manage_project, visible_projects
from apps.identity.roles import has_perm
from apps.projects.models import ActivityAction
from apps.projects.services import record_activity

from .assignment import assignable_users
from .gantt import (
    MAX_BULK,
    ONE,
    Plan,
    dependency_problem,
    match_assignee,
    parse_day,
    parse_lines,
    project_payload,
    short_date,
)
from .models import Task, TaskStatus


def fail(message, status=400, **extra):
    return JsonResponse({"ok": False, "error": message, **extra}, status=status)


def _body(request):
    if request.content_type == "application/json":
        try:
            data = json.loads(request.body or b"{}")
        except ValueError:
            return None
        return data if isinstance(data, dict) else None
    return request.POST.dict()


def json_404(view):
    """Answer JSON instead of the HTML 404 page so the Gantt can show the reason."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except Http404:
            return fail("Project atau task tidak ditemukan, atau Anda tidak punya akses.", 404)

    return wrapper


def _project(request, pk):
    return get_object_or_404(visible_projects(request.user), pk=pk)


def _guard(request, project):
    if not can_manage_project(request.user, project):
        return fail("Hanya PM project atau Admin yang dapat mengubah jadwal.", 403)
    return None


def _ids(raw):
    if not isinstance(raw, list) or not raw:
        return None
    try:
        return [int(x) for x in raw]
    except (TypeError, ValueError):
        return None


def _problem_response(problems):
    code, message, task = problems[0]
    return fail(message, code=code, task=task.pk, errors=[m for _, m, _ in problems])


@login_required
@json_404
@require_GET
def gantt_data(request, pk):
    project = _project(request, pk)
    return JsonResponse({"ok": True, "gantt": project_payload(project, request.user)})


def schedule(request, project, plan, *, primary, shift, preview, reason):
    """Shared tail of every schedule change: validate, optional shift, preview, save."""
    problems = [p for p in plan.problems() if p[0] != "successor"]
    if problems:
        return _problem_response(problems)
    conflicts = [p for p in plan.problems() if p[0] == "successor"]
    if conflicts or shift:
        blocking = plan.shift_successors()
        if blocking:
            return _problem_response(blocking)
        if conflicts and not shift:
            impact = plan.impact(primary)
            return fail(
                f"Jadwal baru bertabrakan dengan {len(conflicts)} task penerus.",
                409,
                code="successor_conflict",
                impact=impact,
            )
        problems = plan.problems()
        if problems:
            return _problem_response(problems)
    if preview:
        return JsonResponse({"ok": True, "preview": True, "impact": plan.impact(primary)})
    changed = plan.apply(request.user, project, reason=reason, notify_ids=primary)
    return JsonResponse({"ok": True, "changes": changed})


# ----------------------------------------------------------------- dates ---


@login_required
@json_404
@require_POST
@transaction.atomic
def gantt_bulk_dates(request, pk):
    """Set several tasks' dates at once (undo, keyboard batches). No implicit shifting."""
    project = _project(request, pk)
    if denied := _guard(request, project):
        return denied
    data = _body(request)
    rows = data.get("changes") if data else None
    if not isinstance(rows, list) or not rows or len(rows) > MAX_BULK:
        return fail("Kirim daftar perubahan tanggal.")
    plan = Plan.load(project)
    for row in rows:
        try:
            task = plan.tasks[int(row["id"])]
            start, end = parse_day(row.get("start")), parse_day(row.get("end"))
        except (KeyError, TypeError, ValueError):
            return fail("Perubahan tanggal tidak valid atau task bukan bagian project ini.")
        if start is None or end is None:
            return fail("Tanggal mulai dan selesai wajib diisi.")
        plan.move(task, start, end, carry_children=False)
    return schedule(
        request,
        project,
        plan,
        primary=set(),
        shift=bool(data.get("shift_successors")),
        preview=bool(data.get("preview")),
        reason="Urungkan jadwal" if data.get("reason") == "undo" else "Jadwal",
    )


@login_required
@json_404
@require_POST
@transaction.atomic
def gantt_sequence(request, pk):
    """Auto-schedule: chain the given tasks one after another, keeping durations."""
    project = _project(request, pk)
    if denied := _guard(request, project):
        return denied
    data = _body(request) or {}
    ids = _ids(data.get("ids"))
    if not ids or len(ids) < 2:
        return fail("Pilih minimal dua task untuk disusun berurutan.")
    plan = Plan.load(project)
    if any(i not in plan.tasks for i in ids):
        return fail("Sebagian task tidak ditemukan di project ini.", 404)
    tasks = [plan.tasks[i] for i in dict.fromkeys(ids)]
    try:
        anchor = parse_day(data.get("start"))
        default = max(1, min(365, int(data.get("duration") or 1)))
    except (TypeError, ValueError):
        return fail("Tanggal mulai atau durasi tidak valid.")
    anchor = anchor or min(
        (t.start_date for t in tasks if t.start_date), default=timezone.localdate()
    )
    cursor = anchor
    for task in tasks:
        if task.status == TaskStatus.DONE:
            return fail(f'Task "{task.title}" sudah selesai; jadwalnya dikunci.', code="done")
        days = (
            (task.due_date - task.start_date).days + 1
            if task.start_date and task.due_date
            else default
        )
        plan.move(task, cursor, cursor + timedelta(days=days - 1))
        cursor = cursor + timedelta(days=days)
    link = bool(data.get("link"))
    if link:
        for before, after in zip(tasks, tasks[1:], strict=False):
            if after.dependencies.filter(pk=before.pk).exists():
                continue
            problem = dependency_problem(before, after)
            if problem:
                return fail(problem, code="dependency")
            plan.extra_links.add((before.pk, after.pk))
    response = schedule(
        request,
        project,
        plan,
        primary={t.pk for t in tasks},
        shift=bool(data.get("shift_successors")),
        preview=bool(data.get("preview")),
        reason="Susun berurutan",
    )
    payload = json.loads(response.content)
    if payload.get("ok") and not payload.get("preview") and link:
        added = []
        for before, after in plan.extra_links:
            plan.tasks[after].dependencies.add(before)
            added.append({"from": before, "to": after})
        record_activity(
            project,
            request.user,
            ActivityAction.TASK_UPDATED,
            f"{len(added)} dependency ditambahkan saat menyusun task berurutan.",
        )
        payload["links"] = added
        return JsonResponse(payload)
    return response


# ---------------------------------------------------------------- create ---


def _next_order(project):
    return (project.tasks.aggregate(top=Max("order"))["top"] or 0) + 1


@login_required
@json_404
@require_POST
@transaction.atomic
def gantt_create(request, pk):
    """Create one or many tasks: drag-create (``items``) or pasted list (``text``)."""
    project = _project(request, pk)
    if denied := _guard(request, project):
        return denied
    data = _body(request)
    if data is None:
        return fail("Format permintaan tidak valid.")
    if isinstance(data.get("items"), list):
        rows = [
            {"line": n, **row} for n, row in enumerate(data["items"], 1) if isinstance(row, dict)
        ]
    else:
        rows = parse_lines(data.get("text", ""))
    if not rows:
        return fail("Tulis minimal satu judul task.")
    if len(rows) > MAX_BULK:
        return fail(f"Maksimal {MAX_BULK} task sekaligus.")
    parent = phase = None
    if data.get("parent"):
        parent = project.tasks.filter(pk=data["parent"], parent_task__isnull=True).first()
        if parent is None:
            return fail("Activity induk tidak ditemukan di project ini.")
        phase = parent.phase
    elif data.get("phase"):
        phase = project.phases.filter(pk=data["phase"]).first()
        if phase is None:
            return fail("Phase tidak ditemukan di project ini.")
    try:
        duration = max(1, min(365, int(data.get("duration") or 3)))
        anchor = parse_day(data.get("start"))
    except (TypeError, ValueError):
        return fail("Tanggal mulai atau durasi tidak valid.")
    sequential = data.get("sequential", True) not in (False, "false", "0", 0)
    if parent and parent.start_date:
        anchor = anchor or parent.start_date
    cursor = anchor or timezone.localdate()
    candidates = list(assignable_users(project))
    order = _next_order(project)
    prepared = []
    for row in rows:
        where = f"Baris {row['line']}: " if len(rows) > 1 else ""
        title = str(row.get("title") or "").strip()
        if not title:
            return fail(f"{where}judul task wajib diisi.", line=row["line"])
        if len(title) > 200:
            return fail(f"{where}judul maksimal 200 karakter.", line=row["line"])
        try:
            start, end = parse_day(row.get("start")), parse_day(row.get("end"))
        except ValueError as exc:
            return fail(
                f'{where}tanggal "{exc}" tidak dikenali. Pakai 2026-11-08 atau 08/11/2026.',
                line=row["line"],
            )
        if start and not end:
            end = start + timedelta(days=duration - 1)
        if end and not start:
            start = end - timedelta(days=duration - 1)
        if not start and sequential:
            start, end = cursor, cursor + timedelta(days=duration - 1)
        if start and end:
            if end < start:
                return fail(
                    f"{where}tanggal selesai tidak boleh sebelum tanggal mulai.", line=row["line"]
                )
            if (
                parent
                and parent.start_date
                and parent.due_date
                and (start < parent.start_date or end > parent.due_date)
            ):
                return fail(
                    f"{where}detail harus berada di dalam rentang activity "
                    f'"{parent.title}" ({short_date(parent.start_date)} – '
                    f"{short_date(parent.due_date)}).",
                    line=row["line"],
                    code="parent",
                )
            cursor = end + ONE
        assignee = match_assignee(row.get("assignee"), candidates)
        if assignee is False:
            return fail(
                f'{where}pelaksana "{row.get("assignee")}" bukan anggota pelaksana project.',
                line=row["line"],
            )
        prepared.append((title, start, end, assignee))
    created = []
    for title, start, end, assignee in prepared:
        task = Task(
            project=project,
            title=title,
            start_date=start,
            due_date=end,
            assignee=assignee,
            phase=phase,
            parent_task=parent,
            order=order,
        )
        order += 1
        task.save()
        created.append(task)
    record_activity(
        project,
        request.user,
        ActivityAction.TASK_CREATED,
        f'Task "{created[0].title}" dibuat dari Gantt.'
        if len(created) == 1
        else f"{len(created)} task dibuat sekaligus dari Gantt.",
        target=created[0] if len(created) == 1 and created[0].assignee_id else None,
    )
    return JsonResponse({"ok": True, "ids": [t.pk for t in created]}, status=201)


@login_required
@json_404
@require_POST
@transaction.atomic
def gantt_duplicate(request, pk):
    """Copy tasks (with their details) and place the copies right after the originals."""
    project = _project(request, pk)
    if denied := _guard(request, project):
        return denied
    data = _body(request) or {}
    ids = _ids(data.get("ids"))
    if not ids:
        return fail("Pilih task yang akan diduplikasi.")
    if len(ids) > MAX_BULK:
        return fail(f"Maksimal {MAX_BULK} task sekaligus.")
    chosen = list(
        project.tasks.filter(pk__in=ids)
        .select_related("parent_task")
        .prefetch_related("subtasks", "dependencies")
    )
    if len(chosen) != len(set(ids)):
        return fail("Sebagian task tidak ditemukan di project ini.", 404)
    chosen_ids = {t.pk for t in chosen}
    # A selected detail is copied with its activity when that activity is selected too.
    sources = [t for t in chosen if t.parent_task_id not in chosen_ids]
    starts = [t.start_date for t in chosen if t.start_date]
    ends = [t.due_date for t in chosen if t.due_date]
    offset = (
        timedelta(days=(max(ends) - min(starts)).days + 1)
        if starts and ends and data.get("place", "after") == "after"
        else timedelta(0)
    )
    order = _next_order(project)
    mapping = {}

    def copy(task, parent, shift):
        nonlocal order
        clone = Task(
            project=project,
            title=(f"{task.title} (salinan)" if parent is task.parent_task else task.title)[:200],
            description=task.description,
            phase_id=task.phase_id,
            milestone_id=task.milestone_id,
            parent_task=parent,
            assignee_id=task.assignee_id,
            priority=task.priority,
            weight=task.weight,
            labels=task.labels,
            status=TaskStatus.BACKLOG if task.status == TaskStatus.BACKLOG else TaskStatus.TODO,
            start_date=task.start_date + shift if task.start_date else None,
            due_date=task.due_date + shift if task.due_date else None,
            order=order,
        )
        order += 1
        clone.save()
        mapping[task.pk] = clone
        return clone

    for task in sources:
        shift = offset
        parent = task.parent_task
        if parent and task.start_date and task.due_date and parent.due_date:
            # A lone detail must stay inside its activity; keep its dates when it would not.
            if task.due_date + shift > parent.due_date:
                shift = timedelta(0)
        clone = copy(task, parent, shift)
        if not task.parent_task_id:
            for child in task.subtasks.all():
                copy(child, clone, shift)
    originals = Task.objects.filter(pk__in=mapping).prefetch_related("dependencies")
    for source in originals:
        for dep in source.dependencies.all():
            if dep.pk in mapping:
                mapping[source.pk].dependencies.add(mapping[dep.pk])
    record_activity(
        project,
        request.user,
        ActivityAction.TASK_CREATED,
        f"{len(mapping)} task diduplikasi dari Gantt.",
    )
    return JsonResponse({"ok": True, "ids": [c.pk for c in mapping.values()]}, status=201)


@login_required
@json_404
@require_POST
@transaction.atomic
def gantt_undo_create(request, pk):
    """Undo a quick creation: remove tasks that were just made and never worked on."""
    project = _project(request, pk)
    if denied := _guard(request, project):
        return denied
    ids = _ids((_body(request) or {}).get("ids"))
    if not ids:
        return fail("Tidak ada task untuk diurungkan.")
    tasks = list(project.tasks.filter(pk__in=ids))
    if len(tasks) != len(set(ids)):
        return fail("Sebagian task sudah tidak ada.", 404)
    recent = timezone.now() - timedelta(hours=1)
    for task in tasks:
        untouched = (
            task.created_at >= recent
            and task.progress == 0
            and task.status in (TaskStatus.BACKLOG, TaskStatus.TODO)
            and not task.comments.exists()
            and not task.attachments.exists()
            and not task.issues.exists()
        )
        if not untouched:
            return fail(
                f'"{task.title}" sudah dikerjakan atau dibuat lebih dari satu jam lalu; '
                "arsipkan dari halaman task bila perlu."
            )
    count = len(tasks)
    Task.objects.filter(pk__in=[t.pk for t in tasks]).delete()
    record_activity(
        project,
        request.user,
        ActivityAction.TASK_ARCHIVED,
        f"Pembuatan {count} task diurungkan.",
    )
    return JsonResponse({"ok": True, "removed": count})


# ---------------------------------------------------------- inline edits ---


@login_required
@json_404
@require_POST
@transaction.atomic
def gantt_patch(request, pk, task_pk):
    """Inline edit from the tree: title and/or assignee."""
    project = _project(request, pk)
    if denied := _guard(request, project):
        return denied
    task = get_object_or_404(project.tasks.prefetch_related("collaborators"), pk=task_pk)
    data = _body(request) or {}
    fields, notes = [], []
    if "title" in data:
        title = str(data.get("title") or "").strip()
        if not title:
            return fail("Judul task wajib diisi.")
        if len(title) > 200:
            return fail("Judul maksimal 200 karakter.")
        if title != task.title:
            notes.append(f'judul "{task.title}" → "{title}"')
            task.title = title
            fields.append("title")
    if "assignee" in data:
        if task.assignee_id and not has_perm(request.user, "task.reassign"):
            return fail("Anda tidak berhak memindahkan penugasan task.", 403)
        raw = data.get("assignee")
        user = None
        if raw not in (None, ""):
            user = match_assignee(raw, list(assignable_users(project, task.assignee_id)))
            if not user:
                return fail("Pilih pelaksana yang terlibat di project (bukan PM project).")
        if user and task.collaborators.filter(pk=user.pk).exists():
            return fail("Pelaksana harus berbeda dari rekan task.")
        if user is None and task.collaborators.exists():
            return fail("Hapus rekan task terlebih dahulu sebelum mengosongkan pelaksana.")
        if (user.pk if user else None) != task.assignee_id:
            task.assignee = user
            fields.append("assignee")
            notes.append("pelaksana diperbarui")
    if fields:
        task.save(update_fields=[*fields, "updated_at"])
        record_activity(
            project,
            request.user,
            ActivityAction.TASK_ASSIGNED if "assignee" in fields else ActivityAction.TASK_UPDATED,
            f'Task "{task.title}": {", ".join(notes)}.',
            target=task if "assignee" in fields else None,
        )
    return JsonResponse(
        {
            "ok": True,
            "id": task.pk,
            "title": task.title,
            "assignee": task.assignee_id,
        }
    )


@login_required
@json_404
@require_POST
@transaction.atomic
def gantt_dependency(request, pk):
    """Add or remove a finish-to-start dependency (predecessor → successor)."""
    project = _project(request, pk)
    if denied := _guard(request, project):
        return denied
    data = _body(request) or {}
    try:
        before = project.tasks.get(pk=int(data.get("from")))
        after = project.tasks.get(pk=int(data.get("to")))
    except (Task.DoesNotExist, TypeError, ValueError):
        return fail("Task dependency tidak ditemukan di project ini.", 404)
    action = data.get("action", "add")
    if action == "remove":
        if not after.dependencies.filter(pk=before.pk).exists():
            return fail("Dependency ini sudah tidak ada.")
        after.dependencies.remove(before)
        message = f'Dependency "{before.title}" → "{after.title}" dihapus.'
        warning = ""
    elif action == "add":
        problem = dependency_problem(before, after)
        if problem:
            return fail(problem, code="dependency")
        after.dependencies.add(before)
        message = f'Dependency "{before.title}" → "{after.title}" ditambahkan.'
        warning = ""
        if before.due_date and after.start_date and after.start_date <= before.due_date:
            warning = (
                f'"{after.title}" dimulai sebelum "{before.title}" selesai. '
                "Geser penerus agar jadwal sesuai."
            )
    else:
        return fail("Aksi dependency tidak dikenal.")
    record_activity(project, request.user, ActivityAction.TASK_UPDATED, message)
    return JsonResponse({"ok": True, "from": before.pk, "to": after.pk, "warning": warning})
