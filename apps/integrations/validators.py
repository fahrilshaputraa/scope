"""Teams webhook URL validation.

Only HTTPS URLs on Microsoft-hosted webhook domains are accepted, so a stored
URL can never be used to make the server call an arbitrary or internal host.
"""

import ipaddress
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError

#: Host suffixes for Teams Incoming Webhook (legacy connector) and
#: Workflows / Power Automate "When a Teams webhook request is received".
ALLOWED_HOST_SUFFIXES = (
    ".webhook.office.com",
    ".logic.azure.com",
    ".powerplatform.com",
)


def is_allowed_host(host: str) -> bool:
    host = (host or "").lower().rstrip(".")
    return any(
        host.endswith(suffix) and len(host) > len(suffix) for suffix in ALLOWED_HOST_SUFFIXES
    )


def validate_webhook_url(value: str) -> str:
    """Return the cleaned URL or raise ``ValidationError`` with an Indonesian message."""
    url = (value or "").strip()
    if not url:
        raise ValidationError("URL webhook wajib diisi.")
    if len(url) > 2000:
        raise ValidationError("URL webhook terlalu panjang.")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise ValidationError("URL webhook tidak valid.") from exc
    if parts.scheme != "https":
        raise ValidationError("URL webhook harus memakai https://.")
    if parts.username or parts.password:
        raise ValidationError("URL webhook tidak boleh memuat kredensial.")
    if port not in (None, 443):
        raise ValidationError("URL webhook harus memakai port standar 443.")
    host = parts.hostname or ""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValidationError("URL webhook harus memakai nama domain Microsoft, bukan IP.")
    if not is_allowed_host(host):
        raise ValidationError(
            "Host tidak dikenali. Gunakan URL dari Teams (*.webhook.office.com) atau "
            "Workflows/Power Automate (*.logic.azure.com, *.powerplatform.com)."
        )
    if not parts.path or parts.path == "/":
        raise ValidationError("URL webhook tidak lengkap.")
    return url


def mask_url(url: str) -> str:
    """Short, non-secret hint shown in the UI: host plus the last four characters."""
    if not url:
        return ""
    host = urlsplit(url).hostname or ""
    return f"{host}/…{url[-4:]}"
