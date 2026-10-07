from .base import *  # noqa: F401,F403

DEBUG = True

# Development memakai static bawaan runserver (tanpa collectstatic).
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
