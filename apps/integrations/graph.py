"""Optional Microsoft Graph calendar integration (delegated Calendars.ReadWrite).

Isolated on purpose: views only call ``connect_client``, ``save_token`` and
``GraphCalendarService``. Tests replace ``session`` with a fake; nothing here
runs unless ``graph_enabled()``.

Azure app registration needs (delegated, Microsoft Graph):
``openid``, ``profile``, ``email``, ``offline_access``, ``Calendars.ReadWrite``
and the redirect URI ``<SITE_URL>/integrations/outlook/callback/``.
"""

from datetime import UTC, datetime, timedelta
from functools import lru_cache

import requests
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from apps.notifications.delivery import absolute_url

from .models import OutlookConnection, OutlookEvent

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPES = "openid profile email offline_access Calendars.ReadWrite"
REQUIRED_SCOPE = "Calendars.ReadWrite"
TIMEOUT = 10


class GraphError(Exception):
    """Failure with a message that is safe to show to the user (Indonesian)."""


class GraphNotConfigured(GraphError):
    pass


class GraphNotConnected(GraphError):
    pass


def graph_enabled() -> bool:
    return bool(
        getattr(settings, "AZURE_ENABLED", False)
        and getattr(settings, "OUTLOOK_GRAPH_ENABLED", False)
    )


def require_enabled() -> None:
    if not getattr(settings, "AZURE_ENABLED", False):
        raise GraphNotConfigured(
            "Integrasi Outlook belum dikonfigurasi: isi AZURE_CLIENT_ID dan "
            "AZURE_CLIENT_SECRET terlebih dahulu."
        )
    if not getattr(settings, "OUTLOOK_GRAPH_ENABLED", False):
        raise GraphNotConfigured(
            "Integrasi kalender Outlook dimatikan. Admin perlu mengatur "
            "OUTLOOK_GRAPH_ENABLED=true setelah permission Calendars.ReadWrite disetujui."
        )


def token_url() -> str:
    tenant = getattr(settings, "AZURE_TENANT_ID", "") or "common"
    return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"


@lru_cache(maxsize=1)
def connect_client():
    """Authlib client for the separate Graph consent flow (keeps SSO scopes minimal)."""
    from authlib.integrations.django_client import OAuth

    oauth = OAuth()
    oauth.register(
        name="entra_graph",
        client_id=settings.AZURE_CLIENT_ID,
        client_secret=settings.AZURE_CLIENT_SECRET,
        server_metadata_url=settings.AZURE_METADATA_URL,
        client_kwargs={"scope": GRAPH_SCOPES, "code_challenge_method": "S256"},
    )
    return oauth.create_client("entra_graph")


def _expiry(token: dict):
    seconds = token.get("expires_in")
    if seconds:
        return timezone.now() + timedelta(seconds=int(seconds) - 60)
    expires_at = token.get("expires_at")
    if expires_at:
        return datetime.fromtimestamp(int(expires_at), tz=UTC)
    return timezone.now() + timedelta(minutes=50)


def save_token(user, token: dict, email: str = "") -> OutlookConnection:
    scope = token.get("scope") or ""
    if isinstance(scope, (list, tuple)):
        scope = " ".join(scope)
    if REQUIRED_SCOPE.lower() not in scope.lower():
        raise GraphError(
            "Izin Calendars.ReadWrite tidak diberikan. Minta admin tenant menyetujui "
            "permission tersebut, lalu hubungkan ulang."
        )
    connection, _ = OutlookConnection.objects.get_or_create(user=user)
    connection.set_tokens(token.get("access_token", ""), token.get("refresh_token", ""))
    connection.expires_at = _expiry(token)
    connection.scope = scope[:500]
    if email:
        connection.account_email = email[:254]
    connection.save()
    return connection


