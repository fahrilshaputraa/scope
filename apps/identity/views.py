from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.form_widgets import style_form
from apps.projects.pagination import paginate

from .forms import LocalUserCreateForm, StaffPasswordResetForm, UserEditForm
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


def _require_staff(request) -> None:
    if not request.user.is_staff:
        raise PermissionDenied


def _display_name(user) -> str:
    profile = getattr(user, "pcc_profile", None)
    if profile is not None:
        return profile.name
    return user.get_full_name() or user.username


@login_required
def user_list(request: HttpRequest) -> HttpResponse:
    _require_staff(request)

    filters = {
        "q": request.GET.get("q", "").strip(),
        "role": request.GET.get("role", "").strip(),
        "status": request.GET.get("status", "").strip(),
    }
    users = User.objects.select_related("pcc_profile").order_by(
        "first_name", "last_name", "username"
    )
    if filters["q"]:
        query = filters["q"]
        users = users.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
            | Q(pcc_profile__display_name__icontains=query)
        )
    if filters["role"] in Role.values:
        users = users.filter(pcc_profile__role=filters["role"])
    if filters["status"] == "active":
        users = users.filter(is_active=True)
    elif filters["status"] == "inactive":
        users = users.filter(is_active=False)

    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    page_obj = paginate(request, users, per_page=25)
    return render(
        request,
        "identity/user_list.html",
        {
            "users": page_obj.object_list,
            "page_obj": page_obj,
            "filters": filters,
            "role_choices": Role.choices,
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": total_users - active_users,
        },
    )


@login_required
def user_create(request: HttpRequest) -> HttpResponse:
    _require_staff(request)

    form = LocalUserCreateForm(request.POST or None)
    style_form(
        form,
        primary=[
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "password1",
            "password2",
        ],
    )
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(request, f"Akun {user.username} dibuat.")
        return redirect(_safe_next(request, "identity:user_list"))
    return render(
        request,
        "identity/user_create.html",
        {
            "form": form,
            "back_url": reverse("identity:user_list"),
            "subtitle": (
                "Akun baru dapat langsung dipakai untuk masuk. "
                "Bagikan kata sandi awal melalui kanal yang aman."
            ),
        },
    )


@login_required
def user_edit(request: HttpRequest, pk: int) -> HttpResponse:
    _require_staff(request)

    target = get_object_or_404(User.objects.select_related("pcc_profile"), pk=pk)
    form = UserEditForm(request.POST or None, instance=target)
    if request.method == "POST" and form.is_valid():
        if target == request.user and not form.cleaned_data["is_active"]:
            form.add_error("is_active", "Anda tidak dapat menonaktifkan akun sendiri.")
        else:
            form.save()
            messages.success(request, f"Akun {target.username} diperbarui.")
            return redirect(_safe_next(request, "identity:user_list"))
    style_form(form)
    subtitle = f"{_display_name(target)} · @{target.username}"
    if target == request.user:
        subtitle += ". Anda mengedit akun sendiri; akun ini tidak dapat dinonaktifkan."
    return render(
        request,
        "identity/user_edit.html",
        {
            "form": form,
            "target": target,
            "is_self": target == request.user,
            "back_url": reverse("identity:user_list"),
            "subtitle": subtitle,
        },
    )


@login_required
def user_password(request: HttpRequest, pk: int) -> HttpResponse:
    _require_staff(request)

    target = get_object_or_404(User, pk=pk)
    form = StaffPasswordResetForm(target, request.POST or None)
    style_form(form)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Kata sandi {target.username} telah direset.")
        return redirect(_safe_next(request, "identity:user_list"))
    return render(
        request,
        "identity/user_password.html",
        {
            "form": form,
            "target": target,
            "back_url": reverse("identity:user_list"),
            "subtitle": (
                f"Atur kata sandi baru untuk {_display_name(target)} (@{target.username}). "
                "Kata sandi lama tidak diperlukan."
            ),
        },
    )


@login_required
@require_POST
def user_toggle_active(request: HttpRequest, pk: int) -> HttpResponse:
    _require_staff(request)

    target = get_object_or_404(User, pk=pk)
    if target == request.user:
        messages.error(request, "Anda tidak dapat menonaktifkan akun sendiri.")
        return redirect(_safe_next(request, "identity:user_list"))
    target.is_active = not target.is_active
    target.save(update_fields=["is_active"])
    state = "diaktifkan" if target.is_active else "dinonaktifkan"
    messages.success(request, f"Akun {target.username} {state}.")
    return redirect(_safe_next(request, "identity:user_list"))
