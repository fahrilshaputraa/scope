"""Navigasi sidebar per role (PRD §6.1, U6).

Sidebar hanya memuat halaman kerja harian, dikelompokkan menjadi "Kerja" (mulai
dari sini) dan "Pantau" (lintas project). Halaman administrasi yang jarang dibuka
(pengguna, role, template, jejak audit, integrasi) ada di Pengaturan
(``SETTINGS_ITEMS``); catatan semua project dan pemeriksaan ada di Quick actions
dan di halaman Persetujuan. Label memakai bahasa Indonesia seragam
(``docs/ux-glossary.md``).
"""

from django.urls import reverse

# key -> (label bawaan, nama url, prefix path untuk status aktif, isi svg)
ITEMS = {
    "dashboard": (
        "Dashboard",
        "projects:dashboard",
        ("/",),
        '<rect x="3" y="3" width="7" height="7" rx="1"/>'
        '<rect x="14" y="3" width="7" height="7" rx="1"/>'
        '<rect x="3" y="14" width="7" height="7" rx="1"/>'
        '<rect x="14" y="14" width="7" height="7" rx="1"/>',
    ),
    "projects": (
        "Project",
        "projects:project_list",
        ("/projects",),
        '<path d="M3 7h7l2 3h9v10H3zM3 7V4h7l2 3h9v3"/>',
    ),
    "reports": (
        "Laporan",
        "projects:reports",
        ("/reports",),
        '<path d="M4 3v18h17M9 17v-5M14 17V8M19 17V4"/>',
    ),
    "my_tasks": (
        "Pekerjaan saya",
        "work:my_tasks",
        ("/my-tasks", "/tasks"),
        '<path d="m3 6 2 2 4-4M13 6h8m-18 9 2 2 4-4M13 15h8M13 21h8"/>',
    ),
    "issues": (
        "Masalah",
        "work:issue_list",
        ("/issues",),
        '<path d="m12 3 10 18H2zM12 9v5M12 17v1"/>',
    ),
    "timeline": (
        "Jadwal semua project",
        "projects:timeline_global",
        ("/timeline",),
        '<path d="M3 5h12M8 12h13M3 19h10M3 3v4M8 10v4M3 17v4"/>',
    ),
    "notes": (
        "Catatan",
        "projects:note_list",
        ("/notes",),
        '<path d="M6 3h14v18H6zM3 7h5M3 12h5M3 17h5M11 8h5M11 12h5"/>',
    ),
    "progress_task": (
        "Progress task",
        "projects:progress_task",
        ("/progress-task",),
        '<path d="M4 6h16M4 12h10M4 18h6"/><path d="m16 15 2 2 3-4"/>',
    ),
    "control": (
        "Kontrol project",
        "projects:control_index",
        ("/control",),
        '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12"/>'
        '<circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/>'
        '<circle cx="18" cy="18" r="2"/>',
    ),
    "approvals": (
        "Persetujuan",
        "governance:approval_inbox",
        ("/approvals", "/reviews"),
        '<path d="M9 11l3 3 8-8"/>'
        '<path d="M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9"/>',
    ),
    "reviews": (
        "Pemeriksaan saya",
        "governance:my_reviews",
        ("/reviews",),
        '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3M8 11l2 2 4-4"/>',
    ),
    "templates": (
        "Template",
        "projects:template_list",
        ("/templates",),
        '<path d="M8 3h11v14H8zM5 7v14h11"/>',
    ),
    "audit": (
        "Jejak audit",
        "projects:audit_trail",
        ("/audit",),
        '<path d="M9 3h6l1 2h3v16H5V5h3zM9 12l2 2 4-4"/>',
    ),
    "users": (
        "Pengguna",
        "identity:user_list",
        ("/auth/users",),
        '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>'
        '<path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    ),
    "integrations": (
        "Integrasi",
        "integrations:index",
        ("/integrations",),
        '<path d="M9 7V3M15 7V3M7 7h10v4a5 5 0 0 1-10 0zM12 16v5"/>',
    ),
    "roles": (
        "Role & permission",
        "identity:role_list",
        ("/auth/roles",),
        '<path d="M12 3 4 6v6c0 4.5 3.2 7.7 8 9 4.8-1.3 8-4.5 8-9V6zM9 12l2 2 4-4"/>',
    ),
}

WORK = "Kerja"
MONITOR = "Pantau"

# role -> daftar (judul grup, [key atau (key, label khusus)])
ROLE_NAV = {
    "admin": [
        (WORK, ["dashboard", "projects", "approvals"]),
        (MONITOR, ["progress_task", "control", "reports"]),
    ],
    "pm": [
        (WORK, ["dashboard", "projects", "approvals"]),
        (MONITOR, ["progress_task", "control", "issues", "timeline", "reports"]),
    ],
    "member": [
        (WORK, ["dashboard", "my_tasks", "reviews", "projects"]),
        (MONITOR, ["issues", "timeline"]),
    ],
    "owner": [
        (WORK, ["dashboard", "projects", "approvals"]),
        (MONITOR, ["issues", "timeline", "reports"]),
    ],
    "management": [
        (WORK, [("dashboard", "Portfolio"), "projects"]),
        (MONITOR, ["timeline", "reports"]),
    ],
    "client": [
        (WORK, ["dashboard", "projects", ("approvals", "Penerimaan")]),
        (MONITOR, ["timeline"]),
    ],
}

# Item yang dipindah ke Pengaturan: key -> permission yang dibutuhkan (None = semua).
SETTINGS_ITEMS = [
    ("users", "user.manage"),
    ("roles", "user.manage"),
    ("templates", "template.manage"),
    ("audit", "audit.view"),
    ("integrations", None),
]


def settings_links(user, active: str = "") -> list[dict]:
    """Tautan administrasi di Pengaturan sesuai permission user aktif."""
    from .roles import has_perm

    links = []
    for key, perm in SETTINGS_ITEMS:
        if perm and not has_perm(user, perm):
            continue
        label, url_name, _prefixes, icon = ITEMS[key]
        links.append(
            {
                "key": key,
                "label": label,
                "url": reverse(url_name),
                "icon": icon,
                "active": key == active,
            }
        )
    return links


def _is_active(path: str, prefixes) -> bool:
    for prefix in prefixes:
        if prefix == "/":
            if path == "/":
                return True
            continue
        clean = prefix.rstrip("/")
        if path == clean or path.startswith(clean + "/"):
            return True
    return False


def nav_groups(role: str, path: str) -> list[dict]:
    groups = []
    for title, entries in ROLE_NAV.get(role, ROLE_NAV["member"]):
        items = []
        for entry in entries:
            key, override = (entry, None) if isinstance(entry, str) else entry
            label, url_name, prefixes, icon = ITEMS[key]
            items.append(
                {
                    "key": key,
                    "label": override or label,
                    "url": reverse(url_name),
                    "icon": icon,
                    "active": _is_active(path, prefixes),
                }
            )
        groups.append({"title": title, "items": items})
    return groups
