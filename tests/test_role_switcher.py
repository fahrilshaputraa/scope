"""Fase 2: role switcher, navigasi per role, halaman role, dan akses Client."""

from datetime import date

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.identity.models import Role, RoleDefinition
from apps.identity.permission_catalog import ALL_PERMISSIONS
from apps.identity.roles import SESSION_KEY, assign_roles
from apps.projects.models import Project

pytestmark = pytest.mark.django_db


def make_user(name, *roles, **extra):
    user = User.objects.create_user(name, password="valid-password", **extra)
    assign_roles(user, list(roles))
    return user


def make_project(**extra):
    fields = {
        "name": "Alpha",
        "code": "ALPHA",
        "start_date": date(2026, 10, 1),
        "target_end_date": date(2026, 12, 1),
        **extra,
    }
    return Project.objects.create(**fields)


def page(client, name, *args):
    return client.get(reverse(name, args=args))


def test_switcher_is_hidden_for_single_role_and_shown_for_several(client):
    single = make_user("solo", Role.MEMBER)
    client.force_login(single)
    body = page(client, "projects:dashboard").content
    assert b'class="project-add-menu role-switcher"' not in body
    multi = make_user("multi", Role.PROJECT_MANAGER, Role.OWNER)
    client.force_login(multi)
    body = page(client, "projects:dashboard").content
    assert b"role-switcher" in body and b"Project Owner" in body


def test_switch_role_changes_sidebar_and_session(client):
    user = make_user("andi", Role.PROJECT_MANAGER, Role.MANAGEMENT)
    client.force_login(user)
    pm_body = page(client, "projects:dashboard").content
    assert b'aria-label="Kontrol project"' in pm_body and b"Portfolio" not in pm_body
    response = client.post(reverse("identity:switch_role"), {"role": Role.MANAGEMENT})
    assert response.status_code == 302 and response.url == reverse("projects:dashboard")
    assert client.session[SESSION_KEY] == Role.MANAGEMENT
    mgmt_body = page(client, "projects:dashboard").content
    assert b"Portfolio" in mgmt_body and b'aria-label="Kontrol project"' not in mgmt_body


def test_switching_to_an_unowned_role_is_refused(client):
    user = make_user("budi", Role.MEMBER)
    client.force_login(user)
    response = client.post(reverse("identity:switch_role"), {"role": Role.ADMIN})
    assert response.status_code == 302
    assert SESSION_KEY not in client.session
    assert client.get(reverse("identity:user_list")).status_code == 403


def test_switch_role_requires_post_and_login(client):
    assert client.get(reverse("identity:switch_role")).status_code in (302, 405)
    user = make_user("budi", Role.MEMBER)
    client.force_login(user)
    assert client.get(reverse("identity:switch_role")).status_code == 405


def test_member_and_admin_navigation_differ(client):
    member = make_user("budi", Role.MEMBER)
    client.force_login(member)
    body = page(client, "projects:dashboard").content
    assert b"Laporan" not in body and b"Role &amp; permission" not in body
    admin = make_user("adm", Role.ADMIN)
    client.force_login(admin)
    body = page(client, "projects:dashboard").content
    assert b"Role &amp; permission" in body and b"Pengguna" in body


def test_user_management_follows_the_active_role_for_staff(client):
    staff = make_user("boss", Role.PROJECT_MANAGER, is_staff=True)
    client.force_login(staff)
    assert client.get(reverse("identity:user_list")).status_code == 200
    client.post(reverse("identity:switch_role"), {"role": Role.PROJECT_MANAGER})
    assert client.get(reverse("identity:user_list")).status_code == 403
    assert client.get(reverse("identity:role_list")).status_code == 403


def test_admin_edits_role_permissions_but_admin_role_stays_full(client):
    admin = make_user("adm", Role.ADMIN)
    client.force_login(admin)
    assert page(client, "identity:role_list").status_code == 200
    response = client.post(
        reverse("identity:role_list"),
        {"perm_member": ["project.view", "task.view"], "perm_admin": ["project.view"]},
    )
    assert response.status_code == 302
    assert RoleDefinition.objects.get(code="member").permissions == ["project.view", "task.view"]
    assert RoleDefinition.objects.get(code="admin").permissions == sorted(ALL_PERMISSIONS)
    # Permission yang dicabut langsung berlaku.
    member = make_user("budi", Role.MEMBER)
    client.force_login(member)
    assert client.get(reverse("identity:role_list")).status_code == 403


def test_unknown_permission_codes_are_ignored(client):
    admin = make_user("adm", Role.ADMIN)
    client.force_login(admin)
    client.post(reverse("identity:role_list"), {"perm_pm": ["project.view", "hack.everything"]})
    assert RoleDefinition.objects.get(code="pm").permissions == ["project.view"]


def test_client_sees_shared_project_but_not_internal_pages(client):
    stakeholder = make_user("klien", Role.CLIENT)
    shared = make_project()
    shared.members.add(stakeholder)
    hidden = make_project(name="Beta", code="BETA")
    client.force_login(stakeholder)
    overview = client.get(reverse("projects:project_detail", args=[shared.pk]))
    assert overview.status_code == 200
    assert b"Aktivitas terbaru" not in overview.content
    tabs = [key for key, _ in overview.context["tabs"]]
    # Tab project (U6): Client tidak melihat Masalah, Catatan, dan Aktivitas.
    assert tabs == ["overview", "work", "progress", "milestones"]
    # Client melihat deliverable yang dibagikan (PRD §21.5) sebagai bagian Milestone.
    assert overview.context["project_sections"] == [
        "overview",
        "tasks_list",
        "tasks",
        "timeline",
        "structure",
        "progress",
        "milestones",
        "deliverables",
    ]
    assert client.get(reverse("projects:project_detail", args=[hidden.pk])).status_code == 404
    for name in ("project_issues", "project_notes", "project_activity", "project_history"):
        assert client.get(reverse("projects:" + name, args=[shared.pk])).status_code == 403
    assert client.get(reverse("work:issue_list")).status_code == 403
    assert client.get(reverse("projects:note_list")).status_code == 403


def test_internal_roles_still_reach_internal_pages(client):
    pm = make_user("pm", Role.PROJECT_MANAGER)
    project = make_project(manager=pm)
    client.force_login(pm)
    for name in ("project_issues", "project_notes", "project_activity", "project_history"):
        assert client.get(reverse("projects:" + name, args=[project.pk])).status_code == 200
