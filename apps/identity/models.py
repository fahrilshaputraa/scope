from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class Role(models.TextChoices):
    """Kode role (PRD §3). Definisi dan permission-nya ada di ``RoleDefinition``."""

    ADMIN = "admin", "Workspace Admin"
    PROJECT_MANAGER = "pm", "Project Manager"
    MEMBER = "member", "Project Member"
    OWNER = "owner", "Project Owner"
    CLIENT = "client", "Client / Stakeholder"
    MANAGEMENT = "management", "Management"


class Workspace(models.Model):
    """Ruang kerja organisasi (PRD §26.2). Saat ini UI memakai satu workspace."""

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=40, unique=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, default="active")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class RoleDefinition(models.Model):
    """Role beserta daftar permission-nya (PRD §26.4)."""

    class Scope(models.TextChoices):
        WORKSPACE = "workspace", "Workspace"
        PROJECT = "project", "Project"

    code = models.CharField(max_length=20, unique=True, choices=Role.choices)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    scope = models.CharField(max_length=20, choices=Scope.choices, default=Scope.WORKSPACE)
    permissions = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.name

    def has_permission(self, code: str) -> bool:
        return code in self.permissions


class Membership(models.Model):
    """Satu user bisa memiliki banyak role per workspace (PRD §26.3)."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Aktif"
        INACTIVE = "inactive", "Nonaktif"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="memberships")
    role = models.ForeignKey(RoleDefinition, on_delete=models.PROTECT, related_name="memberships")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["user_id", "role__code"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "workspace", "role"], name="unique_user_workspace_role"
            )
        ]

    def __str__(self):
        return f"{self.user_id}:{self.role_id}@{self.workspace_id}"


class UserProfile(models.Model):
    """Profil user PCC: identitas SSO. Role ada di ``Membership``."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="pcc_profile")
    sso_subject = models.CharField(max_length=255, blank=True, db_index=True)
    display_name = models.CharField(max_length=200, blank=True)
    job_title = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__first_name", "user__username"]

    def __str__(self):
        return f"{self.name} ({self.get_role_display()})"

    @property
    def name(self):
        return self.display_name or self.user.get_full_name() or self.user.username

    @property
    def role(self) -> str:
        """Kode role aktif user (bawaan: role paling berwenang)."""
        from .roles import active_role

        return active_role(self.user)

    @property
    def role_labels(self) -> list[str]:
        """Label seluruh role user (termasuk Admin implisit dari ``is_staff``)."""
        from .permission_catalog import ROLE_LABELS
        from .roles import membership_codes

        return [ROLE_LABELS[code] for code in membership_codes(self.user)] or [
            ROLE_LABELS[Role.MEMBER]
        ]

    def get_role_display(self) -> str:
        from .permission_catalog import ROLE_LABELS

        return ROLE_LABELS.get(self.role, "Project Member")


@receiver(post_save, sender=User)
def ensure_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)
        from .roles import ensure_default_membership

        ensure_default_membership(instance)


def sync_profile_from_claims(user, claims):
    """Update profil dari claims OIDC (Entra ID)."""
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.sso_subject = str(claims.get("sub") or claims.get("oid") or "")
    name = claims.get("name") or ""
    if name:
        profile.display_name = name
        parts = name.split(" ", 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ""
    email = claims.get("email") or claims.get("preferred_username") or ""
    if email:
        user.email = email
    profile.job_title = claims.get("job_title") or profile.job_title
    profile.save()
    user.save()
    return profile
