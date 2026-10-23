import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.identity.models import Role

pytestmark = pytest.mark.django_db


@pytest.fixture
def accounts(db):
    staff = User.objects.create_user("admin", password="valid-password", is_staff=True)
    staff.pcc_profile.role = Role.MANAGEMENT
    staff.pcc_profile.display_name = "Admin Scope"
    staff.pcc_profile.save()
    member = User.objects.create_user(
        "dimas",
        password="valid-password",
        first_name="Dimas",
        last_name="Pratama",
        email="dimas@example.com",
    )
    member.pcc_profile.job_title = "Analis"
    member.pcc_profile.save()
    return staff, member


def test_staff_can_list_search_and_filter_users(client, accounts):
    staff, member = accounts
    client.force_login(staff)

    response = client.get(reverse("identity:user_list"))
    assert response.status_code == 200
    assert response.context["total_users"] == 2
    assert response.context["active_users"] == 2
    assert b"dimas@example.com" in response.content

    searched = client.get(reverse("identity:user_list"), {"q": "Dimas"})
    assert [user.pk for user in searched.context["users"]] == [member.pk]

    by_role = client.get(reverse("identity:user_list"), {"role": Role.MANAGEMENT})
    assert [user.pk for user in by_role.context["users"]] == [staff.pk]

    member.is_active = False
    member.save(update_fields=["is_active"])
    inactive = client.get(reverse("identity:user_list"), {"status": "inactive"})
    assert [user.pk for user in inactive.context["users"]] == [member.pk]
    assert inactive.context["inactive_users"] == 1


def test_user_list_paginates(client, accounts):
    staff, _ = accounts
    for index in range(30):
        User.objects.create_user(f"person{index:02d}", password="valid-password")
    client.force_login(staff)

    first = client.get(reverse("identity:user_list"))
    assert len(first.context["users"]) == 25
    second = client.get(reverse("identity:user_list"), {"page": 2})
    assert second.context["page_obj"].number == 2
    assert len(second.context["users"]) == 7


def test_non_staff_cannot_manage_users(client, accounts):
    _, member = accounts
    client.force_login(member)

    assert client.get(reverse("identity:user_list")).status_code == 403
    assert client.get(reverse("identity:user_create")).status_code == 403
    assert client.post(reverse("identity:user_edit", args=[member.pk]), {}).status_code == 403
    assert client.post(reverse("identity:user_password", args=[member.pk]), {}).status_code == 403
    assert client.post(reverse("identity:user_toggle_active", args=[member.pk])).status_code == 403


def test_edit_updates_identity_role_and_status(client, accounts):
    staff, member = accounts
    client.force_login(staff)

    response = client.post(
        reverse("identity:user_edit", args=[member.pk]),
        {
            "username": "dimas",
            "first_name": "Dimas",
            "last_name": "Pratama",
            "email": "dimas.pratama@example.com",
            "role": Role.PROJECT_MANAGER,
            "display_name": "Dimas P.",
            "job_title": "Lead Analyst",
            "is_active": "on",
        },
    )
    assert response.status_code == 302
    member.refresh_from_db()
    assert member.email == "dimas.pratama@example.com"
    assert member.pcc_profile.role == Role.PROJECT_MANAGER
    assert member.pcc_profile.display_name == "Dimas P."
    assert member.pcc_profile.job_title == "Lead Analyst"
    assert member.is_active


def test_edit_can_deactivate_another_account(client, accounts):
    staff, member = accounts
    client.force_login(staff)

    client.post(
        reverse("identity:user_edit", args=[member.pk]),
        {
            "username": "dimas",
            "first_name": "Dimas",
            "last_name": "Pratama",
            "email": "dimas@example.com",
            "role": Role.MEMBER,
            "display_name": "",
            "job_title": "",
        },
    )
    member.refresh_from_db()
    assert not member.is_active


def test_staff_cannot_deactivate_self(client, accounts):
    staff, _ = accounts
    client.force_login(staff)

    response = client.post(
        reverse("identity:user_edit", args=[staff.pk]),
        {
            "username": "admin",
            "first_name": "",
            "last_name": "",
            "email": "",
            "role": Role.MANAGEMENT,
            "display_name": "Admin Scope",
            "job_title": "",
        },
    )
    assert response.status_code == 200
    assert b"Anda tidak dapat menonaktifkan akun sendiri" in response.content
    staff.refresh_from_db()
    assert staff.is_active

    toggled = client.post(reverse("identity:user_toggle_active", args=[staff.pk]), follow=True)
    assert toggled.status_code == 200
    assert b"Anda tidak dapat menonaktifkan akun sendiri" in toggled.content
    staff.refresh_from_db()
    assert staff.is_active


def test_toggle_active_round_trip_and_login_blocked(client, accounts):
    staff, member = accounts
    client.force_login(staff)

    client.post(reverse("identity:user_toggle_active", args=[member.pk]))
    member.refresh_from_db()
    assert not member.is_active

    client.logout()
    client.post(
        reverse("identity:login"),
        {"username": "dimas", "password": "valid-password"},
    )
    assert "_auth_user_id" not in client.session

    client.force_login(staff)
    client.post(reverse("identity:user_toggle_active", args=[member.pk]))
    member.refresh_from_db()
    assert member.is_active


def test_staff_resets_password_without_old_password(client, accounts):
    staff, member = accounts
    client.force_login(staff)

    response = client.post(
        reverse("identity:user_password", args=[member.pk]),
        {"new_password1": "kata-sandi-baru-123", "new_password2": "kata-sandi-baru-123"},
    )
    assert response.status_code == 302
    member.refresh_from_db()
    assert member.check_password("kata-sandi-baru-123")
    assert not member.check_password("valid-password")


def test_password_reset_rejects_mismatched_confirmation(client, accounts):
    staff, member = accounts
    client.force_login(staff)

    response = client.post(
        reverse("identity:user_password", args=[member.pk]),
        {"new_password1": "kata-sandi-baru-123", "new_password2": "berbeda-456"},
    )
    assert response.status_code == 200
    member.refresh_from_db()
    assert member.check_password("valid-password")


def test_short_passwords_are_rejected(client, accounts):
    staff, member = accounts
    client.force_login(staff)

    created = client.post(
        reverse("identity:user_create"),
        {
            "username": "pendek",
            "role": Role.MEMBER,
            "password1": "pendek",
            "password2": "pendek",
        },
    )
    assert created.status_code == 200
    assert b"Kata sandi minimal 8 karakter" in created.content
    assert not User.objects.filter(username="pendek").exists()

    updated = client.post(
        reverse("identity:user_password", args=[member.pk]),
        {"new_password1": "pendek", "new_password2": "pendek"},
    )
    assert updated.status_code == 200
    assert b"Kata sandi minimal 8 karakter" in updated.content
    member.refresh_from_db()
    assert member.check_password("valid-password")


def test_create_user_assigns_role_and_profile(client, accounts):
    staff, _ = accounts
    client.force_login(staff)

    response = client.post(
        reverse("identity:user_create"),
        {
            "username": "sari",
            "first_name": "Sari",
            "last_name": "Wulandari",
            "email": "sari@example.com",
            "role": Role.PROJECT_MANAGER,
            "display_name": "Sari W.",
            "job_title": "PM",
            "password1": "kata-sandi-baru-123",
            "password2": "kata-sandi-baru-123",
        },
    )
    assert response.status_code == 302
    created = User.objects.get(username="sari")
    assert created.pcc_profile.role == Role.PROJECT_MANAGER
    assert created.pcc_profile.display_name == "Sari W."
    assert created.check_password("kata-sandi-baru-123")
    assert not created.is_staff
