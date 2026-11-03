"""Role, role aktif, dan permission user (PRD §4, §25).

Satu user punya banyak ``Membership``. Role aktif dipilih per sesi
(``SESSION_KEY``) dan default-nya role paling berwenang. User ``is_staff``
selalu dianggap memiliki role Admin.
"""

from django.db import transaction

from .models import Membership, Role, RoleDefinition, Workspace
from .permission_catalog import (
    DEFAULT_ROLE_PERMISSIONS,
    ROLE_DESCRIPTIONS,
    ROLE_LABELS,
    ROLE_PRIORITY,
)

SESSION_KEY = "pcc_active_role"
DEFAULT_WORKSPACE_CODE = "default"

_CODES_CACHE = "_pcc_role_codes"
_PERMS_CACHE = "_pcc_perm_cache"
_ACTIVE_ATTR = "_pcc_active_role"


def default_workspace() -> Workspace:
    workspace, _ = Workspace.objects.get_or_create(
        code=DEFAULT_WORKSPACE_CODE, defaults={"name": "Scope"}
    )
    return workspace


def get_role(code: str) -> RoleDefinition:
    """Ambil definisi role; dibuat dari katalog bila belum ada."""
    role, _ = RoleDefinition.objects.get_or_create(
        code=code,
        defaults={
            "name": ROLE_LABELS[code],
            "description": ROLE_DESCRIPTIONS[code],
            "scope": RoleDefinition.Scope.WORKSPACE,
            "permissions": DEFAULT_ROLE_PERMISSIONS[code],
        },
    )
    return role


def ensure_roles() -> None:
    for code in ROLE_PRIORITY:
        get_role(code)


def invalidate(user) -> None:
    for attr in (_CODES_CACHE, _PERMS_CACHE):
        if hasattr(user, attr):
            try:
                delattr(user, attr)
            except AttributeError:  # lazy wrapper without the attribute
                pass


def membership_codes(user) -> list[str]:
    """Kode role milik user, urut dari yang paling berwenang."""
    if not getattr(user, "is_authenticated", False):
        return []
    cached = getattr(user, _CODES_CACHE, None)
    if cached is not None:
        return cached
    codes = set(
        Membership.objects.filter(user=user, status=Membership.Status.ACTIVE).values_list(
            "role__code", flat=True
        )
    )
    if user.is_staff:
        codes.add(Role.ADMIN)
    ordered = [code for code in ROLE_PRIORITY if code in codes]
    setattr(user, _CODES_CACHE, ordered)
    return ordered


def active_role(user) -> str:
    """Role aktif: pilihan sesi bila valid, selain itu role paling berwenang."""
    if not getattr(user, "is_authenticated", False):
        return ""
    codes = membership_codes(user)
    chosen = getattr(user, _ACTIVE_ATTR, None)
    if chosen in codes:
        return chosen
    # Akun lama tanpa membership bertindak sebagai Member.
    return codes[0] if codes else Role.MEMBER


def set_active_role(user, code: str) -> bool:
    """Pilih role aktif. Ditolak bila user tidak memilikinya (BR-ROLE-007)."""
    if code not in membership_codes(user):
        return False
    setattr(user, _ACTIVE_ATTR, code)
    return True


def role_permissions(user) -> frozenset:
    code = active_role(user)
    if not code:
        return frozenset()
    cache = getattr(user, _PERMS_CACHE, None)
    if cache is None:
        cache = {}
        setattr(user, _PERMS_CACHE, cache)
    if code not in cache:
        role = RoleDefinition.objects.filter(code=code).first() or get_role(code)
        cache[code] = frozenset(role.permissions)
    return cache[code]


def has_perm(user, permission: str) -> bool:
    return permission in role_permissions(user)


@transaction.atomic
def assign_roles(user, codes, *, assigned_by=None, workspace=None) -> None:
    """Samakan role user di workspace dengan ``codes`` (tambah yang baru, hapus sisanya)."""
    workspace = workspace or default_workspace()
    wanted = {code for code in codes if code in ROLE_LABELS}
    current = {
        m.role.code: m
        for m in Membership.objects.filter(user=user, workspace=workspace).select_related("role")
    }
    for code in wanted - set(current):
        Membership.objects.create(
            user=user, workspace=workspace, role=get_role(code), assigned_by=assigned_by
        )
    for code in set(current) - wanted:
        current[code].delete()
    for code in wanted & set(current):
        membership = current[code]
        if membership.status != Membership.Status.ACTIVE:
            membership.status = Membership.Status.ACTIVE
            membership.save(update_fields=["status"])
    invalidate(user)


def ensure_default_membership(user) -> None:
    """User baru tanpa role mendapat Member supaya bisa langsung dipakai."""
    if not Membership.objects.filter(user=user).exists():
        assign_roles(user, [Role.MEMBER])


def stored_role_codes(user) -> list[str]:
    """Role tersimpan (tanpa implisit ``is_staff``), untuk form edit user."""
    codes = set(
        Membership.objects.filter(user=user, status=Membership.Status.ACTIVE).values_list(
            "role__code", flat=True
        )
    )
    return [code for code in ROLE_PRIORITY if code in codes]
