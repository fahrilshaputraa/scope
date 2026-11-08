from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

import pytest
import requests
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.identity.models import Role
from apps.identity.roles import assign_roles
from apps.integrations import graph, teams
from apps.integrations.calendar_feed import fold
from apps.integrations.cards import build_card
from apps.integrations.events import collect_scheduled_events
from apps.integrations.models import (
    CalendarFeedToken,
    DeliveryLog,
    DeliveryStatus,
    OutlookConnection,
    OutlookEvent,
    ProjectHealthMark,
    TeamsEvent,
    TeamsWebhook,
)
from apps.integrations.validators import validate_webhook_url
from apps.notifications.models import Notification
from apps.projects.models import LifecycleStatus, Milestone, Project
from apps.work.models import Issue, Priority, Task, TaskComment, TaskStatus

pytestmark = pytest.mark.django_db

HOOK_URL = "https://contoso.webhook.office.com/webhookb2/abc@def/IncomingWebhook/xyz/123"
FLOW_URL = (
    "https://prod-01.westeurope.logic.azure.com:443/workflows/abc/triggers/manual/paths/invoke"
    "?api-version=2016-06-01&sig=secret"
)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(teams, "_sleep", lambda seconds: None)


@pytest.fixture
def data(db):
    today = timezone.localdate()
    admin = User.objects.create_user("admin", password="valid-password", is_staff=True)
    pm = User.objects.create_user("pm", password="valid-password")
    assign_roles(pm, [Role.PROJECT_MANAGER])
    other_pm = User.objects.create_user("otherpm", password="valid-password")
    assign_roles(other_pm, [Role.PROJECT_MANAGER])
    member = User.objects.create_user("member", password="valid-password")
    assign_roles(member, [Role.MEMBER])
    outsider = User.objects.create_user("outsider", password="valid-password")
    assign_roles(outsider, [Role.MEMBER])
    project = Project.objects.create(
        name="Alpha",
        code="ALPHA",
        manager=pm,
        start_date=today - timedelta(days=30),
        target_end_date=today + timedelta(days=60),
        lifecycle_status=LifecycleStatus.IN_PROGRESS,
    )
    project.members.add(member)
    secret = Project.objects.create(
        name="Rahasia",
        code="SECRET",
        manager=other_pm,
        start_date=today - timedelta(days=30),
        target_end_date=today + timedelta(days=60),
        lifecycle_status=LifecycleStatus.IN_PROGRESS,
    )
    task = Task.objects.create(
        project=project,
        title="Desain API",
        assignee=member,
        start_date=today - timedelta(days=5),
        due_date=today - timedelta(days=2),
    )
    secret_task = Task.objects.create(
        project=secret,
        title="Tugas rahasia",
        assignee=member,  # assigned, but this project is the point of the leak test
        start_date=today - timedelta(days=5),
        due_date=today + timedelta(days=3),
    )
    milestone = Milestone.objects.create(
        project=project, name="Go live", date=today + timedelta(days=2)
    )
    secret_milestone = Milestone.objects.create(
        project=secret, name="Peluncuran rahasia", date=today + timedelta(days=2)
    )
    return SimpleNamespace(
        today=today,
        admin=admin,
        pm=pm,
        other_pm=other_pm,
        member=member,
        outsider=outsider,
        project=project,
        secret=secret,
        task=task,
        secret_task=secret_task,
        milestone=milestone,
        secret_milestone=secret_milestone,
    )


def make_hook(project=None, events=None, url=HOOK_URL, name="Channel"):
    hook = TeamsWebhook(
        project=project, name=name, events=events or [e for e, _ in TeamsEvent.choices]
    )
    hook.set_url(url)
    hook.save()
    return hook


def ok_response(code=200, text="1"):
    return SimpleNamespace(status_code=code, text=text)


# ------------------------------------------------------------ validation ---


