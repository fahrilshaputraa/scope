import re

from django.urls import reverse

from .navigation import nav_groups, settings_links
from .permission_catalog import ROLE_LABELS
from .permissions import can_create_project
from .roles import active_role, has_perm, membership_codes

PROJECT_PATH = re.compile(r"^/projects/(\d+)/")


def quick_actions(user, groups: list[dict], path: str = "") -> list[dict]:
    """Isi palet Quick actions (Ctrl K): aksi project aktif, aksi buat, halaman, akun."""
    actions = []
    match = PROJECT_PATH.match(path)
    if match and has_perm(user, "project.update"):
        # Aksi cepat di project yang sedang dibuka; izin per project dicek di view.
        pk = int(match.group(1))
        task_new = reverse("work:task_create") + f"?project={pk}"
        actions += [
            ("Project ini", "Buat task cepat", task_new),
            (
                "Project ini",
                "Tempel daftar task",
                reverse("projects:project_timeline", args=[pk]) + "?action=paste",
            ),
            ("Project ini", "Laporkan masalah", reverse("work:issue_create") + f"?project={pk}"),
            ("Project ini", "Tambah milestone", reverse("projects:milestone_create", args=[pk])),
            ("Project ini", "Tulis catatan", reverse("projects:note_create", args=[pk])),
            ("Project ini", "Buka jadwal", reverse("projects:project_timeline", args=[pk])),
            (
                "Project ini",
                "Persetujuan & perubahan",
                reverse("governance:project_approvals", args=[pk]),
            ),
            ("Project ini", "Pengaturan project", reverse("projects:project_settings", args=[pk])),
        ]
    if can_create_project(user):
        actions.append(("Aksi", "Buat project", reverse("projects:project_create")))
        actions.append(("Aksi", "Impor rencana dari AI", reverse("projects:plan_import_new")))
    seen = set()
    for group in groups:
        for item in group["items"]:
            seen.add(item["key"])
            actions.append(("Buka", item["label"], item["url"]))
    extra = [
        ("approvals", "project.view_internal", "Persetujuan", "governance:approval_inbox"),
        ("reviews", "task.review", "Pemeriksaan saya", "governance:my_reviews"),
        ("notes", "project.view_internal", "Catatan semua project", "projects:note_list"),
        ("my_tasks", "task.execute", "Pekerjaan saya", "work:my_tasks"),
    ]
    for key, perm, label, url_name in extra:
        if key not in seen and has_perm(user, perm):
            actions.append(("Buka", label, reverse(url_name)))
    for item in settings_links(user):
        actions.append(("Pengaturan", item["label"], item["url"]))
    actions.append(("Akun", "Pengaturan akun", reverse("identity:settings")))
    actions.append(("Akun", "Profil", reverse("identity:profile")))
    actions.append(("Akun", "Panduan", reverse("identity:docs")))
    drawer = {"Buat task cepat", "Laporkan masalah", "Tambah milestone", "Tulis catatan"}
    return [
        {"group": g, "label": label, "url": url, "drawer": g == "Project ini" and label in drawer}
        for g, label, url in actions
    ]


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
        "quick_actions": quick_actions(user, groups, request.path),
        "can_manage_users": has_perm(user, "user.manage"),
        "settings_links": settings_links(user),
    }
