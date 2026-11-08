import logging
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from apps.identity.permissions import visible_projects
from apps.projects.models import Milestone, MilestoneStatus
from apps.work.models import Task, TaskStatus

from . import graph
from .calendar_feed import project_feed, user_feed
from .forms import TeamsWebhookForm
from .models import CalendarFeedToken, DeliveryLog, OutlookConnection, OutlookEvent, TeamsWebhook
from .permissions import (
    can_configure_teams,
    can_manage_global,
    can_manage_webhook,
    manageable_projects,
)
from .teams import enqueue_test, teams_enabled

logger = logging.getLogger(__name__)


def _feed_token(user) -> CalendarFeedToken:
    token, _ = CalendarFeedToken.objects.get_or_create(user=user)
    return token


def _visible_webhooks(user):
    project_ids = list(manageable_projects(user).values_list("pk", flat=True))
    hooks = TeamsWebhook.objects.select_related("project")
    if can_manage_global(user):
        return hooks.filter(project__isnull=True) | hooks.filter(project_id__in=project_ids)
    return hooks.filter(project_id__in=project_ids)


def _safe_next(request, default):
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return default


@login_required
def index(request):
    user = request.user
    feed = _feed_token(user)
    feed_url = request.build_absolute_uri(reverse("integrations:user_feed", args=[feed.token]))
    hooks = list(_visible_webhooks(user).order_by("project__name", "name"))
    today = timezone.localdate()
    horizon = today + timedelta(days=30)
    projects = visible_projects(user)
    connection = OutlookConnection.objects.filter(user=user).first()
    upcoming_tasks = list(
        Task.objects.filter(
            project__in=projects, assignee=user, due_date__gte=today, due_date__lte=horizon
        )
        .exclude(status=TaskStatus.DONE)
        .select_related("project")
        .order_by("due_date")[:8]
    )
    upcoming_milestones = list(
        Milestone.objects.filter(project__in=projects, date__gte=today, date__lte=horizon)
        .exclude(status=MilestoneStatus.COMPLETED)
        .select_related("project")
        .order_by("date")[:8]
    )
    added = set(OutlookEvent.objects.filter(user=user).values_list("target_type", "target_id"))
    for task in upcoming_tasks:
        task.in_outlook = ("task", task.pk) in added
    for milestone in upcoming_milestones:
        milestone.in_outlook = ("milestone", milestone.pk) in added
    logs = (
        DeliveryLog.objects.filter(webhook__in=[hook.pk for hook in hooks])
        .select_related("webhook", "webhook__project")
        .order_by("-created_at")[:10]
    )
    return render(
        request,
        "integrations/index.html",
        {
            "active_settings": "integrations",
            "feed_url": feed_url,
            "webcal_url": "webcal://" + feed_url.split("://", 1)[-1],
            "feed": feed,
            "calendar_projects": projects.order_by("name"),
            "can_configure_teams": can_configure_teams(user),
            "can_manage_global": can_manage_global(user),
            "teams_enabled": teams_enabled(),
            "webhooks": hooks,
            "logs": logs,
            "graph_enabled": graph.graph_enabled(),
            "azure_enabled": getattr(settings, "AZURE_ENABLED", False),
            "outlook": connection,
            "upcoming_tasks": upcoming_tasks,
            "upcoming_milestones": upcoming_milestones,
        },
    )


# -------------------------------------------------------------- Teams ---


def _form_kwargs(user):
    return {
        "projects": list(manageable_projects(user).order_by("name")),
        "allow_global": can_manage_global(user),
    }


@login_required
def webhook_create(request):
    if not can_configure_teams(request.user):
        raise PermissionDenied
    initial = {}
    if request.GET.get("project"):
        initial["scope"] = request.GET["project"]
    form = TeamsWebhookForm(
        request.POST or None, initial=initial or None, **_form_kwargs(request.user)
    )
    if request.method == "POST" and form.is_valid():
        webhook = form.save(request.user)
        messages.success(request, f'Webhook "{webhook.name}" disimpan. Kirim tes untuk memastikan.')
        return redirect("integrations:index")
    return render(
        request,
        "integrations/webhook_form.html",
        {"form": form, "webhook": None, "active_settings": "integrations"},
    )


def _webhook_or_403(request, pk):
    webhook = get_object_or_404(TeamsWebhook.objects.select_related("project"), pk=pk)
    if not can_manage_webhook(request.user, webhook):
        raise PermissionDenied
    return webhook


@login_required
def webhook_edit(request, pk):
    webhook = _webhook_or_403(request, pk)
    form = TeamsWebhookForm(request.POST or None, instance=webhook, **_form_kwargs(request.user))
    if request.method == "POST" and form.is_valid():
        form.save(request.user)
        messages.success(request, "Webhook diperbarui.")
        return redirect("integrations:index")
    return render(
        request,
        "integrations/webhook_form.html",
        {"form": form, "webhook": webhook, "active_settings": "integrations"},
    )