@pytest.mark.parametrize(
    "url",
    [
        HOOK_URL,
        FLOW_URL,
        "https://default123.ab.environment.api.powerplatform.com/powerautomate/automations/x",
    ],
)
def test_valid_webhook_urls(url):
    assert validate_webhook_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://contoso.webhook.office.com/webhookb2/x",
        "https://evil.example.com/webhookb2/x",
        "https://webhook.office.com.evil.com/x",
        "https://evilwebhook.office.com/x",
        "https://user:pw@contoso.webhook.office.com/x",
        "https://contoso.webhook.office.com:8443/x",
        "https://127.0.0.1/x",
        "https://contoso.webhook.office.com/",
        "ftp://contoso.webhook.office.com/x",
    ],
)
def test_invalid_webhook_urls(url):
    with pytest.raises(ValidationError):
        validate_webhook_url(url)


def test_webhook_url_is_encrypted_and_masked(data):
    hook = make_hook(data.project, url=FLOW_URL)
    hook.refresh_from_db()
    assert "sig=secret" not in hook.url_encrypted
    assert hook.url == FLOW_URL
    assert "secret" not in hook.url_hint and hook.url_hint.startswith("prod-01.")


# ----------------------------------------------------------------- cards ---


def test_card_format():
    payload = build_card(
        "Task terlambat: X",
        text="Lewat 2 hari.",
        facts=[("Status", "To Do"), ("Kosong", "")],
        url="/tasks/1/",
        tone="attention",
        context="Scope · A",
    )
    assert payload["type"] == "message"
    attachment = payload["attachments"][0]
    assert attachment["contentType"] == "application/vnd.microsoft.card.adaptive"
    card = attachment["content"]
    assert card["type"] == "AdaptiveCard"
    assert card["version"] == "1.4"
    assert card["body"][1]["text"] == "Task terlambat: X"
    assert card["body"][1]["color"] == "attention"
    facts = [block for block in card["body"] if block["type"] == "FactSet"][0]["facts"]
    assert facts == [{"title": "Status", "value": "To Do"}]  # empty values dropped
    assert card["actions"][0]["type"] == "Action.OpenUrl"
    assert card["actions"][0]["url"] == "http://testserver/tasks/1/"


def test_card_clips_long_text():
    card = build_card("T", text="x" * 5000)["attachments"][0]["content"]
    assert len(card["body"][2]["text"]) <= 1500


# ------------------------------------------------------- queue & dedupe ---


def test_scheduled_events_are_deduped(data):
    hook = make_hook(data.project)
    first = collect_scheduled_events()
    second = collect_scheduled_events()
    assert first > 0
    assert second == 0
    keys = set(DeliveryLog.objects.filter(webhook=hook).values_list("dedupe_key", flat=True))
    assert f"task_overdue:{data.task.pk}:{data.task.due_date.isoformat()}" in keys
    assert f"milestone_due:{data.milestone.pk}:{data.milestone.date.isoformat()}" in keys
    # The other project's milestone never reaches a project-scoped webhook.
    secret_key = (
        f"milestone_due:{data.secret_milestone.pk}:{data.secret_milestone.date.isoformat()}"
    )
    assert secret_key not in keys


def test_events_respect_webhook_selection(data):
    hook = make_hook(data.project, events=[TeamsEvent.MILESTONE_DUE])
    collect_scheduled_events()
    events = set(DeliveryLog.objects.filter(webhook=hook).values_list("event", flat=True))
    assert events == {TeamsEvent.MILESTONE_DUE}


def test_global_webhook_receives_all_projects(data):
    hook = make_hook(None, events=[TeamsEvent.MILESTONE_DUE])
    collect_scheduled_events()
    assert DeliveryLog.objects.filter(webhook=hook).count() == 2


def test_no_webhooks_means_no_work(data):
    assert collect_scheduled_events() == 0
    assert DeliveryLog.objects.count() == 0


