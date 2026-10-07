from .base import *  # noqa: F401,F403

DEBUG = False

# Test: file static dilayani langsung tanpa whitenoise compression.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
