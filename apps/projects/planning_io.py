"""Versioned, permission-scoped JSON plans for AI-assisted project planning."""

import hashlib
import json
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.identity.permissions import can_create_project, can_manage_project
from apps.work.models import Task

from .models import ActivityAction, Milestone, Phase, PlanningImport, Project
from .services import capture_baseline, record_activity, record_snapshot

MAX_BYTES = 2 * 1024 * 1024
TOP_KEYS = {
    "version",
    "project",
    "members",
    "phases",
    "milestones",
    "tasks",
    "_instructions",
    "available_users",
}
PROJECT_KEYS = {
    "name",
    "code",
    "description",
    "manager",
    "team",
    "start_date",
    "target_end_date",
    "status",
}
PHASE_KEYS = {"key", "name", "start_date", "end_date", "status"}
MILESTONE_KEYS = {"key", "name", "date", "owner", "description", "status"}
TASK_KEYS = {
    "key",
    "title",
    "description",
    "phase",
    "milestone",
    "assignee",
    "collaborators",
    "status",
    "priority",
    "start_date",
    "due_date",
    "progress",
    "weight",
    "labels",
    "parent_task",
    "dependencies",
    "blocked_reason",
    "blocked_dependency",
    "baseline_start_date",
    "baseline_end_date",
}


def fail(message):
    raise ValidationError(message)


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            fail(f"Field {key} ditulis dua kali dalam JSON.")
        result[key] = value
    return result


def read_plan(upload):
    if upload.size > MAX_BYTES:
        fail("File terlalu besar. Maksimal 2 MB.")
    try:
        text = upload.read(MAX_BYTES + 1).decode("utf-8-sig").strip()
        if text.startswith("```") and text.endswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        payload = json.loads(
            text,
            object_pairs_hook=strict_object,
            parse_constant=lambda x: fail(f"Angka {x} tidak valid."),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, IndexError) as error:
        fail(f"JSON belum valid. Minta AI memperbaiki format file: {error}")
    check_keys(payload, TOP_KEYS, "File")
    if type(payload.get("version")) is not int or payload["version"] != 1:
        fail("Gunakan template PCC version 1.")
    for name, limit in (("phases", 100), ("milestones", 100), ("tasks", 500)):
        rows = payload.get(name, [])
        if not isinstance(rows, list) or len(rows) > limit:
            fail(f"{name} harus berupa daftar, maksimal {limit} item.")
    if not any(payload.get(name) for name in ("phases", "milestones", "tasks")):
        fail("Rencana masih kosong. Isi setidaknya satu tahap, milestone, atau task.")
    return payload


def check_keys(value, allowed, label):
    if not isinstance(value, dict):
        fail(f"{label} harus berupa object JSON.")
    unknown = set(value) - allowed
    if unknown:
        fail(f"{label}: field tidak dikenal: {', '.join(sorted(unknown))}. Ikuti template PCC.")


def string(value, label, required=False, maximum=10000):
    if value is None and not required:
        return ""
    if not isinstance(value, str) or (required and not value.strip()) or len(value) > maximum:
        fail(
            f"{label} harus berupa teks {'yang terisi' if required else ''}, "
            f"maksimal {maximum} karakter."
        )
    return value.strip()


def date_value(value, label, required=False):
    if value in (None, "") and not required:
        return None
    if not isinstance(value, str):
        fail(f"{label}: gunakan tanggal YYYY-MM-DD.")
    try:
        parsed = parse_date(value)
    except ValueError:
        parsed = None
    if not parsed or parsed.isoformat() != value:
        fail(f"{label}: gunakan tanggal YYYY-MM-DD yang valid.")
    return parsed


def number(value, label):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        fail(f"{label} harus berupa angka.")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        fail(f"{label} harus berupa angka.")
    if not parsed.is_finite():
        fail(f"{label} harus berupa angka finite.")
    return parsed


def indexed(rows, allowed, label):
    result = {}
    for index, row in enumerate(rows, 1):
        check_keys(row, allowed, f"{label} #{index}")
        key = string(row.get("key"), f"{label} #{index} key", True, 80)
        if key in result:
            fail(f"{label}: key {key} dipakai dua kali.")
        result[key] = row
    return result


