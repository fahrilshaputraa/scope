"""Bobot sibling (PRD §11.2, BR-WGT-001 sampai 006).

Satu kelompok sibling adalah task utama satu project (sumber actual progress) atau
detail activity dari satu induk. Bobot ditampilkan sebagai persentase kelompok dan
total kelompok harus 100%. Mode ``auto`` membagi rata setiap kali isi kelompok berubah.
"""

from decimal import ROUND_DOWN, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

HUNDRED = Decimal("100")
CENT = Decimal("0.01")


def group_tasks(project, parent_id=None):
    from .models import Task

    return list(
        Task.objects.filter(project=project, parent_task_id=parent_id).order_by("order", "pk")
    )


def group_total(tasks) -> Decimal:
    return sum((t.weight for t in tasks), Decimal("0"))


def is_complete(tasks) -> bool:
    return not tasks or abs(group_total(tasks) - HUNDRED) < CENT


def equal_weights(count: int) -> list[Decimal]:
    if count <= 0:
        return []
    base = (HUNDRED / count).quantize(CENT, rounding=ROUND_DOWN)
    weights = [base] * count
    weights[-1] = HUNDRED - base * (count - 1)
    return weights


def proportional_weights(values) -> list[Decimal]:
    values = [Decimal(v) for v in values]
    total = sum(values, Decimal("0"))
    if total <= 0:
        return equal_weights(len(values))
    weights = [(v / total * HUNDRED).quantize(CENT, rounding=ROUND_DOWN) for v in values]
    weights[-1] = HUNDRED - sum(weights[:-1], Decimal("0"))
    return weights


def _change_problem(project):
    from apps.governance.changes import major_change_problem

    return major_change_problem(project, "task", ["weight"])


@transaction.atomic
def set_weights(project, tasks, weights, actor=None, note="", *, check_change=True):
    """Simpan bobot satu kelompok tanpa revisi per task; catat ringkasan di activity log."""
    from apps.projects.models import ActivityAction
    from apps.projects.services import record_activity

    from .models import Task

    if check_change:
        problem = _change_problem(project)
        if problem:
            raise ValidationError(problem)
    changed = [t for t, w in zip(tasks, weights, strict=True) if t.weight != w]
    for task, weight in zip(tasks, weights, strict=True):
        task.weight = weight
    if changed:
        Task.objects.bulk_update(changed, ["weight"])
        if actor is not None or note:
            record_activity(
                project,
                actor,
                ActivityAction.WEIGHTS_UPDATED,
                note or f"Bobot {len(tasks)} pekerjaan diperbarui (total 100%).",
            )
    return changed


def equalize(project, parent_id=None, actor=None):
    tasks = group_tasks(project, parent_id)
    return set_weights(
        project, tasks, equal_weights(len(tasks)), actor, "Bobot dibagi rata (total 100%)."
    )


def normalize(project, parent_id=None, actor=None):
    tasks = group_tasks(project, parent_id)
    return set_weights(
        project,
        tasks,
        proportional_weights([t.weight for t in tasks]),
        actor,
        "Bobot dinormalisasi ke total 100% sesuai proporsi lama.",
    )


def validate_manual(weights) -> None:
    total = sum((Decimal(w) for w in weights), Decimal("0"))
    if abs(total - HUNDRED) >= CENT:
        raise ValidationError(f"Total bobot harus 100%, sekarang {total.normalize():f}%.")


def rebalance_if_auto(project, parent_id=None):
    """Mode otomatis: bagi rata ulang kelompok yang isinya berubah (BR-WGT-001)."""
    from apps.projects.models import WeightMode

    if project is None or project.weight_mode != WeightMode.AUTO:
        return
    tasks = group_tasks(project, parent_id)
    set_weights(project, tasks, equal_weights(len(tasks)), check_change=False)


def groups(project) -> list[dict]:
    """Kelompok sibling beserta total dan persentase, untuk halaman Struktur."""
    from .models import Task

    tasks = list(Task.objects.filter(project=project).order_by("order", "pk"))
    by_parent = {}
    for task in tasks:
        by_parent.setdefault(task.parent_task_id, []).append(task)
    titles = {t.pk: t.title for t in tasks}
    result = []
    for parent_id, members in by_parent.items():
        total = group_total(members)
        result.append(
            {
                "parent_id": parent_id,
                "label": "Task utama project" if parent_id is None else titles.get(parent_id),
                "tasks": [
                    {
                        "task": t,
                        "share": (t.weight / total * HUNDRED).quantize(CENT) if total else None,
                    }
                    for t in members
                ],
                "total": total,
                "complete": is_complete(members),
            }
        )
    result.sort(key=lambda g: (g["parent_id"] is not None, g["label"] or ""))
    return result
