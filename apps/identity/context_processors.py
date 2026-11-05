from django.urls import reverse

from .navigation import nav_groups
from .permission_catalog import ROLE_LABELS
from .permissions import can_create_project
from .roles import active_role, has_perm, membership_codes


def quick_actions(user, groups: list[dict]) -> list[dict]:
    """Isi palet Quick actions: aksi buat, lompat ke halaman, dan akun."""
    actions = []
    if can_create_project(user):
        actions.append(("Aksi", "Buat project", reverse("projects:project_create")))
        actions.append(("Aksi", "Impor rencana dari AI", reverse("projects:plan_import_new")))
    for group in groups:
        for item in group["items"]:
            actions.append(("Buka", item["label"], item["url"]))
    actions.append(("Akun", "Pengaturan", reverse("identity:settings")))
    actions.append(("Akun", "Profil", reverse("identity:profile")))
    actions.append(("Akun", "Panduan (Docs)", reverse("identity:docs")))
    return [{"group": g, "label": label, "url": url} for g, label, url in actions]


def workspace(request):
    """Role aktif, daftar role yang boleh dipilih, dan navigasi sidebar."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    role = active_role(user)
    groups = nav_groups(role, request.path)
    return {
        "active_role": role,
        "active_role_label": ROLE_LABELS.get(role, ""),
        "available_roles": [
            {"code": code, "label": ROLE_LABELS[code], "active": code == role}
            for code in membership_codes(user)
        ],
        "nav_groups": groups,
        "quick_actions": quick_actions(user, groups),
        "can_manage_users": has_perm(user, "user.manage"),
    }