def test_health_change_is_detected_once(data):
    hook = make_hook(data.project, events=[TeamsEvent.HEALTH_CHANGED])
    collect_scheduled_events()  # baseline only
    assert ProjectHealthMark.objects.filter(project=data.project).exists()
    assert DeliveryLog.objects.filter(webhook=hook).count() == 0
    ProjectHealthMark.objects.filter(project=data.project).update(health="on_track")
    with mock.patch.object(Project, "health_status", new="critical"):
        collect_scheduled_events()
        collect_scheduled_events()
    rows = DeliveryLog.objects.filter(webhook=hook, event=TeamsEvent.HEALTH_CHANGED)
    assert rows.count() == 1


@override_settings(TEAMS_DAILY_SUMMARY_HOUR=0)
def test_daily_summary_once_per_day(data):
    hook = make_hook(data.project, events=[TeamsEvent.DAILY_SUMMARY])
    collect_scheduled_events()
    collect_scheduled_events()
    assert DeliveryLog.objects.filter(webhook=hook, event=TeamsEvent.DAILY_SUMMARY).count() == 1


@override_settings(TEAMS_NOTIFICATIONS_ENABLED=False)
def test_disabled_flag_stops_queueing(data):
    make_hook(data.project)
    assert collect_scheduled_events() == 0


def test_blocked_task_via_notifications_single_message(data, django_capture_on_commit_callbacks):
    hook = make_hook(data.project, events=[TeamsEvent.TASK_BLOCKED])
    data.task.status = TaskStatus.BLOCKED
    data.task.blocked_reason = "Menunggu akses server"
    data.task.save()
    with django_capture_on_commit_callbacks(execute=True):
        for user in (data.pm, data.member):  # one Notification per recipient
            Notification.objects.create(
                recipient=user,
                verb="task.status",
                target_type="task",
                target_id=data.task.pk,
                title="Status",
                dedupe_key=f"task.status:task:{data.task.pk}:status:blocked:2026-11-08:{user.pk}",
            )
    rows = DeliveryLog.objects.filter(webhook=hook, event=TeamsEvent.TASK_BLOCKED)
    assert rows.count() == 1
    assert "Menunggu akses server" in str(rows.get().payload)


def test_critical_issue_signal_and_scan_do_not_duplicate(data, django_capture_on_commit_callbacks):
    hook = make_hook(data.project, events=[TeamsEvent.ISSUE_CRITICAL])
    issue = Issue.objects.create(project=data.project, title="DB down", severity=Priority.CRITICAL)
    with django_capture_on_commit_callbacks(execute=True):
        Notification.objects.create(
            recipient=data.pm,
            verb="issue.created",
            target_type="issue",
            target_id=issue.pk,
            title="Issue",
            dedupe_key=f"issue.created:issue:{issue.pk}:created:{issue.pk}:{data.pm.pk}",
        )
    collect_scheduled_events()
    assert DeliveryLog.objects.filter(webhook=hook, event=TeamsEvent.ISSUE_CRITICAL).count() == 1


def test_mention_is_queued(data, django_capture_on_commit_callbacks):
    from apps.work.models import Mention

    hook = make_hook(data.project, events=[TeamsEvent.MENTION])
    comment = TaskComment.objects.create(
        task=data.task, author=data.pm, content="<p>@member cek</p>"
    )
    with django_capture_on_commit_callbacks(execute=True):
        Mention.objects.create(task_comment=comment, user=data.member)
    row = DeliveryLog.objects.get(webhook=hook, event=TeamsEvent.MENTION)
    assert "<p>" not in str(row.payload)


# --------------------------------------------------------------- deliver ---


