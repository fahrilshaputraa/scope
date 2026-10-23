"""Field-level revision capture, diff formatting, and restore (roadmap E5)."""

import re
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.signals import m2m_changed, post_save, pre_save
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.html import strip_tags

from apps.work.models import (
    TASK_STATUS_LABELS,
    Issue,
    IssueStatus,
    Priority,
    Task,
)

from .models import (
    Milestone,
    MilestoneStatus,
    Phase,
    Project,
    ProjectStatus,
    Revision,
    RevisionAction,
    RevisionEntity,
    Risk,
)


@dataclass(frozen=True)
class FieldSpec:
    label: str
    kind: str = "text"
    attname: str | None = None


REVISION_FIELDS: dict[str, dict[str, FieldSpec]] = {
    RevisionEntity.PROJECT: {
        "name": FieldSpec("Nama"),
        "description": FieldSpec("Deskripsi", "rich"),
        "team": FieldSpec("Tim"),
        "start_date": FieldSpec("Tanggal mulai", "date"),
        "target_end_date": FieldSpec("Target selesai", "date"),
        "actual_end_date": FieldSpec("Selesai aktual", "date"),
        "status": FieldSpec("Status", "choice"),
        "current_phase": FieldSpec("Phase aktif", "phase", "current_phase_id"),
        "progress_override": FieldSpec("Progress manual", "percent"),
        "manager": FieldSpec("Manager", "user", "manager_id"),
        "members": FieldSpec("Anggota", "users"),
        "archived_at": FieldSpec("Status arsip", "datetime"),
    },
    RevisionEntity.TASK: {
        "title": FieldSpec("Judul"),
        "description": FieldSpec("Deskripsi", "rich"),
        "start_date": FieldSpec("Tanggal mulai", "date"),
        "due_date": FieldSpec("Tenggat", "date"),
        "baseline_start_date": FieldSpec("Baseline mulai", "date"),
        "baseline_end_date": FieldSpec("Baseline selesai", "date"),
        "status": FieldSpec("Status", "choice"),
        "progress": FieldSpec("Progress", "percent"),
        "weight": FieldSpec("Bobot", "decimal"),
        "priority": FieldSpec("Prioritas", "choice"),
        "assignee": FieldSpec("PIC", "user", "assignee_id"),
        "collaborators": FieldSpec("Rekan", "users"),
        "phase": FieldSpec("Phase", "phase", "phase_id"),
        "dependencies": FieldSpec("Dependensi", "tasks"),
        "archived_at": FieldSpec("Status arsip", "datetime"),
    },
    RevisionEntity.MILESTONE: {
        "name": FieldSpec("Nama"),
        "description": FieldSpec("Deskripsi", "rich"),
        "date": FieldSpec("Tanggal", "date"),
        "status": FieldSpec("Status", "choice"),
        "owner": FieldSpec("Pemilik", "user", "owner_id"),
    },
    RevisionEntity.ISSUE: {
        "title": FieldSpec("Judul"),
        "description": FieldSpec("Deskripsi", "rich"),
        "severity": FieldSpec("Severitas", "choice"),
        "priority": FieldSpec("Prioritas", "choice"),
        "status": FieldSpec("Status", "choice"),
        "owner": FieldSpec("Pemilik", "user", "owner_id"),
        "due_date": FieldSpec("Tenggat", "date"),
        "resolution": FieldSpec("Resolusi", "rich"),
        "archived_at": FieldSpec("Status arsip", "datetime"),
    },
    RevisionEntity.RISK: {
        "title": FieldSpec("Judul"),
        "severity": FieldSpec("Severitas", "choice"),
        "status": FieldSpec("Status", "choice"),
        "owner": FieldSpec("Pemilik", "user", "owner_id"),
        "due_date": FieldSpec("Tenggat", "date"),
        "mitigation": FieldSpec("Mitigasi", "rich"),
    },
}

ENTITY_MODELS = {
    RevisionEntity.PROJECT: Project,
    RevisionEntity.TASK: Task,
    RevisionEntity.MILESTONE: Milestone,
    RevisionEntity.ISSUE: Issue,
    RevisionEntity.RISK: Risk,
}

