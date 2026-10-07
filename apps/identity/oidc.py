from functools import lru_cache

from authlib.integrations.django_client import OAuth
from django.conf import settings


@lru_cache(maxsize=1)
def get_entra_client():
    """Authlib client untuk Microsoft Entra ID (authorization code + PKCE)."""
    oauth = OAuth()
    oauth.register(
        name="entra",
        client_id=settings.AZURE_CLIENT_ID,
        client_secret=settings.AZURE_CLIENT_SECRET,
        server_metadata_url=settings.AZURE_METADATA_URL,
        client_kwargs={
            "scope": settings.AZURE_SCOPES,
            "code_challenge_method": "S256",
        },
    )
    return oauth.create_client("entra")
