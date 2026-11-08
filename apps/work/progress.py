"""Weighted work progress shared by activities, phases and projects."""

from decimal import Decimal


def weighted_progress(tasks, *, empty=Decimal("0.00")):
    total = Decimal("0")
    weighted = Decimal("0")
    for task in tasks:
        total += task.weight
        weighted += task.display_progress * task.weight
    if total <= 0:
        return empty
    return (weighted / total).quantize(Decimal("0.01"))


def status_progress(status, config=None, current=Decimal("0")):
    """Progress metode status-based (PRD §11.1 Method B).

    Blocked mempertahankan progress terakhir; In Progress dan In Review dapat diatur
    per project lewat ``Project.progress_config``.
    """
    from .models import STATUS_PROGRESS_DEFAULTS

    if status == "blocked":
        return current
    values = {**STATUS_PROGRESS_DEFAULTS, **{k: v for k, v in (config or {}).items() if v != ""}}
    return Decimal(str(values.get(status, current)))
