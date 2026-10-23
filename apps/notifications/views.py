from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.identity.permissions import visible_projects
from apps.projects.pagination import paginate
from apps.work.models import Task

from .models import Notification, SubscriptionTarget
from .subscriptions import unwatch, watch


def _redirect_back(request: HttpRequest, fallback: str | None = None) -> HttpResponse:
    default = fallback or reverse("notifications:center")
    target = request.POST.get("next") or default
    if not url_has_allowed_host_and_scheme(
        target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        target = default
    return redirect(target)


def _project_for_watch(request: HttpRequest, pk: int):
    return get_object_or_404(visible_projects(request.user), pk=pk)


def _task_for_watch(request: HttpRequest, pk: int):
    return get_object_or_404(
        Task.objects.select_related("project"),
        pk=pk,
        project__in=visible_projects(request.user),
    )


@login_required
@require_POST
def watch_project(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_for_watch(request, pk)
    watch(request.user, SubscriptionTarget.PROJECT, project.pk)
    messages.success(request, f"Anda mengikuti project {project.code}.")
    return _redirect_back(request, reverse("projects:project_detail", args=[project.pk]))


@login_required
@require_POST
def unwatch_project(request: HttpRequest, pk: int) -> HttpResponse:
    project = _project_for_watch(request, pk)
    unwatch(request.user, SubscriptionTarget.PROJECT, project.pk)
    messages.success(request, f"Anda berhenti mengikuti project {project.code}.")
    return _redirect_back(request, reverse("projects:project_detail", args=[project.pk]))


@login_required
@require_POST
def watch_task(request: HttpRequest, pk: int) -> HttpResponse:
    task = _task_for_watch(request, pk)
    watch(request.user, SubscriptionTarget.TASK, task.pk)
    messages.success(request, "Anda mengikuti task ini.")
    return _redirect_back(request, reverse("work:task_detail", args=[task.pk]))


@login_required
@require_POST
def unwatch_task(request: HttpRequest, pk: int) -> HttpResponse:
    task = _task_for_watch(request, pk)
    unwatch(request.user, SubscriptionTarget.TASK, task.pk)
    messages.success(request, "Anda berhenti mengikuti task ini.")
    return _redirect_back(request, reverse("work:task_detail", args=[task.pk]))


@login_required
def center(request: HttpRequest) -> HttpResponse:
    current = request.GET.get("filter", "all")
    if current not in ("all", "unread"):
        current = "all"
    notifications = Notification.objects.filter(recipient=request.user).select_related("actor")
    if current == "unread":
        notifications = notifications.filter(read_at__isnull=True)
    page_obj = paginate(request, notifications, 25)
    return render(
        request,
        "notifications/center.html",
        {
            "notifications": page_obj,
            "page_obj": page_obj,
            "filter": current,
            "unread_count": Notification.objects.filter(
                recipient=request.user, read_at__isnull=True
            ).count(),
        },
    )


@login_required
@require_POST
def mark_read(request: HttpRequest, pk: int) -> HttpResponse:
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.mark_read()
    return _redirect_back(request)


@login_required
@require_POST
def mark_unread(request: HttpRequest, pk: int) -> HttpResponse:
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.mark_unread()
    return _redirect_back(request)


@login_required
@require_POST
def mark_all_read(request: HttpRequest) -> HttpResponse:
    Notification.objects.filter(recipient=request.user, read_at__isnull=True).update(
        read_at=timezone.now()
    )
    return _redirect_back(request)
