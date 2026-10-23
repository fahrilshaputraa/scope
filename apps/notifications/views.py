from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.projects.pagination import paginate

from .models import Notification


def _redirect_back(request: HttpRequest) -> HttpResponse:
    target = request.POST.get("next") or reverse("notifications:center")
    if not url_has_allowed_host_and_scheme(
        target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        target = reverse("notifications:center")
    return redirect(target)


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
