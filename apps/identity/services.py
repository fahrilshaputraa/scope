from django.contrib.auth.models import User

from .models import UserProfile, sync_profile_from_claims


def upsert_user_from_claims(claims) -> User:
    """Cari user dari claims OIDC; buat bila belum ada.

    Urutan pencarian: sso_subject → email → baru dibuat.
    """
    subject = str(claims.get("sub") or claims.get("oid") or "")
    user = None
    if subject:
        profile = UserProfile.objects.filter(sso_subject=subject).select_related("user").first()
        if profile:
            user = profile.user
    if user is None:
        email = (claims.get("email") or claims.get("preferred_username") or "").strip()
        if email:
            user = User.objects.filter(email__iexact=email).first()
    if user is None:
        email = (claims.get("email") or claims.get("preferred_username") or "").strip()
        base = email or subject or "user"
        username = base
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base}{counter}"
            counter += 1
        user = User.objects.create(username=username, email=email)
    sync_profile_from_claims(user, claims)
    return user