ENTITY_LABELS = {
    RevisionEntity.PROJECT: "Project",
    RevisionEntity.TASK: "Task",
    RevisionEntity.MILESTONE: "Milestone",
    RevisionEntity.ISSUE: "Issue",
    RevisionEntity.RISK: "Risiko",
}

_PRIORITY_LABELS = {
    Priority.CRITICAL: "Kritis",
    Priority.HIGH: "Tinggi",
    Priority.MEDIUM: "Sedang",
    Priority.LOW: "Rendah",
}

CHOICE_LABELS = {
    (RevisionEntity.PROJECT, "status"): {
        ProjectStatus.PLANNING: "Perencanaan",
        ProjectStatus.ON_TRACK: "Sesuai jalur",
        ProjectStatus.AT_RISK: "Berisiko",
        ProjectStatus.DELAYED: "Terlambat",
        ProjectStatus.COMPLETED: "Selesai",
        ProjectStatus.ON_HOLD: "Ditahan",
        ProjectStatus.CANCELLED: "Dibatalkan",
    },
    (RevisionEntity.TASK, "status"): TASK_STATUS_LABELS,
    (RevisionEntity.TASK, "priority"): _PRIORITY_LABELS,
    (RevisionEntity.MILESTONE, "status"): {
        MilestoneStatus.UPCOMING: "Akan datang",
        MilestoneStatus.IN_PROGRESS: "Berjalan",
        MilestoneStatus.COMPLETED: "Selesai",
        MilestoneStatus.DELAYED: "Terlambat",
    },
    (RevisionEntity.ISSUE, "status"): {
        IssueStatus.OPEN: "Terbuka",
        IssueStatus.IN_PROGRESS: "Sedang ditangani",
        IssueStatus.BLOCKED: "Terhambat",
        IssueStatus.RESOLVED: "Diselesaikan",
        IssueStatus.CLOSED: "Ditutup",
    },
    (RevisionEntity.ISSUE, "severity"): _PRIORITY_LABELS,
    (RevisionEntity.ISSUE, "priority"): _PRIORITY_LABELS,
    (RevisionEntity.RISK, "severity"): _PRIORITY_LABELS,
    (RevisionEntity.RISK, "status"): {
        "open": "Terbuka",
        "mitigated": "Termitigasi",
        "closed": "Ditutup",
    },
}

_M2M_SPECS = {
    Project.members.through: (RevisionEntity.PROJECT, "members"),
    Task.collaborators.through: (RevisionEntity.TASK, "collaborators"),
    Task.dependencies.through: (RevisionEntity.TASK, "dependencies"),
}

_ENTITY_BY_MODEL = {model: entity for entity, model in ENTITY_MODELS.items()}

_M2M_KINDS = ("users", "tasks")

_state = threading.local()


class RestoreError(Exception):
    """Raised when a revision cannot be restored safely."""


# ------------------------------------------------------------ request state ---


def set_request_state(user=None):
    actor = user if getattr(user, "is_authenticated", False) else None
    _state.revision = {"actor": actor, "seen": {}, "action": None}


def clear_request_state():
    _state.revision = None


def _current_state():
    return getattr(_state, "revision", None)


@contextmanager
def revision_context(action, actor=None):
    """Force the action (and optionally actor) for revisions recorded in this block."""
    created = _current_state() is None
    if created:
        set_request_state(actor)
    state = _current_state()
    previous = (state["action"], state["actor"])
    state["action"] = action
    if actor is not None:
        state["actor"] = actor
    try:
        yield
    finally:
        state["action"], state["actor"] = previous
        if created:
            clear_request_state()


# ---------------------------------------------------------------- capturing ---


def _normalize(value, kind=None):
    if kind in ("percent", "decimal"):
        # Normalise numeric scale so 20, Decimal("20") and Decimal("20.00") compare equal.
        try:
            return format(Decimal(str(value)).normalize(), "f")
        except (InvalidOperation, TypeError, ValueError):
            return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    return value


def _instance_values(instance, entity):
    values = {}
    for name, spec in REVISION_FIELDS[entity].items():
        if spec.kind in _M2M_KINDS:
            continue
        value = getattr(instance, spec.attname or name)
        values[name] = _normalize(value, spec.kind)
    return values


