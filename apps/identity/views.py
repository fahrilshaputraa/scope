from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache

from .models import Role, UserProfile
from .oidc import get_entra_client
from .services import upsert_user_from_claims


def _safe_next(request, default="projects:dashboard") -> str:
    next_url = request.GET.get("next") or request.POST.get("next") or ""
    if url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return reverse(default)


def dev_login_allowed() -> bool:
    """Login dev hanya bila Entra ID belum dikonfigurasi atau DEBUG."""
    return settings.DEBUG or not settings.AZURE_ENABLED


@never_cache
def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("projects:dashboard")
    return render(
        request,
        "identity/login.html",
        {
            "entra_enabled": settings.AZURE_ENABLED,
            "dev_login": dev_login_allowed(),
            "dev_form": dev_login_allowed() and not settings.AZURE_ENABLED,
            "roles": Role.choices,
            "next": request.GET.get("next", ""),
        },
    )


@never_cache
def authorize_view(request: HttpRequest) -> HttpResponse:
    if not settings.AZURE_ENABLED:
        return redirect("identity:login")
    next_url = request.GET.get("next", "")
    if url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        request.session["pcc_login_next"] = next_url
    client = get_entra_client()
    redirect_uri = request.build_absolute_uri(reverse("identity:callback"))
    return client.authorize_redirect(request, redirect_uri)


@never_cache
def callback_view(request: HttpRequest) -> HttpResponse:
    client = get_entra_client()
    token = client.authorize_access_token(request)
    metadata = client.load_server_metadata()
    userinfo_endpoint = metadata.get("userinfo_endpoint")
    if userinfo_endpoint:
        claims = client.get(userinfo_endpoint, token=token).json()
    else:  # pragma: no cover - fallback bila metadata tanpa userinfo
        claims = token.get("userinfo") or {}
    user = upsert_user_from_claims(claims)
    django_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    messages.success(request, f"Signed in as {user.username}")
    next_url = request.session.pop("pcc_login_next", "") or reverse("projects:dashboard")
    if not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        next_url = reverse("projects:dashboard")
    return redirect(next_url)


def logout_view(request: HttpRequest) -> HttpResponse:
    django_logout(request)
    return redirect("identity:login")


@never_cache
def dev_login_view(request: HttpRequest) -> HttpResponse:
    if not dev_login_allowed():
        return redirect("identity:login")
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        role = request.POST.get("role", Role.MEMBER)
        if role not in Role.values:
            role = Role.MEMBER
        if not username:
            messages.error(request, "Username wajib diisi.")
            return redirect("identity:dev")
        user, _ = User.objects.get_or_create(username=username)
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if profile.role != role:
            profile.role = role
            profile.save(update_fields=["role", "updated_at"])
        django_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, f"Dev login sebagai {username} ({profile.get_role_display()})")
        return redirect(_safe_next(request))
    return render(
        request,
        "identity/login.html",
        {
            "entra_enabled": False,
            "dev_login": True,
            "dev_form": True,
            "roles": Role.choices,
            "next": request.GET.get("next", ""),
        },
    )


@login_required
def profile_view(request: HttpRequest) -> HttpResponse:
    return render(request, "identity/profile.html")