def test_deliver_marks_sent_and_is_idempotent(data):
    hook = make_hook(data.project)
    collect_scheduled_events()
    pending = DeliveryLog.objects.filter(status=DeliveryStatus.PENDING).count()
    session = mock.Mock()
    session.post.return_value = ok_response(202, "")
    counts = teams.deliver_pending(session=session)
    assert counts["sent"] == pending
    assert session.post.call_count == pending
    url, kwargs = session.post.call_args.args[0], session.post.call_args.kwargs
    assert url == HOOK_URL
    assert kwargs["timeout"] > 0
    assert kwargs["json"]["type"] == "message"
    assert not DeliveryLog.objects.filter(sent_at__isnull=True).exists()
    hook.refresh_from_db()
    assert hook.last_status == "sent"
    # Second run sends nothing.
    session.post.reset_mock()
    assert teams.deliver_pending(session=session)["sent"] == 0
    session.post.assert_not_called()


def test_transient_error_retries_then_fails(data):
    hook = make_hook(data.project)
    teams.enqueue_test(hook, data.pm)
    session = mock.Mock()
    session.post.side_effect = requests.Timeout()
    counts = teams.deliver_pending(session=session)
    assert counts["retry"] == 1
    assert session.post.call_count == 2  # one inline retry
    row = DeliveryLog.objects.get()
    assert row.status == DeliveryStatus.PENDING and row.next_attempt_at is not None
    # Not due yet: nothing is sent.
    assert teams.deliver_pending(session=session)["retry"] == 0
    for _ in range(teams.MAX_ATTEMPTS):
        DeliveryLog.objects.update(next_attempt_at=timezone.now() - timedelta(minutes=1))
        teams.deliver_pending(session=session)
    row.refresh_from_db()
    assert row.status == DeliveryStatus.FAILED
    assert row.attempts == teams.MAX_ATTEMPTS
    hook.refresh_from_db()
    assert hook.last_status == "failed" and "Koneksi gagal" in hook.last_error


def test_permanent_error_fails_immediately(data):
    hook = make_hook(data.project)
    teams.enqueue_test(hook, data.pm)
    session = mock.Mock()
    session.post.return_value = ok_response(400, "Bad payload")
    teams.deliver_pending(session=session)
    assert session.post.call_count == 1
    assert DeliveryLog.objects.get().status == DeliveryStatus.FAILED


def test_inactive_webhook_is_skipped(data):
    hook = make_hook(data.project)
    teams.enqueue_test(hook, data.pm)
    TeamsWebhook.objects.filter(pk=hook.pk).update(is_active=False)
    session = mock.Mock()
    assert teams.deliver_pending(session=session)["skipped"] == 1
    session.post.assert_not_called()


def test_command_is_idempotent(data):
    make_hook(data.project)
    with mock.patch.object(teams.requests, "post", return_value=ok_response()) as post:
        call_command("send_teams_notifications")
        sent = post.call_count
        call_command("send_teams_notifications")
    assert sent > 0
    assert post.call_count == sent


def test_scheduler_tick_runs_teams(data):
    from apps.projects.scheduler import tick

    make_hook(data.project)
    with mock.patch.object(teams.requests, "post", return_value=ok_response()) as post:
        tick()
    assert post.called
    assert DeliveryLog.objects.filter(status=DeliveryStatus.SENT).exists()


# ---------------------------------------------------------- views & perms ---


