"""Fase 1: multi-role, permission berbasis role aktif, owner, dan pencatatan role."""

from datetime import date

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.identity.models import Membership, Role, RoleDefinition
from apps.identity.permissions import (
    can_comment,
    can_create_project,
    can_manage_project,
    can_report_issue,
    visible_projects,
)
from apps.identity.roles import (
    SESSION_KEY,
    active_role,
    assign_roles,
    has_perm,
    membership_codes,
    set_active_role,
)
from apps.projects.models import ActivityAction, ActivityEvent, Project
from apps.projects.services import record_activity

pytestmark = pytest.mark.django_db


def make_user(name, *roles, **extra):
    user = User.objects.create_user(name, password="valid-password", **extra)
    assign_roles(user, list(roles))
    return user


def make_project(manager=None, owner=None, **extra):
    return Project.objects.create(
        name="Alpha",
        code="ALPHA",
        manager=manager,
        owner=owner,
        start_date=date(2026, 10, 1),
        target_end_date=date(2026, 12, 1),
        **extra,
    )


def test_roles_are_seeded_with_default_permissions():
    codes = set(RoleDefinition.objects.values_list("code", flat=True))
    assert codes == set(Role.values)
    pm = RoleDefinition.objects.get(code="pm")
    assert pm.has_permission("project.create") and not pm.has_permission("task.update_progress")


def test_new_user_defaults_to_member_and_can_hold_many_roles():
    user = User.objects.create_user("fresh")
    assert membership_codes(user) == [Role.MEMBER]
    assign_roles(user, [Role.PROJECT_MANAGER, Role.OWNER])
    assert membership_codes(user) == [Role.PROJECT_MANAGER, Role.OWNER]
    assign_roles(user, [Role.OWNER])
    assert membership_codes(user) == [Role.OWNER]
    assert Membership.objects.filter(user=user).count() == 1


def test_staff_user_is_implicitly_admin():
    user = make_user("boss", Role.MEMBER, is_staff=True)
    assert membership_codes(user) == [Role.ADMIN, Role.MEMBER]
    assert active_role(user) == Role.ADMIN


def test_active_role_defaults_to_most_authoritative_and_cannot_be_forged():
    user = make_user("andi", Role.OWNER, Role.PROJECT_MANAGER)
    assert active_role(user) == Role.PROJECT_MANAGER
    assert set_active_role(user, Role.OWNER) is True
    assert active_role(user) == Role.OWNER
    # Role yang tidak dimiliki ditolak (BR-ROLE-007, BR-ROLE-010).
    assert set_active_role(user, Role.ADMIN) is False
    assert active_role(user) == Role.OWNER


def test_permissions_follow_the_active_role():
    user = make_user("andi", Role.PROJECT_MANAGER, Role.MANAGEMENT)
    assert can_create_project(user)
    assert can_report_issue(user) and can_comment(user)
    set_active_role(user, Role.MANAGEMENT)
    assert not can_create_project(user)
    assert not can_report_issue(user) and not can_comment(user)
    assert has_perm(user, "report.view")


def test_client_is_read_only():
    client_user = make_user("klien", Role.CLIENT)
    assert has_perm(client_user, "project.view")
    assert not has_perm(client_user, "task.update_progress")
    assert not can_create_project(client_user) and not can_report_issue(client_user)


def test_pm_manages_only_own_projects_but_admin_manages_all():
    pm, other = make_user("pm", Role.PROJECT_MANAGER), make_user("pm2", Role.PROJECT_MANAGER)
    admin = make_user("adm", Role.ADMIN)
    project = make_project(manager=pm)
    assert can_manage_project(pm, project)
    assert not can_manage_project(other, project)
    assert can_manage_project(admin, project)


def test_visible_projects_include_owner_member_and_exclude_outsiders():
    owner = make_user("sponsor", Role.OWNER)
    stakeholder = make_user("klien", Role.CLIENT)
    outsider = make_user("luar", Role.MEMBER)
    management = make_user("direksi", Role.MANAGEMENT)
    project = make_project(owner=owner)
    project.members.add(stakeholder)
    assert list(visible_projects(owner)) == [project]
    assert list(visible_projects(stakeholder)) == [project]
    assert list(visible_projects(outsider)) == []
    assert list(visible_projects(management)) == [project]
    membership = project.memberships.get(user=stakeholder)
    assert membership.project_role == "member" and membership.status == "active"


def test_middleware_applies_valid_session_role_and_ignores_invalid(client):
    user = make_user("andi", Role.PROJECT_MANAGER, Role.OWNER)
    client.force_login(user)
    session = client.session
    session[SESSION_KEY] = Role.OWNER
    session.save()
    response = client.get(reverse("projects:dashboard"))
    assert response.status_code == 200
    assert response.wsgi_request.user.pcc_profile.role == Role.OWNER
    session[SESSION_KEY] = Role.ADMIN
    session.save()
    response = client.get(reverse("projects:dashboard"))
    assert response.wsgi_request.user.pcc_profile.role == Role.PROJECT_MANAGER


def test_activity_records_the_active_role():
    user = make_user("andi", Role.PROJECT_MANAGER, Role.OWNER)
    project = make_project(manager=user)
    set_active_role(user, Role.OWNER)
    event = record_activity(project, user, ActivityAction.PROJECT_UPDATED, "Diubah.")
    assert ActivityEvent.objects.get(pk=event.pk).active_role == Role.OWNER
    system = record_activity(project, None, ActivityAction.PROJECT_UPDATED, "Sistem.")
    assert system.active_role == ""


def test_project_owner_is_required_for_new_projects_and_listed_in_form(client):
    pm = make_user("pm", Role.PROJECT_MANAGER)
    owner = make_user("sponsor", Role.OWNER)
    plain = make_user("biasa", Role.MEMBER)
    client.force_login(pm)
    response = client.get(reverse("projects:project_create"))
    queryset = response.context["form"].fields["owner"].queryset
    assert list(queryset) == [owner] and plain not in queryset
    assert response.context["form"].fields["owner"].required