def _stored_values(instance, entity):
    manager = ENTITY_MODELS[entity]._base_manager
    mapping = {
        spec.attname or name: (name, spec)
        for name, spec in REVISION_FIELDS[entity].items()
        if spec.kind not in _M2M_KINDS
    }
    row = manager.filter(pk=instance.pk).values(*mapping.keys()).first() or {}
    return {
        name: _normalize(row.get(attname), spec.kind)
        for attname, (name, spec) in mapping.items()
    }


def _m2m_values(instance, field):
    return sorted(getattr(instance, field).values_list("pk", flat=True))


def _object_repr(instance, entity):
    if entity == RevisionEntity.PROJECT:
        text = f'Project "{instance.code}"'
    else:
        title = getattr(instance, "title", None) or getattr(instance, "name", "")
        text = f'{ENTITY_LABELS[entity]} "{title}"'
    return text[:200]


def _summary(instance, entity, action):
    label = _object_repr(instance, entity)
    if action == RevisionAction.CREATED:
        return f"{label} dibuat."[:300]
    if action == RevisionAction.RESTORED:
        return f"{label} dipulihkan dari riwayat."[:300]
    return f"{label} diperbarui."[:300]


def _record_revision(instance, entity, changes, action):
    state = _current_state()
    if action == RevisionAction.CREATED:
        final_action = RevisionAction.CREATED
    else:
        forced = state["action"] if state else None
        final_action = forced or action
    actor = state["actor"] if state else None
    project = instance if entity == RevisionEntity.PROJECT else instance.project
    if project is None:
        return None

    seen = state["seen"] if state else {}
    key = (entity, instance.pk)
    existing_id = seen.get(key)
    if existing_id:
        revision = Revision.objects.filter(pk=existing_id).first()
        if revision is not None:
            merged = {name: dict(change) for name, change in (revision.changes or {}).items()}
            for name, change in changes.items():
                if name in merged:
                    merged[name]["new"] = change["new"]
                else:
                    merged[name] = change
            revision.changes = merged
            revision.summary = _summary(instance, entity, revision.action)
            revision.save(update_fields=["changes", "summary"])
            return revision

    revision = Revision.objects.create(
        project=project,
        entity=entity,
        object_id=instance.pk,
        object_repr=_object_repr(instance, entity),
        actor=actor,
        action=final_action,
        changes=changes,
        summary=_summary(instance, entity, final_action),
    )
    if state is not None:
        state["seen"][key] = revision.pk
    return revision


def _capture_before_save(sender, instance, **kwargs):
    entity = _ENTITY_BY_MODEL.get(sender)
    if entity is None:
        return
    if instance._state.adding:
        instance._revision_before = {}
    else:
        instance._revision_before = _stored_values(instance, entity)


def _capture_after_save(sender, instance, created=False, raw=False, **kwargs):
    entity = _ENTITY_BY_MODEL.get(sender)
    if entity is None or raw:
        return
    if created:
        _record_revision(instance, entity, {}, RevisionAction.CREATED)
        instance._revision_before = {}
        return
    before = getattr(instance, "_revision_before", None)
    if before is None:
        before = _stored_values(instance, entity)
    after = _instance_values(instance, entity)
    changes = {}
    for name, spec in REVISION_FIELDS[entity].items():
        if spec.kind in _M2M_KINDS:
            continue
        old, new = before.get(name), after.get(name)
        if old != new:
            changes[name] = {"old": old, "new": new}
    instance._revision_before = {}
    if changes:
        _record_revision(instance, entity, changes, RevisionAction.UPDATED)


def _capture_m2m_before(sender, instance, action, reverse, **kwargs):
    if reverse or not action.startswith("pre_"):
        return
    spec = _M2M_SPECS.get(sender)
    if spec is None or not instance.pk:
        return
    entity, field = spec
    before = getattr(instance, "_revision_m2m_before", None) or {}
    before[field] = _m2m_values(instance, field)
    instance._revision_m2m_before = before


def _capture_m2m_after(sender, instance, action, reverse, **kwargs):
    if reverse or action.startswith("pre_") or not instance.pk:
        return
    spec = _M2M_SPECS.get(sender)
    if spec is None:
        return
    entity, field = spec
    before_map = getattr(instance, "_revision_m2m_before", None) or {}
    before = before_map.pop(field, None)
    instance._revision_m2m_before = before_map
    after = _m2m_values(instance, field)
    if before is None or before == after:
        return
    _record_revision(
        instance, entity, {field: {"old": before, "new": after}}, RevisionAction.UPDATED
    )


