"""Template project (R7.5) dan field tambahan (R7.6).

Template menyimpan struktur dalam JSON dengan offset hari dari tanggal mulai project.
Admin dapat menulis struktur sebagai outline singkat::

    Perencanaan
    - Kickoff | 2
    - Analisis kebutuhan | 5
    -- Wawancara pengguna | 2
    Pengembangan
    + Backend
    - API pemesanan | 10
    * Go-live | 45

Baris tanpa awalan adalah phase, ``+`` work package, ``-`` task, ``--`` detail activity,
dan ``*`` milestone. Angka setelah ``|`` adalah durasi (hari) atau hari ke-n untuk
milestone. Project yang dibuat dari template menyalin isinya; mengubah template tidak
mengubah project yang sudah ada.
"""

import re
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify

DEFAULT_DURATION = 5
MAX_LINES = 500
FIELD_TYPES = {"teks": "text", "angka": "number", "tanggal": "date"}
FIELD_TYPE_LABELS = {v: k for k, v in FIELD_TYPES.items()}


# ----------------------------------------------------------------- outline ---


def _split(line):
    name, _, number = line.partition("|")
    name = name.strip()
    number = number.strip()
    if number and not number.isdigit():
        raise ValidationError(f'Angka setelah "|" harus bilangan bulat: "{line.strip()}".')
    return name, int(number) if number else None


def outline_to_structure(text: str) -> dict:
    lines = [raw.rstrip() for raw in (text or "").splitlines() if raw.strip()]
    if len(lines) > MAX_LINES:
        raise ValidationError(f"Outline maksimal {MAX_LINES} baris.")
    structure = {"phases": [], "tasks": [], "milestones": []}
    phase = package = task = None
    cursor = 0
    for raw in lines:
        line = raw.strip()
        if line.startswith("--"):
            if task is None:
                raise ValidationError(f'Detail activity "{line}" harus berada di bawah task.')
            name, duration = _split(line[2:])
            used = sum(s["duration"] for s in task["subtasks"])
            task["subtasks"].append(
                {
                    "title": name,
                    "offset": task["offset"] + used,
                    "duration": duration or 1,
                    "weight": "1",
                }
            )
            continue
        if line.startswith("-"):
            name, duration = _split(line[1:])
            task = {
                "title": name,
                "offset": cursor,
                "duration": duration or DEFAULT_DURATION,
                "weight": "1",
                "method": "manual",
                "package": package,
                "subtasks": [],
            }
            cursor += task["duration"]
            (phase["tasks"] if phase else structure["tasks"]).append(task)
            if phase:
                phase["duration"] = cursor - phase["offset"]
            continue
        if line.startswith("+"):
            if phase is None:
                raise ValidationError(f'Work package "{line}" harus berada di bawah phase.')
            package = _split(line[1:])[0]
            phase["packages"].append({"name": package})
            task = None
            continue
        if line.startswith("*"):
            name, day = _split(line[1:])
            structure["milestones"].append(
                {"name": name, "offset": day if day is not None else cursor}
            )
            continue
        name, _ = _split(line)
        phase = {"name": name, "offset": cursor, "duration": 0, "packages": [], "tasks": []}
        structure["phases"].append(phase)
        package = task = None
    for item in structure["phases"]:
        if not item["name"]:
            raise ValidationError("Nama phase tidak boleh kosong.")
    return structure


def structure_to_outline(structure: dict) -> str:
    lines = []

    def task_lines(task):
        lines.append(f"- {task['title']} | {task.get('duration') or DEFAULT_DURATION}")
        for sub in task.get("subtasks", []):
            lines.append(f"-- {sub['title']} | {sub.get('duration') or 1}")

    for task in structure.get("tasks", []):
        task_lines(task)
    for phase in structure.get("phases", []):
        lines.append(phase["name"])
        tasks = phase.get("tasks", [])
        for task in [t for t in tasks if not t.get("package")]:
            task_lines(task)
        for package in phase.get("packages", []):
            lines.append(f"+ {package['name']}")
            for task in [t for t in tasks if t.get("package") == package["name"]]:
                task_lines(task)
    for milestone in structure.get("milestones", []):
        lines.append(f"* {milestone['name']} | {milestone.get('offset', 0)}")
    return "\n".join(lines)


def structure_summary(structure: dict) -> dict:
    phases = structure.get("phases", [])
    tasks = structure.get("tasks", []) + [t for p in phases for t in p.get("tasks", [])]
    return {
        "phases": len(phases),
        "packages": sum(len(p.get("packages", [])) for p in phases),
        "tasks": len(tasks),
        "subtasks": sum(len(t.get("subtasks", [])) for t in tasks),
        "milestones": len(structure.get("milestones", [])),
        "days": max(
            [t["offset"] + t.get("duration", 1) for t in tasks]
            + [m.get("offset", 0) for m in structure.get("milestones", [])]
            + [0]
        ),
    }