def assert_acyclic(edges, label):
    visiting, finished = set(), set()

    def visit(key):
        if key in visiting:
            fail(f"{label} membentuk lingkaran pada {key}. Perbaiki hubungan task.")
        if key in finished:
            return
        visiting.add(key)
        for dependency in edges[key]:
            if dependency not in edges:
                fail(f"{label}: key {dependency} tidak ditemukan.")
            visit(dependency)
        visiting.remove(key)
        finished.add(key)

    for key in edges:
        visit(key)


@transaction.atomic
def import_plan(payload, actor, project=None, baseline=False):
    if project is not None and not can_manage_project(actor, project):
        fail("Hanya PM project yang dapat mengimpor rencana.")
    if project is None and not can_create_project(actor):
        fail("Anda tidak memiliki akses membuat project.")
    # Prompt/reference metadata doesn't change the imported data's identity.
    core = {
        key: value
        for key, value in payload.items()
        if key not in {"_instructions", "available_users"}
    }
    digest = hashlib.sha256(
        json.dumps(core, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    if project:
        project = Project.objects.select_for_update().get(pk=project.pk)
        previous = project.planning_imports.filter(fingerprint=digest).first()
    else:
        previous = (
            PlanningImport.objects.filter(fingerprint=digest, created_by=actor)
            .select_related("project")
            .first()
        )
        if previous and not can_manage_project(actor, previous.project):
            previous = None
    if previous:
        return {"project": previous.project, **previous.summary, "already_imported": True}

    users = {u.username: u for u in User.objects.filter(is_active=True)}

    def user_value(value, label):
        if value in (None, ""):
            return None
        if not isinstance(value, str) or value not in users:
            fail(
                f"{label}: username {value!r} tidak tersedia. "
                "Gunakan available_users dari template."
            )
        return users[value]

    info = payload.get("project", {})
    check_keys(info, PROJECT_KEYS, "project")
    if project:
        if info.get("code") and info["code"] != project.code:
            fail(
                "Kode dalam file berbeda dengan project ini. "
                "Pilih project yang sesuai atau gunakan templatenya."
            )
    else:
        manager = user_value(info.get("manager"), "Project Manager") or actor
        if not actor.is_staff and manager.pk != actor.pk:
            fail("Project baru harus menggunakan Anda sebagai PM.")
        if not manager.is_staff and manager.pcc_profile.role != "pm":
            fail("Project Manager harus memiliki role PM.")
        project = Project(
            name=string(info.get("name"), "Nama project", True, 200),
            code=string(info.get("code"), "Kode project", maximum=40)
            or "PRJ-" + uuid4().hex[:10].upper(),
            manager=manager,
            start_date=date_value(info.get("start_date"), "Project mulai", True),
            target_end_date=date_value(info.get("target_end_date"), "Project target selesai", True),
            description=string(info.get("description", ""), "Deskripsi project"),
            team=string(info.get("team", ""), "Tim", maximum=100),
            status=info.get("status", "planning"),
        )
        project.full_clean()
        project.save()

    member_names = payload.get("members", [])
    if not isinstance(member_names, list) or len(member_names) > 200:
        fail("members harus berupa daftar username, maksimal 200 orang.")
    members = {user_value(name, "Anggota") for name in member_names}
    members.discard(None)
    phase_rows = indexed(payload.get("phases", []), PHASE_KEYS, "Tahap")
    milestone_rows = indexed(payload.get("milestones", []), MILESTONE_KEYS, "Milestone")
    task_rows = indexed(payload.get("tasks", []), TASK_KEYS, "Task")
    phases, milestones, tasks = {}, {}, {}
    sequence = project.phases.aggregate(last=Max("sequence"))["last"] or 0
    for index, (key, row) in enumerate(phase_rows.items(), 1):
        phase = Phase(
            project=project,
            name=string(row.get("name"), f"Tahap {key} nama", True, 200),
            sequence=sequence + index,
            start_date=date_value(row.get("start_date"), f"Tahap {key} mulai"),
            end_date=date_value(row.get("end_date"), f"Tahap {key} selesai"),
            status=row.get("status", "not_started"),
        )
        phase.full_clean()
        phase.save()
        phases[key] = phase
    for key, row in milestone_rows.items():
        owner = user_value(row.get("owner"), f"Milestone {key} owner")
        milestone = Milestone(
            project=project,
            name=string(row.get("name"), f"Milestone {key} nama", True, 200),
            date=date_value(row.get("date"), f"Milestone {key} tanggal", True),
            owner=owner,
            status=row.get("status", "upcoming"),
            description=string(row.get("description", ""), f"Milestone {key} deskripsi"),
        )
        milestone.full_clean()
        milestone.save()
        milestones[key] = milestone
        if owner:
            members.add(owner)

    dependency_edges, parent_edges = {}, {}
    for key, row in task_rows.items():
        dependencies = row.get("dependencies", [])
        if not isinstance(dependencies, list) or any(not isinstance(v, str) for v in dependencies):
            fail(f"Task {key}: dependencies harus berupa daftar key task.")
        dependency_edges[key] = dependencies
        parent = row.get("parent_task")
        if parent is not None and not isinstance(parent, str):
            fail(f"Task {key}: parent_task harus berupa key task atau null.")
        parent_edges[key] = [parent] if parent else []
    assert_acyclic(dependency_edges, "Dependency")
    assert_acyclic(parent_edges, "Task induk")

    def relation(mapping, key, label):
        if key in (None, ""):
            return None
        if not isinstance(key, str) or key not in mapping:
            fail(f"{label}: key {key!r} tidak ditemukan dalam file.")
        return mapping[key]

    for index, (key, row) in enumerate(task_rows.items()):
        assignee = user_value(row.get("assignee"), f"Task {key} assignee")
        collaborators = row.get("collaborators", [])
        if not isinstance(collaborators, list) or len(collaborators) > 1:
            fail(f"Task {key}: pilih maksimal satu rekan pengerjaan.")
        collaborators = [user_value(value, f"Task {key} rekan") for value in collaborators]
        if any(person is None or person == assignee for person in collaborators):
            fail(f"Task {key}: rekan harus pengguna valid yang berbeda dari assignee.")
        if collaborators and not assignee:
            fail(f"Task {key}: tentukan assignee sebelum menambahkan rekan.")
        task = Task(
            project=project,
            title=string(row.get("title"), f"Task {key} judul", True, 200),
            description=string(row.get("description", ""), f"Task {key} deskripsi"),
            phase=relation(phases, row.get("phase"), f"Task {key} phase"),
            milestone=relation(milestones, row.get("milestone"), f"Task {key} milestone"),
            assignee=assignee,
            status=row.get("status", "todo"),
            priority=row.get("priority", "medium"),
            progress=number(row.get("progress", 0), f"Task {key} progress"),
            weight=number(row.get("weight", 1), f"Task {key} bobot"),
            order=index,
            labels=string(row.get("labels", ""), f"Task {key} labels", maximum=200),
            blocked_reason=string(row.get("blocked_reason", ""), f"Task {key} alasan hambatan"),
            blocked_dependency=string(
                row.get("blocked_dependency", ""), f"Task {key} menunggu", maximum=200
            ),
        )
        for field in ("start_date", "due_date", "baseline_start_date", "baseline_end_date"):
            setattr(task, field, date_value(row.get(field), f"Task {key} {field}"))
        if task.status in ("in_progress", "done") and any(
            task_rows[dep].get("status", "todo") != "done" for dep in dependency_edges[key]
        ):
            fail(f"Task {key}: selesaikan dependency sebelum memulai atau menyelesaikan task.")
        task.full_clean()
        task.save()
        tasks[key] = task
        task.collaborators.set(collaborators)
        members.update(collaborators)
        if assignee:
            members.add(assignee)
    for key, task in tasks.items():
        if parent_edges[key]:
            task.parent_task = tasks[parent_edges[key][0]]
            task.full_clean()
            task.save()
        task.dependencies.set(tasks[dep] for dep in dependency_edges[key])
    project.members.add(*members)
    if baseline:
        capture_baseline(project, actor)
    record_snapshot(project)
    summary = {"tasks": len(tasks), "phases": len(phases), "milestones": len(milestones)}
    PlanningImport.objects.create(
        project=project, fingerprint=digest, created_by=actor, summary=summary
    )
    record_activity(
        project,
        actor,
        ActivityAction.PROJECT_UPDATED,
        f"Rencana diimpor: {len(tasks)} task, {len(phases)} tahap, {len(milestones)} milestone.",
    )
    return {"project": project, **summary, "already_imported": False}


def planning_template(actor, project=None):
    first = project.start_date if project else timezone.localdate()
    last = project.target_end_date if project else first + timezone.timedelta(days=30)
    users = User.objects.filter(is_active=True).select_related("pcc_profile").order_by("username")
    return {
        "version": 1,
        "_instructions": (
            "Isi JSON ini untuk rencana PCC. Jangan ubah version. Tanggal YYYY-MM-DD. "
            "Username hanya dari available_users; null jika belum ditugaskan. "
            "key unik dalam setiap daftar. phase/milestone/parent_task/dependencies "
            "memakai key, bukan ID database. Dependency tidak boleh melingkar. "
            "Untuk project yang sudah ada, pertahankan project.code. "
            "File menambahkan data baru; tidak menghapus/mengubah data lama. "
            "Boleh hapus contoh dan buat daftar sendiri. Kembalikan file JSON, tanpa narasi."
        ),
        "available_users": [{"username": u.username, "name": u.pcc_profile.name} for u in users],
        "project": {
            "name": project.name if project else "Nama project Anda",
            "code": project.code if project else "",
            "manager": actor.username,
            "start_date": first.isoformat(),
            "target_end_date": last.isoformat(),
        },
        "members": [actor.username],
        "phases": [
            {
                "key": "persiapan",
                "name": "Persiapan",
                "start_date": first.isoformat(),
                "end_date": last.isoformat(),
            }
        ],
        "milestones": [
            {
                "key": "rilis",
                "name": "Siap rilis",
                "date": last.isoformat(),
                "owner": actor.username,
            }
        ],
        "tasks": [
            {
                "key": "task-1",
                "title": "Susun kebutuhan",
                "phase": "persiapan",
                "assignee": actor.username,
                "collaborators": [],
                "start_date": first.isoformat(),
                "due_date": first.isoformat(),
                "weight": 1,
                "dependencies": [],
            },
            {
                "key": "task-2",
                "title": "Implementasi",
                "phase": "persiapan",
                "milestone": "rilis",
                "assignee": None,
                "collaborators": [],
                "start_date": last.isoformat(),
                "due_date": last.isoformat(),
                "weight": 2,
                "dependencies": ["task-1"],
            },
        ],
    }


def export_plan(project):
    phases = list(project.phases.all())
    milestones = list(project.milestones.select_related("owner"))
    tasks = list(
        project.tasks.select_related("assignee").prefetch_related("dependencies", "collaborators")
    )

    def iso(value):
        return value.isoformat() if value else None

    return {
        "version": 1,
        "project": {
            "name": project.name,
            "code": project.code,
            "description": project.description,
            "manager": project.manager.username if project.manager else None,
            "team": project.team,
            "start_date": iso(project.start_date),
            "target_end_date": iso(project.target_end_date),
            "status": project.status,
        },
        "members": list(project.members.values_list("username", flat=True)),
        "phases": [
            {
                "key": f"phase-{p.pk}",
                "name": p.name,
                "start_date": iso(p.start_date),
                "end_date": iso(p.end_date),
                "status": p.status,
            }
            for p in phases
        ],
        "milestones": [
            {
                "key": f"milestone-{m.pk}",
                "name": m.name,
                "date": iso(m.date),
                "owner": m.owner.username if m.owner else None,
                "description": m.description,
                "status": m.status,
            }
            for m in milestones
        ],
        "tasks": [
            {
                "key": f"task-{t.pk}",
                "title": t.title,
                "description": t.description,
                "phase": f"phase-{t.phase_id}" if t.phase_id else None,
                "milestone": f"milestone-{t.milestone_id}" if t.milestone_id else None,
                "assignee": t.assignee.username if t.assignee else None,
                "collaborators": [user.username for user in t.collaborators.all()],
                "status": t.status,
                "priority": t.priority,
                "start_date": iso(t.start_date),
                "due_date": iso(t.due_date),
                "baseline_start_date": iso(t.baseline_start_date),
                "baseline_end_date": iso(t.baseline_end_date),
                "progress": str(t.display_progress),
                "weight": str(t.weight),
                "labels": t.labels,
                "parent_task": f"task-{t.parent_task_id}" if t.parent_task_id else None,
                "dependencies": [f"task-{dep.pk}" for dep in t.dependencies.all()],
                "blocked_reason": t.blocked_reason,
                "blocked_dependency": t.blocked_dependency,
            }
            for t in tasks
        ],
    }