def connect_signals():
    for model in ENTITY_MODELS.values():
        pre_save.connect(
            _capture_before_save, sender=model, dispatch_uid=f"revision-pre-{model._meta.label}"
        )
        post_save.connect(
            _capture_after_save, sender=model, dispatch_uid=f"revision-post-{model._meta.label}"
        )
    for through in _M2M_SPECS:
        m2m_changed.connect(
            _capture_m2m_before,
            sender=through,
            dispatch_uid=f"revision-m2m-pre-{through._meta.label}",
        )
        m2m_changed.connect(
            _capture_m2m_after,
            sender=through,
            dispatch_uid=f"revision-m2m-post-{through._meta.label}",
        )


connect_signals()


# ---------------------------------------------------------------- formatting ---


def _format_decimal(value, suffix=""):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return f"{value}{suffix}"
    text = f"{number.quantize(Decimal('0.01')):f}".rstrip("0").rstrip(".")
    return f"{text}{suffix}"


def _collapse(text):
    return re.sub(r"\s+", " ", text).strip()


def _format_value(spec, value, entity, field, users, phases, tasks):
    if value is None or value == "":
        return "—"
    if spec.kind == "date":
        parsed = parse_date(value) if isinstance(value, str) else value
        return parsed.strftime("%d %b %Y") if parsed else str(value)
    if spec.kind == "datetime":
        parsed = parse_datetime(value) if isinstance(value, str) else value
        return parsed.strftime("%d %b %Y %H:%M") if parsed else str(value)
    if spec.kind == "user":
        user = users.get(value)
        if user is None:
            return f"Pengguna #{value}"
        return _collapse(user.get_full_name() or user.username)
    if spec.kind == "users":
        names = []
        for user_id in value or []:
            user = users.get(user_id)
            name = _collapse(user.get_full_name() or user.username) if user else f"#{user_id}"
            names.append(name)
        return ", ".join(names) if names else "—"
    if spec.kind == "phase":
        phase = phases.get(value)
        return phase.name if phase else f"Phase #{value}"
    if spec.kind == "tasks":
        titles = [tasks[task_id].title for task_id in value or [] if task_id in tasks]
        return ", ".join(titles) if titles else "—"
    if spec.kind == "percent":
        return _format_decimal(value, "%")
    if spec.kind == "decimal":
        return _format_decimal(value)
    if spec.kind == "choice":
        return CHOICE_LABELS.get((entity, field), {}).get(value, str(value))
    if spec.kind == "rich":
        return _collapse(strip_tags(str(value)))
    return _collapse(str(value)) or "—"


def _truncate(text, limit=140):
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def decorate_revisions(revisions):
    """Attach display labels and formatted diff rows for the history template."""
    revisions = list(revisions)
    user_ids, phase_ids, task_ids = set(), set(), set()
    for revision in revisions:
        fields = REVISION_FIELDS.get(revision.entity, {})
        for name, change in (revision.changes or {}).items():
            spec = fields.get(name)
            if spec is None:
                continue
            for side in ("old", "new"):
                value = change.get(side)
                if value is None:
                    continue
                if spec.kind == "user":
                    user_ids.add(value)
                elif spec.kind == "users":
                    user_ids.update(value)
                elif spec.kind == "phase":
                    phase_ids.add(value)
                elif spec.kind == "tasks":
                    task_ids.update(value)
    users = User.objects.in_bulk(user_ids)
    phases = Phase.all_objects.in_bulk(phase_ids)
    tasks = Task.all_objects.in_bulk(task_ids)

    for revision in revisions:
        revision.entity_label = ENTITY_LABELS.get(revision.entity, revision.entity)
        revision.action_label = revision.get_action_display()
        fields = REVISION_FIELDS.get(revision.entity, {})
        rows = []
        for name, change in (revision.changes or {}).items():
            spec = fields.get(name)
            if spec is None:
                continue
            old = _format_value(
                spec, change.get("old"), revision.entity, name, users, phases, tasks
            )
            new = _format_value(
                spec, change.get("new"), revision.entity, name, users, phases, tasks
            )
            rows.append(
                {
                    "label": spec.label,
                    "old": _truncate(old),
                    "new": _truncate(new),
                    "old_full": old,
                    "new_full": new,
                    "long": len(old) > 140 or len(new) > 140,
                }
            )
        revision.change_rows = rows
    return revisions


