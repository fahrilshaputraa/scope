"""Symmetric encryption for integration secrets (webhook URLs, Graph tokens).

The key comes from ``INTEGRATIONS_ENCRYPTION_KEY`` (a Fernet key). Without it
the key is derived from ``SECRET_KEY``, so rotating ``SECRET_KEY`` makes stored
secrets unreadable: set a dedicated key in production.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet() -> Fernet:
    raw = getattr(settings, "INTEGRATIONS_ENCRYPTION_KEY", "") or ""
    if raw:
        return Fernet(raw.encode() if isinstance(raw, str) else raw)
    digest = hashlib.sha256(f"scope-integrations:{settings.SECRET_KEY}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(value: str) -> str:
    if not value:
        return ""
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    """Return the plaintext, or an empty string when the key no longer matches."""
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError):
        return ""
