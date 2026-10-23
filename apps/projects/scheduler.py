"""Optional in-process scheduler for daily progress snapshots (H6).

Disabled by default. When ``SCOPE_SCHEDULER_ENABLED`` is true, the project
``AppConfig.ready()`` starts one daemon thread per process. The thread sleeps
for the configured interval before its first tick, so app initialization never
touches the database. Every worker may run its own thread because the tick is
idempotent per project per calendar day.
"""

import logging
import threading
import time

from django.conf import settings

logger = logging.getLogger(__name__)

THREAD_NAME = "scope-snapshot-scheduler"
DEFAULT_INTERVAL_MINUTES = 60.0

_start_lock = threading.Lock()
_started = False


def interval_seconds() -> float:
    try:
        minutes = float(
            getattr(settings, "SCOPE_SCHEDULER_INTERVAL_MINUTES", DEFAULT_INTERVAL_MINUTES)
        )
    except (TypeError, ValueError):
        minutes = DEFAULT_INTERVAL_MINUTES
    return max(minutes * 60, 1.0)


def tick() -> int:
    """Capture today's snapshot for every project that does not have one."""
    from .services import snapshot_due_projects

    return snapshot_due_projects()


def start_scheduler():
    """Start the daemon thread once per process, if enabled.

    Returns the thread when a new one is started, otherwise ``None``.
    """
    global _started
    if not getattr(settings, "SCOPE_SCHEDULER_ENABLED", False):
        return None
    with _start_lock:
        if _started:
            return None
        _started = True
    thread = threading.Thread(target=_run, name=THREAD_NAME, daemon=True)
    thread.start()
    logger.info("Snapshot scheduler started (interval %.0fs).", interval_seconds())
    return thread


def _run():
    while True:
        time.sleep(interval_seconds())
        try:
            count = tick()
        except Exception:  # a failed tick must not kill the thread
            logger.exception("Snapshot scheduler tick failed; retrying next interval.")
            continue
        if count:
            logger.info("Snapshot scheduler captured %s project snapshot(s).", count)
