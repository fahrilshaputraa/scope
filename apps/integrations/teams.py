"""Teams queue: enqueue (cheap, safe inside a request) and deliver (scheduler only).

``enqueue`` only writes ``DeliveryLog`` rows. ``deliver_pending`` performs the
HTTP calls and is run by ``send_teams_notifications`` or the scheduler tick,
never by a web view.
"""

import logging
import time
from datetime import timedelta

import requests
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone

from .cards import card_title
from .models import DeliveryLog, DeliveryStatus, TeamsEvent, TeamsWebhook
from .validators import is_allowed_host

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
#: Retries inside one delivery attempt for transient errors (timeout, 5xx, 429).
INLINE_RETRIES = 1
RETRY_BACKOFF = timedelta(minutes=5)
STALE_SENDING = timedelta(minutes=15)
BATCH_SIZE = 200

_sleep = time.sleep  # patched in tests


def teams_enabled() -> bool:
    return bool(getattr(settings, "TEAMS_NOTIFICATIONS_ENABLED", True))


def webhooks_for(event: str, project=None):
    """Active webhooks subscribed to ``event`` for ``project`` (plus global ones)."""
    qs = TeamsWebhook.objects.filter(is_active=True)
    if project is None:
        qs = qs.filter(project__isnull=True)
    else:
        qs = qs.filter(Q(project=project) | Q(project__isnull=True))
    # JSON "contains" is not portable to SQLite; webhook counts are tiny.
    return [hook for hook in qs if hook.wants(event)]


def enqueue_for(webhook, event: str, dedupe_key: str, payload: dict):
    """Queue one message for one webhook; returns the new row or ``None`` if a duplicate."""
    key = dedupe_key[:255]
    if DeliveryLog.objects.filter(webhook=webhook, dedupe_key=key).exists():
        return None
    try:
        with transaction.atomic():
            return DeliveryLog.objects.create(
                webhook=webhook,
                event=event,
                dedupe_key=key,
                title=(card_title(payload) or event)[:200],
                payload=payload,
            )
    except IntegrityError:  # concurrent enqueue of the same key
        return None


def enqueue(event: str, project, dedupe_key: str, payload_factory) -> list:
    """Queue ``event`` to every matching webhook. ``payload_factory()`` builds the card once."""
    if not teams_enabled():
        return []
    hooks = webhooks_for(event, project)
    if not hooks:
        return []
    payload = payload_factory()
    created = []
    for hook in hooks:
        row = enqueue_for(hook, event, dedupe_key, payload)
        if row is not None:
            created.append(row)
    return created


def post_card(url: str, payload: dict, *, timeout=None, session=None):
    """POST once (plus one inline retry for transient errors). Returns ``(ok, code, error)``."""
    timeout = timeout or float(getattr(settings, "TEAMS_REQUEST_TIMEOUT", 10))
    http = session or requests
    code = None
    error = ""
    for attempt in range(INLINE_RETRIES + 1):
        try:
            response = http.post(url, json=payload, timeout=timeout)
        except requests.RequestException as exc:
            code, error = None, f"Koneksi gagal: {exc.__class__.__name__}"
        else:
            code = response.status_code
            if 200 <= code < 300:
                body = (getattr(response, "text", "") or "")[:200]
                # Legacy connectors answer 200 with an error string on throttling.
                if "http error" in body.lower():
                    return False, code, f"Teams menolak pesan: {body}"
                return True, code, ""
            error = f"HTTP {code}"
            if code not in (408, 429) and code < 500:
                return False, code, error  # permanent: bad URL or rejected card
        if attempt < INLINE_RETRIES:
            _sleep(1)
    return False, code, error


def _claim(row) -> bool:
    """Atomically move a row to SENDING so parallel workers never double-send."""
    return bool(
        DeliveryLog.objects.filter(
            pk=row.pk, status=row.status, attempts=row.attempts, sent_at__isnull=True
        ).update(status=DeliveryStatus.SENDING, attempts=F("attempts") + 1)
    )


def _due_rows(now):
    stale = now - STALE_SENDING
    return (
        DeliveryLog.objects.filter(sent_at__isnull=True)
        .filter(
            Q(status=DeliveryStatus.PENDING, next_attempt_at__isnull=True)
            | Q(status=DeliveryStatus.PENDING, next_attempt_at__lte=now)
            | Q(status=DeliveryStatus.SENDING, updated_at__lt=stale)
        )
        .select_related("webhook")
        .order_by("created_at", "id")[:BATCH_SIZE]
    )


def _finish(row, webhook, ok, code, error, now):
    attempts = row.attempts + 1
    if ok:
        status = DeliveryStatus.SENT
        next_at = None
    elif attempts >= MAX_ATTEMPTS or (code is not None and code < 500 and code not in (408, 429)):
        status = DeliveryStatus.FAILED
        next_at = None
    else:
        status = DeliveryStatus.PENDING
        next_at = now + RETRY_BACKOFF * attempts
    DeliveryLog.objects.filter(pk=row.pk).update(
        status=status,
        response_code=code,
        error=error[:500],
        next_attempt_at=next_at,
        sent_at=now if ok else None,
        updated_at=now,
    )
    TeamsWebhook.objects.filter(pk=webhook.pk).update(
        last_delivery_at=now,
        last_status=DeliveryStatus.SENT if ok else DeliveryStatus.FAILED,
        last_error="" if ok else error[:500],
    )
    return status


def deliver_pending(*, session=None) -> dict:
    """Send queued messages. Safe to run repeatedly and from several processes."""
    counts = {"sent": 0, "failed": 0, "retry": 0, "skipped": 0}
    now = timezone.now()
    for row in list(_due_rows(now)):
        if not _claim(row):
            continue
        webhook = row.webhook
        url = webhook.url
        if not webhook.is_active or not url or not _host_ok(url):
            reason = "Webhook nonaktif." if not webhook.is_active else "URL webhook tidak valid."
            DeliveryLog.objects.filter(pk=row.pk).update(
                status=DeliveryStatus.SKIPPED, error=reason, updated_at=now
            )
            counts["skipped"] += 1
            continue
        ok, code, error = post_card(url, row.payload, session=session)
        status = _finish(row, webhook, ok, code, error, now)
        if status == DeliveryStatus.SENT:
            counts["sent"] += 1
        elif status == DeliveryStatus.FAILED:
            counts["failed"] += 1
            logger.warning("Teams delivery %s failed: %s", row.pk, error)
        else:
            counts["retry"] += 1
    return counts


def _host_ok(url: str) -> bool:
    from urllib.parse import urlsplit

    return is_allowed_host(urlsplit(url).hostname or "")


def enqueue_test(webhook, user) -> DeliveryLog:
    """Queue a test card; delivered by the next ``send_teams_notifications`` run."""
    from apps.notifications.services import user_display

    from .cards import build_card

    stamp = timezone.now()
    payload = build_card(
        "Pesan tes dari Scope",
        text=(f'Webhook "{webhook.name}" terhubung. Dikirim atas permintaan {user_display(user)}.'),
        facts=[
            ("Cakupan", webhook.project.name if webhook.project_id else "Global (semua project)"),
            ("Waktu antre", timezone.localtime(stamp).strftime("%d-%m-%Y %H:%M")),
        ],
        url="/integrations/",
        tone="accent",
    )
    return DeliveryLog.objects.create(
        webhook=webhook,
        event=TeamsEvent.TEST,
        dedupe_key=f"test:{stamp.isoformat()}",
        title="Pesan tes dari Scope",
        payload=payload,
    )
