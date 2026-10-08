from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm
from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache

from apps.form_widgets import style_form

from .models import Role
from .oidc import get_entra_client
from .services import upsert_user_from_claims


def _safe_next(request, default="projects:dashboard") -> str:
    next_url = request.GET.get("next") or request.POST.get("next") or ""
    if url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return reverse(default)


@never_cache
def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("projects:dashboard")
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        django_login(request, form.get_user())
        return redirect(_safe_next(request))
    return render(
        request,
        "identity/login.html",
        {
            "form": form,
            "entra_enabled": settings.AZURE_ENABLED,
            "next": request.GET.get("next") or request.POST.get("next", ""),
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


@login_required
def profile_view(request: HttpRequest) -> HttpResponse:
    return render(request, "identity/profile.html")


@login_required
def settings_view(request):
    from django import forms

    class ProfileForm(forms.ModelForm):
        class Meta:
            model = User
            fields = ["first_name", "last_name", "email"]

    profile_form = ProfileForm(
        request.POST if request.POST.get("action") == "profile" else None, instance=request.user
    )
    password_form = PasswordChangeForm(
        request.user, request.POST if request.POST.get("action") == "password" else None
    )
    style_form(profile_form)
    style_form(password_form)
    if request.method == "POST":
        if request.POST.get("action") == "profile" and profile_form.is_valid():
            profile_form.save()
            messages.success(request, "Profil disimpan.")
            return redirect("identity:settings")
        if request.POST.get("action") == "password" and password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Password diperbarui.")
            return redirect("identity:settings")
    return render(
        request,
        "identity/settings.html",
        {"profile_form": profile_form, "password_form": password_form},
    )


@login_required
def user_create(request):
    from django import forms
    from django.core.exceptions import PermissionDenied

    if not request.user.is_staff:
        raise PermissionDenied

    class LocalUserForm(UserCreationForm):
        role = forms.ChoiceField(choices=Role.choices, initial=Role.MEMBER)

        class Meta(UserCreationForm.Meta):
            fields = ["username", "first_name", "last_name", "email"]

    form = LocalUserForm(request.POST or None)
    style_form(form)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        user.pcc_profile.role = form.cleaned_data["role"]
        user.pcc_profile.save()
        messages.success(request, f"Akun {user.username} dibuat.")
        return redirect("identity:settings")
    return render(request, "identity/user_form.html", {"form": form})
