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
