from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class Role(models.TextChoices):
    MANAGEMENT = "management", "Management"
    PROJECT_MANAGER = "pm", "Project Manager"
    MEMBER = "member", "Project Member"


class UserProfile(models.Model):
    """Profil user PCC: role akses + identitas SSO."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="pcc_profile")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
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
    def is_pm(self):
        return self.role == Role.PROJECT_MANAGER

    @property
    def is_management(self):
        return self.role == Role.MANAGEMENT


@receiver(post_save, sender=User)
def ensure_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


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