class GraphCalendarService:
    """Creates or updates all-day Outlook events for tasks and milestones."""

    def __init__(self, user, session=None):
        require_enabled()
        self.user = user
        self.session = session or requests.Session()
        self.connection = OutlookConnection.objects.filter(user=user).first()
        if self.connection is None or not self.connection.access_token_encrypted:
            raise GraphNotConnected(
                "Kalender Outlook belum terhubung. Buka Pengaturan → Integrasi lalu pilih "
                "Hubungkan Outlook."
            )

    # -- tokens --------------------------------------------------------------
    def _refresh(self) -> None:
        refresh_token = self.connection.refresh_token
        if not refresh_token:
            raise GraphNotConnected("Sesi Outlook kedaluwarsa. Hubungkan ulang kalender Outlook.")
        try:
            response = self.session.post(
                token_url(),
                data={
                    "grant_type": "refresh_token",
                    "client_id": settings.AZURE_CLIENT_ID,
                    "client_secret": settings.AZURE_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                    "scope": GRAPH_SCOPES,
                },
                timeout=TIMEOUT,
            )
        except requests.RequestException as exc:
            raise GraphError("Tidak dapat menghubungi Microsoft. Coba lagi nanti.") from exc
        if response.status_code != 200:
            raise GraphNotConnected("Sesi Outlook kedaluwarsa. Hubungkan ulang kalender Outlook.")
        token = response.json()
        self.connection.set_tokens(token.get("access_token", ""), token.get("refresh_token", ""))
        self.connection.expires_at = _expiry(token)
        if token.get("scope"):
            self.connection.scope = token["scope"][:500]
        self.connection.save()

    def _token(self) -> str:
        expires = self.connection.expires_at
        if expires is None or expires <= timezone.now():
            self._refresh()
        return self.connection.access_token

    def _request(self, method, path, payload):
        headers = {"Authorization": f"Bearer {self._token()}", "Content-Type": "application/json"}
        try:
            response = self.session.request(
                method, f"{GRAPH_BASE}{path}", json=payload, headers=headers, timeout=TIMEOUT
            )
        except requests.RequestException as exc:
            raise GraphError("Tidak dapat menghubungi Microsoft Graph. Coba lagi nanti.") from exc
        if response.status_code == 401:
            raise GraphNotConnected("Akses Outlook ditolak. Hubungkan ulang kalender Outlook.")
        if response.status_code == 403:
            raise GraphError(
                "Microsoft menolak akses kalender (403). Pastikan permission "
                "Calendars.ReadWrite sudah disetujui admin tenant."
            )
        return response

    # -- events --------------------------------------------------------------
    @staticmethod
    def event_payload(subject, day, body, url):
        end = day + timedelta(days=1)
        return {
            "subject": subject[:255],
            "isAllDay": True,
            "start": {"dateTime": f"{day.isoformat()}T00:00:00", "timeZone": settings.TIME_ZONE},
            "end": {"dateTime": f"{end.isoformat()}T00:00:00", "timeZone": settings.TIME_ZONE},
            "showAs": "free",
            "isReminderOn": True,
            "reminderMinutesBeforeStart": 1080,
            "body": {
                "contentType": "text",
                "content": f"{body}\n\nBuka di Scope: {absolute_url(url)}",
            },
            "categories": ["Scope"],
        }

    def upsert(self, target_type, target_id, payload) -> OutlookEvent:
        existing = OutlookEvent.objects.filter(
            user=self.user, target_type=target_type, target_id=target_id
        ).first()
        if existing is not None:
            response = self._request("PATCH", f"/me/events/{existing.graph_event_id}", payload)
            if response.status_code == 200:
                existing.web_link = response.json().get("webLink", existing.web_link)[:1000]
                existing.save(update_fields=["web_link", "updated_at"])
                return existing
            if response.status_code != 404:
                raise GraphError(f"Gagal memperbarui event Outlook (HTTP {response.status_code}).")
            existing.delete()  # removed in Outlook; create a fresh one
        response = self._request("POST", "/me/events", payload)
        if response.status_code not in (200, 201):
            raise GraphError(f"Gagal membuat event Outlook (HTTP {response.status_code}).")
        data = response.json()
        return OutlookEvent.objects.create(
            user=self.user,
            target_type=target_type,
            target_id=target_id,
            graph_event_id=data["id"],
            web_link=(data.get("webLink") or "")[:1000],
        )

    def add_task(self, task) -> OutlookEvent:
        if not task.due_date:
            raise GraphError("Task belum memiliki target selesai.")
        payload = self.event_payload(
            f"{task.title} ({task.project.code})",
            task.due_date,
            f"Target selesai task di {task.project.name}.",
            reverse("work:task_detail", args=[task.pk]),
        )
        return self.upsert(OutlookEvent.Target.TASK, task.pk, payload)

    def add_milestone(self, milestone) -> OutlookEvent:
        payload = self.event_payload(
            f"Milestone: {milestone.name} ({milestone.project.code})",
            milestone.date,
            f"Milestone project {milestone.project.name}.",
            reverse("projects:project_milestones", args=[milestone.project_id]),
        )
        return self.upsert(OutlookEvent.Target.MILESTONE, milestone.pk, payload)