@login_required
@require_POST
def webhook_delete(request, pk):
    webhook = _webhook_or_403(request, pk)
    name = webhook.name
    webhook.delete()
    messages.success(request, f'Webhook "{name}" dihapus.')
    return redirect("integrations:index")


@login_required
@require_POST
def webhook_test(request, pk):
    webhook = _webhook_or_403(request, pk)
    if not webhook.is_active:
        messages.error(request, "Aktifkan webhook terlebih dahulu sebelum mengirim tes.")
        return redirect("integrations:index")
    enqueue_test(webhook, request.user)
    messages.success(
        request,
        "Pesan tes masuk antrean dan dikirim pada putaran scheduler berikutnya "
        "(atau jalankan send_teams_notifications).",
    )
    return redirect("integrations:index")


# ----------------------------------------------------------- Calendar ---


@login_required
@require_POST
def feed_reset(request):
    _feed_token(request.user).reset()
    messages.success(
        request,
        "Tautan kalender diganti. Langganan lama berhenti bekerja; tambahkan tautan baru "
        "di Outlook atau Google Calendar.",
    )
    return redirect("integrations:index")


def _ics_response(body, filename, inline=True):
    response = HttpResponse(body, content_type="text/calendar; charset=utf-8")
    disposition = "inline" if inline else "attachment"
    response["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    response["Cache-Control"] = "private, max-age=300"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


@never_cache
@require_GET
def user_feed_view(request, token):
    feed = (
        CalendarFeedToken.objects.select_related("user").filter(token=token).first()
        if token
        else None
    )
    if feed is None or not feed.user.is_active:
        raise Http404
    now = timezone.now()
    if feed.last_accessed_at is None or now - feed.last_accessed_at > timedelta(hours=1):
        CalendarFeedToken.objects.filter(pk=feed.pk).update(last_accessed_at=now)
    return _ics_response(user_feed(feed.user), "scope-jadwal.ics")


@login_required
@require_GET
def project_calendar(request, pk):
    project = visible_projects(request.user).filter(pk=pk).first()
    if project is None:
        raise Http404
    filename = f"scope-{project.code.lower()}.ics"
    return _ics_response(project_feed(project, request.user), filename, inline=False)


@login_required
@require_GET
def project_calendar_pick(request):
    pk = request.GET.get("project", "")
    if not pk.isdigit():
        messages.error(request, "Pilih project yang ingin diunduh.")
        return redirect("integrations:index")
    return redirect("integrations:project_calendar", pk=int(pk))


# ------------------------------------------------------------ Outlook ---


@login_required
def outlook_connect(request):
    try:
        graph.require_enabled()
    except graph.GraphError as exc:
        messages.error(request, str(exc))
        return redirect("integrations:index")
    redirect_uri = request.build_absolute_uri(reverse("integrations:outlook_callback"))
    return graph.connect_client().authorize_redirect(request, redirect_uri)


@login_required
def outlook_callback(request):
    try:
        graph.require_enabled()
        if request.GET.get("error"):
            raise graph.GraphError(
                "Microsoft membatalkan persetujuan: "
                f"{request.GET.get('error_description') or request.GET['error']}"[:300]
            )
        client = graph.connect_client()
        try:
            token = client.authorize_access_token(request)
        except Exception as exc:  # Authlib raises several error types
            logger.warning("Outlook token exchange failed: %s", exc.__class__.__name__)
            raise graph.GraphError("Gagal menukar kode otorisasi Microsoft. Coba lagi.") from exc
        claims = token.get("userinfo") or {}
        email = claims.get("email") or claims.get("preferred_username") or ""
        graph.save_token(request.user, token, email=email)
    except graph.GraphError as exc:
        messages.error(request, str(exc))
        return redirect("integrations:index")
    messages.success(request, "Kalender Outlook terhubung.")
    return redirect("integrations:index")


@login_required
@require_POST
def outlook_disconnect(request):
    OutlookConnection.objects.filter(user=request.user).delete()
    messages.success(
        request,
        "Koneksi Outlook diputus. Event yang sudah dibuat tetap ada di kalender Anda.",
    )
    return redirect("integrations:index")


@login_required
@require_POST
def outlook_add(request, kind, pk):
    projects = visible_projects(request.user)
    if kind == "task":
        target = Task.objects.filter(pk=pk, project__in=projects).select_related("project").first()
    elif kind == "milestone":
        target = (
            Milestone.objects.filter(pk=pk, project__in=projects).select_related("project").first()
        )
    else:
        target = None
    if target is None:
        raise Http404
    destination = _safe_next(request, reverse("integrations:index"))
    try:
        service = graph.GraphCalendarService(request.user)
        if kind == "task":
            service.add_task(target)
        else:
            service.add_milestone(target)
    except graph.GraphError as exc:
        messages.error(request, str(exc))
        return redirect(destination)
    messages.success(request, "Ditambahkan ke kalender Outlook.")
    return redirect(destination)
