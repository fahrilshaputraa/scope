from datetime import timedelta

import pytest
from authlib.integrations.base_client import OAuthError
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.work.forms import AttachmentForm, sanitize_filename
from tests.test_public_project import public_case, public_url, publish  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def test_login_locks_after_repeated_failures(client):
    User.objects.create_user("budi", password="rahasia-panjang-1")
    url = reverse("identity:login")
    for _ in range(5):
        client.post(url, {"username": "budi", "password": "salah"})
    response = client.post(url, {"username": "budi", "password": "rahasia-panjang-1"})
    assert "Terlalu banyak percobaan" in response.content.decode()
    assert "_auth_user_id" not in client.session


def test_login_success_clears_counter(client):
    User.objects.create_user("budi", password="rahasia-panjang-1")
    url = reverse("identity:login")
    for _ in range(3):
        client.post(url, {"username": "budi", "password": "salah"})
    assert (
        client.post(url, {"username": "budi", "password": "rahasia-panjang-1"}).status_code == 302
    )


def test_logout_requires_post(client):
    user = User.objects.create_user("budi", password="x")
    client.force_login(user)
    assert client.get(reverse("identity:logout")).status_code == 405
    assert client.post(reverse("identity:logout")).status_code == 302
    assert "_auth_user_id" not in client.session


def test_logout_button_is_post_form(client):
    user = User.objects.create_user("budi", password="x")
    client.force_login(user)
    html = client.get(reverse("projects:dashboard")).content.decode()
    assert f'method="post" action="{reverse("identity:logout")}"' in html


@override_settings(AZURE_ENABLED=True)
def test_callback_provider_error_redirects_with_message(client):
    response = client.get(reverse("identity:callback"), {"error": "access_denied"}, follow=True)
    assert response.status_code == 200
    assert "dibatalkan" in response.content.decode()


@override_settings(AZURE_ENABLED=True)
def test_callback_oauth_error_does_not_500(client, monkeypatch):
    class Boom:
        def authorize_access_token(self, request):
            raise OAuthError(error="mismatching_state")

    monkeypatch.setattr("apps.identity.views.get_entra_client", lambda: Boom())
    response = client.get(reverse("identity:callback"), {"code": "x"}, follow=True)
    assert response.status_code == 200
    assert "gagal" in response.content.decode()


def _upload(name, content=b"data", content_type="application/octet-stream"):
    form = AttachmentForm({}, {"file": SimpleUploadedFile(name, content, content_type)})
    return form


@pytest.mark.parametrize("name", ["a.exe", "a.html", "a.svg", "a.js", "a.php", "noext"])
def test_attachment_rejects_dangerous_extensions(name):
    assert not _upload(name).is_valid()


def test_attachment_accepts_allowed_and_sanitizes_name():
    form = _upload("../../Laporan Q1 (final)!.PDF", content_type="application/pdf")
    assert form.is_valid()
    assert form.cleaned_data["file"].name == "Laporan Q1 _final.pdf"


def test_attachment_rejects_mismatched_content_type():
    assert not _upload("a.pdf", content_type="text/html").is_valid()


def test_sanitize_filename_strips_path():
    assert sanitize_filename("..\\..\\evil.txt") == "evil.txt"


def test_public_link_expiry(client, public_case):  # noqa: F811
    project = public_case.project
    publish(project)
    project.public_expires_at = timezone.now() - timedelta(minutes=1)
    project.save()
    assert client.get(public_url(project)).status_code == 410
    project.public_expires_at = timezone.now() + timedelta(days=1)
    project.save()
    assert client.get(public_url(project)).status_code == 200


def test_public_link_password_unlock(client, public_case):  # noqa: F811
    from django.contrib.auth.hashers import make_password

    project = public_case.project
    publish(project)
    project.public_password_hash = make_password("kunci-rahasia")
    project.save()
    page = client.get(public_url(project))
    assert "Secret task title" not in page.content.decode()
    assert "Kata sandi" in page.content.decode()
    assert client.post(public_url(project), {"password": "salah"}).status_code == 403
    assert client.post(public_url(project), {"password": "kunci-rahasia"}).status_code == 302
    assert "Secret task title" in client.get(public_url(project)).content.decode()


def test_public_link_hides_task_titles(client, public_case):  # noqa: F811
    project = public_case.project
    publish(project)
    project.public_hide_task_titles = True
    project.save()
    html = client.get(public_url(project)).content.decode()
    assert "Secret task title" not in html
    assert "Task 1" in html
    assert project.tasks.get().title == "Secret task title"


def test_pm_saves_share_options(client, public_case):  # noqa: F811
    client.force_login(public_case.pm)
    day = (timezone.localdate() + timedelta(days=7)).isoformat()
    response = client.post(
        reverse("projects:project_share", args=[public_case.project.pk]),
        {"action": "options", "expires_on": day, "password": "abcdef", "hide_task_titles": "1"},
    )
    assert response.status_code == 302
    project = public_case.project
    project.refresh_from_db()
    assert project.public_expires_at is not None
    assert project.public_hide_task_titles
    assert project.public_password_hash and project.public_password_hash != "abcdef"


def test_production_settings_require_secret_key():
    import subprocess
    import sys

    env = {"PATH": "/usr/bin:/bin", "DJANGO_SETTINGS_MODULE": "config.settings.production"}
    result = subprocess.run(
        [sys.executable, "-c", "import django; django.setup()"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY" in result.stderr
