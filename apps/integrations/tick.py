"""Teams work for the internal scheduler tick (``apps.projects.scheduler``)."""

from .events import collect_scheduled_events
from .teams import deliver_pending


def run_teams_tick() -> dict:
    queued = collect_scheduled_events()
    counts = deliver_pending()
    counts["queued"] = queued
    return counts
