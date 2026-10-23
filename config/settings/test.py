from .base import *  # noqa: F401,F403

DEBUG = False

# Test: file static dilayani langsung tanpa whitenoise compression.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Test tidak boleh mengirim email nyata.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
SITE_URL = "http://testserver"
