"""Pengaturan produksi: HTTPS, cookie aman, HSTS. Semua dapat diatur lewat env."""

import os

from .base import *  # noqa: F401,F403
from .base import env_bool

DEBUG = False

# Di belakang reverse proxy TLS: DJANGO_SECURE_PROXY_SSL_HEADER="HTTP_X_FORWARDED_PROTO,https"
_proxy = os.getenv("DJANGO_SECURE_PROXY_SSL_HEADER", "")
if _proxy and "," in _proxy:
    _name, _value = (part.strip() for part in _proxy.split(",", 1))
    SECURE_PROXY_SSL_HEADER = (_name, _value)

SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", True)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", True)
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", True)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
