from .navigation import nav_groups
from .permission_catalog import ROLE_LABELS
from .roles import active_role, has_perm, membership_codes


def workspace(request):
    """Role aktif, daftar role yang boleh dipilih, dan navigasi sidebar."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    role = active_role(user)
    return {
        "active_role": role,
        "active_role_label": ROLE_LABELS.get(role, ""),
        "available_roles": [
            {"code": code, "label": ROLE_LABELS[code], "active": code == role}
            for code in membership_codes(user)
        ],
        "nav_groups": nav_groups(role, request.path),
        "can_manage_users": has_perm(user, "user.manage"),
    }