# ---------------------------------------------------------- custom fields ---


def parse_field_definitions(text: str) -> list[dict]:
    """Baris ``Label | jenis`` (teks, angka, tanggal) menjadi definisi field."""
    fields, keys = [], set()
    for raw in (text or "").splitlines():
        if not raw.strip():
            continue
        label, _, kind = raw.partition("|")
        label, kind = label.strip(), (kind.strip().lower() or "teks")
        if kind not in FIELD_TYPES:
            raise ValidationError(
                f'Jenis field "{kind}" tidak dikenal. Pakai teks, angka, atau tanggal.'
            )
        key = slugify(label).replace("-", "_")[:40]
        if not key or key in keys:
            raise ValidationError(f'Label field "{label}" kosong atau ganda.')
        keys.add(key)
        fields.append({"key": key, "label": label[:80], "type": FIELD_TYPES[kind]})
    if len(fields) > 20:
        raise ValidationError("Maksimal 20 field tambahan.")
    return fields


def field_definitions_text(fields) -> str:
    return "\n".join(f"{f['label']} | {FIELD_TYPE_LABELS.get(f['type'], 'teks')}" for f in fields)


def custom_field_rows(project) -> list[dict]:
    values = project.custom_values or {}
    return [
        {"label": f["label"], "value": values.get(f["key"], ""), "key": f["key"]}
        for f in project.custom_fields or []
    ]


def custom_fields_text(project) -> str:
    return "; ".join(
        f"{r['label']}: {r['value']}" for r in custom_field_rows(project) if r["value"]
    )


# --------------------------------------------------------- project → JSON ---


def project_to_structure(project) -> dict:
    from apps.work.models import Task

    start = project.start_date

    def offset(day):
        return max((day - start).days, 0) if day else 0

    def duration(first, last):
        if first and last:
            return max((last - first).days + 1, 1)
        return DEFAULT_DURATION

    roots = list(
        Task.objects.filter(project=project, parent_task__isnull=True)
        .select_related("work_package")
        .prefetch_related("subtasks")
        .order_by("start_date", "order", "pk")
    )

    def task_json(task):
        return {
            "title": task.title,
            "offset": offset(task.start_date),
            "duration": duration(task.start_date, task.due_date),
            "weight": str(task.weight),
            "method": task.progress_method if task.progress_method != "subtask" else "manual",
            "package": task.work_package.name if task.work_package_id else None,
            "subtasks": [
                {
                    "title": sub.title,
                    "offset": offset(sub.start_date),
                    "duration": duration(sub.start_date, sub.due_date),
                    "weight": str(sub.weight),
                }
                for sub in task.subtasks.all()
            ],
        }

    phases = []
    for phase in project.phases.all():
        tasks = [task_json(t) for t in roots if t.phase_id == phase.pk]
        first = phase.start_date or (
            min(
                (t.start_date for t in roots if t.phase_id == phase.pk and t.start_date),
                default=None,
            )
        )
        phases.append(
            {
                "name": phase.name,
                "offset": offset(first),
                "duration": duration(phase.start_date, phase.end_date),
                "packages": [{"name": wp.name} for wp in phase.work_packages.all()],
                "tasks": tasks,
            }
        )
    return {
        "phases": phases,
        "tasks": [task_json(t) for t in roots if not t.phase_id],
        "milestones": [
            {"name": m.name, "offset": offset(m.date)} for m in project.milestones.all()
        ],
    }


def approval_config_of(project) -> list[dict]:
    return [
        {
            "type": p.approval_type,
            "enabled": p.enabled,
            "mode": p.mode,
            "allow_self": p.allow_self_approval,
        }
        for p in project.approval_policies.all()
    ]


@transaction.atomic
def save_project_as_template(project, name, actor, description=""):
    from .models import ProjectTemplate

    return ProjectTemplate.objects.create(
        workspace=project.workspace,
        name=name,
        description=description,
        project_type=project.project_type,
        structure_config=project_to_structure(project),
        progress_config=project.progress_config or {},
        approval_config=approval_config_of(project),
        custom_fields=project.custom_fields or [],
        weight_mode=project.weight_mode,
        created_by=actor,
    )


# --------------------------------------------------------- JSON → project ---


