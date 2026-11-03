"""Katalog permission dan matriks default per role (PRD §25, §25.1).

Matriks ini hanya dipakai untuk mengisi ``RoleDefinition.permissions`` (migrasi
dan ``ensure_roles``). Setelah itu data di database yang berlaku, sehingga admin
dapat mengubahnya tanpa mengubah kode. Sel "Conditional" di PRD tidak diberikan
secara default; permission itu diberikan lewat konfigurasi.
"""

# kode -> label singkat (Indonesia)
PERMISSIONS = {
    "project.view": "Melihat project yang berwenang",
    "project.view_all": "Melihat seluruh project di workspace",
    "project.view_internal": "Melihat catatan, issue, dan aktivitas internal project",
    "project.create": "Membuat project",
    "project.update": "Mengubah informasi project",
    "project.archive": "Mengarsipkan project",
    "project.manage_members": "Mengelola anggota project",
    "structure.view": "Melihat struktur project",
    "structure.create": "Membuat phase dan work package",
    "structure.update": "Mengubah struktur project",
    "task.view": "Melihat task",
    "task.create": "Membuat task",
    "task.assign": "Menugaskan task",
    "task.execute": "Mengerjakan task",
    "task.update_progress": "Memperbarui progress task",
    "task.reassign": "Memindahkan penugasan task",
    "task.review": "Memeriksa hasil task",
    "task.approve": "Menyetujui task",
    "timeline.view": "Melihat jadwal",
    "timeline.update": "Mengubah jadwal",
    "baseline.view": "Melihat baseline",
    "baseline.approve": "Menyetujui baseline",
    "milestone.manage": "Mengelola milestone",
    "issue.report": "Melaporkan issue",
    "issue.manage": "Mengelola issue",
    "risk.manage": "Mengelola risiko",
    "change_request.submit": "Mengajukan change request",
    "change_request.approve": "Menyetujui change request",
    "comment.create": "Menulis komentar",
    "report.view": "Melihat laporan",
    "report.export": "Mengekspor laporan",
    "user.manage": "Mengelola user dan role",
    "template.manage": "Mengelola template project",
}

ALL_PERMISSIONS = sorted(PERMISSIONS)

# Urutan prioritas untuk role aktif bawaan (paling berwenang lebih dulu).
ROLE_PRIORITY = ["admin", "pm", "owner", "management", "member", "client"]

ROLE_LABELS = {
    "admin": "Workspace Admin",
    "pm": "Project Manager",
    "member": "Project Member",
    "owner": "Project Owner",
    "client": "Client / Stakeholder",
    "management": "Management",
}

ROLE_DESCRIPTIONS = {
    "admin": "Mengelola user, role, template, dan pengaturan workspace.",
    "pm": "Merencanakan, memonitor, dan mengontrol pelaksanaan project.",
    "member": "Melaksanakan task dan memperbarui progress.",
    "owner": "Bertanggung jawab atas outcome project dan keputusan strategis.",
    "client": "Melihat progress dan deliverable yang dibagikan.",
    "management": "Memantau portfolio dan project health.",
}

_READ = ["project.view", "structure.view", "task.view", "timeline.view", "baseline.view"]
_INTERNAL = ["project.view_internal"]

DEFAULT_ROLE_PERMISSIONS = {
    "admin": ALL_PERMISSIONS,
    "pm": sorted(
        set(
            _READ
            + _INTERNAL
            + [
                "project.create",
                "project.update",
                "project.archive",
                "project.manage_members",
                "structure.create",
                "structure.update",
                "task.create",
                "task.assign",
                "task.reassign",
                "timeline.update",
                "milestone.manage",
                "issue.report",
                "issue.manage",
                "risk.manage",
                "change_request.submit",
                "comment.create",
                "report.view",
                "report.export",
            ]
        )
    ),
    "member": sorted(
        set(
            _READ
            + _INTERNAL
            + [
                "task.execute",
                "task.update_progress",
                "issue.report",
                "comment.create",
                "report.view",
                "report.export",
            ]
        )
    ),
    "owner": sorted(
        set(
            _READ
            + _INTERNAL
            + [
                "baseline.approve",
                "issue.report",
                "change_request.submit",
                "change_request.approve",
                "comment.create",
                "report.view",
                "report.export",
            ]
        )
    ),
    "client": sorted(set(_READ + ["comment.create", "report.view"])),
    "management": sorted(
        set(_READ + _INTERNAL + ["project.view_all", "report.view", "report.export"])
    ),
}
# Admin dan management melihat seluruh project di workspace.
DEFAULT_ROLE_PERMISSIONS["admin"] = ALL_PERMISSIONS