def test_index_renders_empty_state(client, data):
    client.force_login(data.pm)
    response = client.get(reverse("integrations:index"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Belum ada webhook Teams" in content
    assert "Langganan kalender" in content


def test_pm_creates_project_webhook_and_url_is_hidden(client, data):
    client.force_login(data.pm)
    response = client.post(
        reverse("integrations:webhook_create"),
        {
            "name": "Channel Alpha",
            "scope": str(data.project.pk),
            "url": FLOW_URL,
            "events": [TeamsEvent.TASK_OVERDUE, TeamsEvent.MENTION],
            "is_active": "on",
        },
    )
    assert response.status_code == 302
    hook = TeamsWebhook.objects.get()
    assert hook.project == data.project and hook.url == FLOW_URL
    page = client.get(reverse("integrations:index")).content.decode()
    assert "sig=secret" not in page
    edit = client.get(reverse("integrations:webhook_edit", args=[hook.pk])).content.decode()
    assert "sig=secret" not in edit


def test_invalid_url_rejected_in_form(client, data):
    client.force_login(data.pm)
    response = client.post(
        reverse("integrations:webhook_create"),
        {
            "name": "X",
            "scope": str(data.project.pk),
            "url": "https://evil.example.com/x",
            "events": [TeamsEvent.TASK_OVERDUE],
        },
    )
    assert response.status_code == 200
    assert TeamsWebhook.objects.count() == 0


def test_pm_cannot_create_global_or_other_project_webhook(client, data):
    client.force_login(data.pm)
    for scope in ("global", str(data.secret.pk)):
        response = client.post(
            reverse("integrations:webhook_create"),
            {"name": "X", "scope": scope, "url": HOOK_URL, "events": [TeamsEvent.TASK_OVERDUE]},
        )
        assert response.status_code == 200
    assert TeamsWebhook.objects.count() == 0


def test_member_cannot_configure_teams(client, data):
    client.force_login(data.member)
    assert client.get(reverse("integrations:webhook_create")).status_code == 403
    hook = make_hook(data.project)
    assert client.post(reverse("integrations:webhook_test", args=[hook.pk])).status_code == 403
    assert client.post(reverse("integrations:webhook_delete", args=[hook.pk])).status_code == 403


def test_other_pm_cannot_touch_webhook(client, data):
    hook = make_hook(data.project)
    client.force_login(data.other_pm)
    assert client.get(reverse("integrations:webhook_edit", args=[hook.pk])).status_code == 403
    global_hook = make_hook(None)
    client.force_login(data.pm)
    assert (
        client.post(reverse("integrations:webhook_test", args=[global_hook.pk])).status_code == 403
    )


def test_admin_creates_global_webhook(client, data):
    client.force_login(data.admin)
    response = client.post(
        reverse("integrations:webhook_create"),
        {
            "name": "Portfolio",
            "scope": "global",
            "url": HOOK_URL,
            "events": [TeamsEvent.DAILY_SUMMARY],
            "is_active": "on",
        },
    )
    assert response.status_code == 302
    assert TeamsWebhook.objects.get().project is None


def test_send_test_only_queues(client, data):
    hook = make_hook(data.project)
    client.force_login(data.pm)
    with mock.patch.object(teams.requests, "post") as post:
        response = client.post(reverse("integrations:webhook_test", args=[hook.pk]))
    assert response.status_code == 302
    post.assert_not_called()  # never sends inside the web request
    row = DeliveryLog.objects.get()
    assert row.event == TeamsEvent.TEST and row.status == DeliveryStatus.PENDING


def test_edit_keeps_url_when_blank(client, data):
    hook = make_hook(data.project)
    client.force_login(data.pm)
    client.post(
        reverse("integrations:webhook_edit", args=[hook.pk]),
        {
            "name": "Baru",
            "scope": str(data.project.pk),
            "url": "",
            "events": [TeamsEvent.TASK_OVERDUE],
            "is_active": "on",
        },
    )
    hook.refresh_from_db()
    assert hook.name == "Baru" and hook.url == HOOK_URL


# ------------------------------------------------------------ ICS feeds ---


def test_feed_contents_and_access_scope(client, data):
    feed = CalendarFeedToken.objects.create(user=data.member)
    data.secret_task.assignee = data.outsider
    data.secret_task.save()
    response = client.get(reverse("integrations:user_feed", args=[feed.token]))
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/calendar")
    body = response.content.decode()
    assert body.startswith("BEGIN:VCALENDAR\r\n")
    assert body.rstrip().endswith("END:VCALENDAR")
    assert f"UID:scope-task-{data.task.pk}@testserver" in body
    assert f"DTSTART;VALUE=DATE:{data.task.due_date.strftime('%Y%m%d')}" in body
    assert "Desain API (ALPHA)" in body
    assert f"UID:scope-milestone-{data.milestone.pk}@" in body
    assert "Rahasia" not in body and "SECRET" not in body
    assert "Peluncuran rahasia" not in body
    feed.refresh_from_db()
    assert feed.last_accessed_at is not None


def test_feed_includes_owned_issue(client, data):
    issue = Issue.objects.create(
        project=data.project, title="Lisensi", owner=data.member, due_date=data.today
    )
    feed = CalendarFeedToken.objects.create(user=data.member)
    body = client.get(reverse("integrations:user_feed", args=[feed.token])).content.decode()
    assert f"UID:scope-issue-{issue.pk}@" in body


def test_feed_wrong_token_404(client, data):
    CalendarFeedToken.objects.create(user=data.member)
    assert client.get(reverse("integrations:user_feed", args=["nope"])).status_code == 404


def test_feed_inactive_user_404(client, data):
    feed = CalendarFeedToken.objects.create(user=data.member)
    User.objects.filter(pk=data.member.pk).update(is_active=False)
    assert client.get(reverse("integrations:user_feed", args=[feed.token])).status_code == 404


def test_feed_reset_invalidates_old_token(client, data):
    feed = CalendarFeedToken.objects.create(user=data.member)
    old = feed.token
    client.force_login(data.member)
    assert client.post(reverse("integrations:feed_reset")).status_code == 302
    feed.refresh_from_db()
    assert feed.token != old
    client.logout()
    assert client.get(reverse("integrations:user_feed", args=[old])).status_code == 404
    assert client.get(reverse("integrations:user_feed", args=[feed.token])).status_code == 200


def test_project_calendar_requires_access(client, data):
    client.force_login(data.member)
    response = client.get(reverse("integrations:project_calendar", args=[data.project.pk]))
    assert response.status_code == 200
    assert "attachment" in response["Content-Disposition"]
    assert "Go live" in response.content.decode()
    client.force_login(data.outsider)
    assert (
        client.get(reverse("integrations:project_calendar", args=[data.project.pk])).status_code
        == 404
    )


def test_ics_escaping_and_folding():
    from apps.integrations.calendar_feed import escape_text

    assert escape_text("a,b;c\\d\ne") == "a\\,b\\;c\\\\d\\ne"
    line = "SUMMARY:" + "é" * 80
    folded = fold(line)
    assert all(len(part.encode()) <= 75 for part in folded.split("\r\n"))
    assert folded.replace("\r\n ", "") == line


# ---------------------------------------------------------------- Graph ---


def test_graph_not_configured_message(client, data):
    client.force_login(data.member)
    response = client.post(
        reverse("integrations:outlook_add", args=["task", data.task.pk]), follow=True
    )
    assert response.status_code == 200
    assert "belum dikonfigurasi" in response.content.decode()
    assert OutlookEvent.objects.count() == 0


def test_graph_add_hidden_target_404(client, data):
    client.force_login(data.outsider)
    response = client.post(reverse("integrations:outlook_add", args=["task", data.task.pk]))
    assert response.status_code == 404


@override_settings(
    AZURE_ENABLED=True, OUTLOOK_GRAPH_ENABLED=True, AZURE_CLIENT_ID="cid", AZURE_CLIENT_SECRET="sec"
)
def test_graph_service_creates_then_updates_event(data):
    connection = OutlookConnection(user=data.member, scope="Calendars.ReadWrite offline_access")
    connection.set_tokens("access-1", "refresh-1")
    connection.expires_at = timezone.now() + timedelta(hours=1)
    connection.save()
    session = mock.Mock()
    session.request.return_value = mock.Mock(
        status_code=201, json=lambda: {"id": "evt-1", "webLink": "https://outlook/evt-1"}
    )
    service = graph.GraphCalendarService(data.member, session=session)
    event = service.add_milestone(data.milestone)
    method, url = session.request.call_args.args
    kwargs = session.request.call_args.kwargs
    assert method == "POST" and url.endswith("/me/events")
    assert kwargs["headers"]["Authorization"] == "Bearer access-1"
    assert kwargs["json"]["isAllDay"] is True
    assert kwargs["json"]["start"]["dateTime"].startswith(data.milestone.date.isoformat())
    assert event.graph_event_id == "evt-1"
    session.request.return_value = mock.Mock(status_code=200, json=lambda: {"webLink": "x"})
    service.add_milestone(data.milestone)
    assert session.request.call_args.args[0] == "PATCH"
    assert OutlookEvent.objects.count() == 1


@override_settings(
    AZURE_ENABLED=True, OUTLOOK_GRAPH_ENABLED=True, AZURE_CLIENT_ID="cid", AZURE_CLIENT_SECRET="sec"
)
def test_graph_refreshes_expired_token(data):
    connection = OutlookConnection(user=data.member, scope="Calendars.ReadWrite")
    connection.set_tokens("old", "refresh-1")
    connection.expires_at = timezone.now() - timedelta(minutes=1)
    connection.save()
    session = mock.Mock()
    session.post.return_value = mock.Mock(
        status_code=200,
        json=lambda: {"access_token": "new", "refresh_token": "refresh-2", "expires_in": 3600},
    )
    session.request.return_value = mock.Mock(status_code=201, json=lambda: {"id": "e"})
    graph.GraphCalendarService(data.member, session=session).add_task(data.task)
    assert session.post.call_args.kwargs["data"]["grant_type"] == "refresh_token"
    assert session.request.call_args.kwargs["headers"]["Authorization"] == "Bearer new"
    connection.refresh_from_db()
    assert connection.refresh_token == "refresh-2"


@override_settings(AZURE_ENABLED=True, OUTLOOK_GRAPH_ENABLED=True)
def test_graph_not_connected_and_forbidden(data):
    with pytest.raises(graph.GraphNotConnected):
        graph.GraphCalendarService(data.member)
    connection = OutlookConnection(user=data.member, scope="Calendars.ReadWrite")
    connection.set_tokens("a", "r")
    connection.expires_at = timezone.now() + timedelta(hours=1)
    connection.save()
    session = mock.Mock()
    session.request.return_value = mock.Mock(status_code=403)
    with pytest.raises(graph.GraphError, match="Calendars.ReadWrite"):
        graph.GraphCalendarService(data.member, session=session).add_task(data.task)


@override_settings(AZURE_ENABLED=True, OUTLOOK_GRAPH_ENABLED=True)
def test_save_token_requires_calendar_scope(data):
    with pytest.raises(graph.GraphError):
        graph.save_token(data.member, {"access_token": "a", "scope": "openid profile"})
    connection = graph.save_token(
        data.member,
        {
            "access_token": "a",
            "refresh_token": "r",
            "scope": "Calendars.ReadWrite",
            "expires_in": 60,
        },
    )
    assert connection.has_calendar_scope
    assert "a" != connection.access_token_encrypted


@override_settings(AZURE_ENABLED=True, OUTLOOK_GRAPH_ENABLED=True)
def test_index_renders_configured_state(client, data):
    hook = make_hook(data.project, url=FLOW_URL)
    teams.enqueue_test(hook, data.pm)
    connection = OutlookConnection(user=data.pm, scope="Calendars.ReadWrite")
    connection.set_tokens("a", "r")
    connection.save()
    Task.objects.create(project=data.project, title="Rilis", assignee=data.pm, due_date=data.today)
    client.force_login(data.pm)
    content = client.get(reverse("integrations:index")).content.decode()
    assert "Channel" in content and "Kirim tes" in content
    assert "Pesan tes dari Scope" in content
    assert "Tambahkan ke kalender Outlook" in content
    assert "sig=secret" not in content