@transaction.atomic
def apply_template(template, project, actor):
    """Salin isi template ke project baru (tanpa assignee; status To Do)."""
    from apps.governance.services import save_policy

    from .models import ActivityAction
    from .services import record_activity

    structure = template.structure_config or {}
    project.project_type = template.project_type or project.project_type
    project.progress_config = template.progress_config or {}
    project.custom_fields = template.custom_fields or []
    project.weight_mode = template.weight_mode or project.weight_mode
    project.template = template
    project.template_version = template.version
    project.save(
        update_fields=[
            "project_type",
            "progress_config",
            "custom_fields",
            "weight_mode",
            "template",
            "template_version",
            "updated_at",
        ]
    )

    counts = apply_structure(structure, project)
    for policy in template.approval_config or []:
        save_policy(
            project,
            policy["type"],
            enabled=bool(policy.get("enabled")),
            mode=policy.get("mode") or "sequential",
            allow_self=bool(policy.get("allow_self")),
            approvers=[],
            actor=actor,
        )
    record_activity(
        project,
        actor,
        ActivityAction.TEMPLATE_APPLIED,
        f'Rencana dibuat dari template "{template.name}" v{template.version}: '
        f"{counts['phases']} phase, {counts['tasks']} task, {counts['milestones']} milestone.",
    )
    return counts


def apply_structure(structure, project):
    """Buat phase, work package, task, dan milestone dari struktur (offset hari)."""
    from apps.work.models import Task

    from .models import Milestone, Phase, WorkPackage

    start = project.start_date
    first_sequence = (
        Phase.all_objects.filter(project=project)
        .order_by("-sequence")
        .values_list("sequence", flat=True)
        .first()
        or 0
    )

    def day(n):
        return start + timedelta(days=int(n or 0))

    def make_task(item, phase=None, package=None):
        method = item.get("method") if item.get("method") in ("manual", "status") else "manual"
        task = Task.objects.create(
            project=project,
            title=item["title"][:200],
            phase=phase,
            work_package=package,
            start_date=day(item.get("offset")),
            due_date=day(item.get("offset"))
            + timedelta(days=max(int(item.get("duration") or 1), 1) - 1),
            weight=Decimal(str(item.get("weight") or 1)),
            progress_method=method,
        )
        for sub in item.get("subtasks", []):
            Task.objects.create(
                project=project,
                title=sub["title"][:200],
                parent_task=task,
                start_date=day(sub.get("offset")),
                due_date=day(sub.get("offset"))
                + timedelta(days=max(int(sub.get("duration") or 1), 1) - 1),
                weight=Decimal(str(sub.get("weight") or 1)),
            )
        return task

    counts = {"phases": 0, "tasks": 0, "milestones": 0}
    for item in structure.get("tasks", []):
        make_task(item)
        counts["tasks"] += 1
    for index, item in enumerate(structure.get("phases", []), start=1):
        phase_start = day(item.get("offset"))
        phase = Phase.objects.create(
            project=project,
            name=item["name"][:200],
            sequence=first_sequence + index,
            start_date=phase_start,
            end_date=phase_start + timedelta(days=max(int(item.get("duration") or 1), 1) - 1),
        )
        counts["phases"] += 1
        packages = {}
        for seq, wp in enumerate(item.get("packages", []), start=1):
            packages[wp["name"]] = WorkPackage.objects.create(
                project=project, phase=phase, name=wp["name"][:200], sequence=seq
            )
        for task in item.get("tasks", []):
            make_task(task, phase, packages.get(task.get("package")))
            counts["tasks"] += 1
    for item in structure.get("milestones", []):
        Milestone.objects.create(
            project=project, name=item["name"][:200], date=day(item.get("offset"))
        )
        counts["milestones"] += 1
    return counts


def template_signature(template) -> str:
    return re.sub(r"\s+", " ", structure_to_outline(template.structure_config or {})).strip()


PLAIN_PREFIXES = ("-", "+", "*")


def plain_list_structure(text: str) -> dict:
    """'Tempel daftar': satu task per baris, atau outline lengkap bila memakai awalan.

    Tanpa awalan di baris mana pun, setiap baris menjadi task (durasi opsional
    ``| hari``). Bila ada baris berawalan ``-``/``+``/``*``, teks dibaca sebagai
    outline template (baris tanpa awalan = phase).
    """
    lines = [raw.strip().lstrip("•").strip() for raw in (text or "").splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        raise ValidationError("Tulis minimal satu task, satu per baris.")
    if not any(line.startswith(PLAIN_PREFIXES) for line in lines):
        lines = ["- " + line for line in lines]
    structure = outline_to_structure("\n".join(lines))
    for task in structure["tasks"] + [t for p in structure["phases"] for t in p["tasks"]]:
        if not task["title"]:
            raise ValidationError("Judul task tidak boleh kosong.")
        if len(task["title"]) > 200:
            title = task["title"][:40]
            raise ValidationError(f'Judul task terlalu panjang (maks. 200): "{title}…".')
    return structure


def template_spans() -> dict:
    """Durasi (hari) setiap template aktif, untuk mengisi tanggal akhir otomatis."""
    from .models import ProjectTemplate

    return {
        t.pk: structure_summary(t.structure_config or {})["days"]
        for t in ProjectTemplate.objects.filter(is_active=True)
    }