# ------------------------------------------------------------------ restore ---


def _deserialize(spec, value):
    if value is None:
        return None
    if spec.kind == "date":
        return parse_date(value)
    if spec.kind == "datetime":
        return parse_datetime(value)
    if spec.kind in ("percent", "decimal"):
        return Decimal(str(value))
    if spec.kind in ("user", "phase"):
        return int(value)
    return value


def _validate_refs(entity, specs, plain, project):
    for name, value in plain.items():
        spec = specs[name]
        if value is None:
            continue
        if spec.kind == "user" and not User.objects.filter(pk=value).exists():
            raise RestoreError(f"Pengguna untuk {spec.label} sudah tidak tersedia.")
        if spec.kind == "phase" and not Phase.all_objects.filter(
            pk=value, project_id=project.pk
        ).exists():
            raise RestoreError(f"{spec.label} pada riwayat ini tidak lagi valid untuk project.")


def _dependency_cycle(task, dependency_ids):
    stack = [dep for dep in dependency_ids if dep is not None]
    seen = set()
    while stack:
        current = stack.pop()
        if current == task.pk:
            return True
        if current in seen:
            continue
        seen.add(current)
        stack.extend(
            dep
            for dep in Task._base_manager.filter(pk=current).values_list(
                "dependencies__pk", flat=True
            )
            if dep is not None
        )
    return False


def _resolve_m2m(entity, obj, specs, pending):
    resolved = {}
    for name, ids in pending.items():
        spec = specs[name]
        if spec.kind == "users":
            resolved[name] = list(User.objects.filter(pk__in=ids))
        elif spec.kind == "tasks":
            ids = list(ids or [])
            tasks = list(Task._base_manager.filter(pk__in=ids, project_id=obj.project_id))
            if len({task.pk for task in tasks}) != len(set(ids)):
                raise RestoreError(
                    f"{spec.label} pada riwayat ini sudah tidak tersedia di project."
                )
            if obj.pk in ids:
                raise RestoreError(f"{spec.label} tidak boleh merujuk task itu sendiri.")
            if name == "dependencies" and _dependency_cycle(obj, ids):
                raise RestoreError("Pemulihan ditolak: dependensi akan membentuk siklus.")
            resolved[name] = tasks
    return resolved


def restore_revision(revision, actor=None):
    """Apply the old side of every changed field, then record a restored revision."""
    entity = revision.entity
    model = ENTITY_MODELS.get(entity)
    specs = REVISION_FIELDS.get(entity)
    if model is None or specs is None:
        raise RestoreError("Jenis data pada riwayat ini tidak dikenal.")
    obj = model._base_manager.filter(
        pk=revision.object_id, project_id=revision.project_id
    ).first()
    if obj is None:
        raise RestoreError("Data yang dirujuk riwayat ini sudah tidak tersedia.")

    plain, pending = {}, {}
    for name, change in (revision.changes or {}).items():
        spec = specs.get(name)
        if spec is None:
            continue
        value = _deserialize(spec, change.get("old"))
        if spec.kind in _M2M_KINDS:
            pending[name] = value or []
        else:
            plain[name] = value
    if not plain and not pending:
        raise RestoreError("Riwayat ini tidak memiliki perubahan yang bisa dipulihkan.")

    _validate_refs(entity, specs, plain, revision.project)
    m2m = _resolve_m2m(entity, obj, specs, pending)

    try:
        with transaction.atomic():
            for name, value in plain.items():
                spec = specs[name]
                setattr(obj, spec.attname or name, value)
            obj.full_clean()
            with revision_context(RevisionAction.RESTORED, actor):
                obj.save()
                for name, value in m2m.items():
                    getattr(obj, name).set(value)
                state = _current_state()
                if state is not None and (entity, obj.pk) not in state["seen"]:
                    _record_revision(obj, entity, {}, RevisionAction.RESTORED)
    except ValidationError as exc:
        raise RestoreError("Pemulihan ditolak: " + " ".join(exc.messages)) from exc
    except IntegrityError as exc:
        raise RestoreError(
            "Pemulihan ditolak karena melanggar batasan data (mis. duplikat atau relasi)."
        ) from exc
    return obj
