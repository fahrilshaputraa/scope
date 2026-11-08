import os
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parents[2]

DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG or os.getenv("DJANGO_SETTINGS_MODULE", "").endswith((".development", ".test")):
        SECRET_KEY = "dev-only-unsafe-secret"
    else:
        from django.core.exceptions import ImproperlyConfigured

        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY wajib diisi saat DJANGO_DEBUG=false (produksi)."
        )
ALLOWED_HOSTS = [
    host for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host
]
CSRF_TRUSTED_ORIGINS = [
    origin for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if origin
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.identity.apps.IdentityConfig",
    "apps.projects.apps.ProjectsConfig",
    "apps.work.apps.WorkConfig",
    "apps.notifications.apps.NotificationsConfig",
    "apps.integrations.apps.IntegrationsConfig",
    "apps.governance.apps.GovernanceConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.identity.middleware.ActiveRoleMiddleware",
    "apps.projects.middleware.RevisionActorMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context_processors.settings",
                "apps.identity.context_processors.workspace",
                "apps.notifications.context_processors.notifications",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


def database_config():
    raw = os.getenv("DATABASE_URL")
    if not raw:
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
    parsed = urlparse(raw)
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parsed.path.lstrip("/"),
        "USER": parsed.username,
        "PASSWORD": parsed.password,
        "HOST": parsed.hostname,
        "PORT": parsed.port or 5432,
        "CONN_MAX_AGE": 60,
    }


DATABASES = {"default": database_config()}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "id"
TIME_ZONE = "Asia/Jakarta"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "identity:login"
LOGIN_REDIRECT_URL = "projects:dashboard"
LOGOUT_REDIRECT_URL = "identity:login"
SESSION_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# --- Login lockout (cache-based, per username+IP) ---
LOGIN_MAX_FAILURES = int(os.getenv("PCC_LOGIN_MAX_FAILURES", "5"))
LOGIN_LOCKOUT_SECONDS = int(os.getenv("PCC_LOGIN_LOCKOUT_SECONDS", "600"))
X_FRAME_OPTIONS = "DENY"

# --- Microsoft Entra ID (OIDC via Authlib) ---
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "")
AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "")
AZURE_SCOPES = "openid profile email"
AZURE_METADATA_URL = (
    "https://login.microsoftonline.com/"
    f"{AZURE_TENANT_ID or 'common'}/v2.0/.well-known/openid-configuration"
)
AZURE_ENABLED = bool(AZURE_CLIENT_ID and AZURE_CLIENT_SECRET)


# --- Progress variance thresholds (persen) ---
#   variance >= 0            -> Ahead / On Track
#   variance >= AT_RISK      -> At Risk
#   else                     -> Delayed
PROGRESS_AT_RISK_THRESHOLD = float(os.getenv("PCC_AT_RISK_THRESHOLD", "-1"))
PROGRESS_DELAYED_THRESHOLD = float(os.getenv("PCC_DELAYED_THRESHOLD", "-5"))
# Selisih plan vs actual yang masih dianggap "On Track" (|variance| <= eps)
PROGRESS_ON_TRACK_EPSILON = float(os.getenv("PCC_ON_TRACK_EPSILON", "1"))

# Local username/password is the default authentication method.

# --- Snapshot scheduler internal (H6) ---
# Default mati. Nyalakan hanya pada satu opsi deployment: thread internal atau
# systemd timer. Tick bersifat idempoten per project per hari.
SCOPE_SCHEDULER_ENABLED = os.getenv("SCOPE_SCHEDULER_ENABLED", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
try:
    SCOPE_SCHEDULER_INTERVAL_MINUTES = float(
        os.getenv("SCOPE_SCHEDULER_INTERVAL_MINUTES", "60")
    )
except ValueError:
    SCOPE_SCHEDULER_INTERVAL_MINUTES = 60.0


# --- Email delivery (B2) ---
# Default lokal: cetak email ke console. Deployment mengatur SMTP lewat env.
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "Scope <no-reply@localhost>")
# URL publik tanpa request; dipakai untuk deep link absolut di email.
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000").rstrip("/")

# --- Integrasi Microsoft Teams & Outlook (docs/integrations.md) ---
# Kunci Fernet untuk URL webhook dan token Graph; kosong = diturunkan dari SECRET_KEY.
INTEGRATIONS_ENCRYPTION_KEY = os.getenv("INTEGRATIONS_ENCRYPTION_KEY", "")
TEAMS_NOTIFICATIONS_ENABLED = os.getenv("TEAMS_NOTIFICATIONS_ENABLED", "true").strip().lower() in {
    "1", "true", "yes", "on",
}
TEAMS_REQUEST_TIMEOUT = float(os.getenv("TEAMS_REQUEST_TIMEOUT", "10"))
TEAMS_DAILY_SUMMARY_HOUR = int(os.getenv("TEAMS_DAILY_SUMMARY_HOUR", "8"))
TEAMS_MILESTONE_DUE_DAYS = int(os.getenv("TEAMS_MILESTONE_DUE_DAYS", "3"))
# Microsoft Graph (Calendars.ReadWrite) hanya aktif bila AZURE_ENABLED dan flag ini true.
OUTLOOK_GRAPH_ENABLED = os.getenv("OUTLOOK_GRAPH_ENABLED", "false").strip().lower() in {
    "1", "true", "yes", "on",
}


def env_bool(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": os.getenv("DJANGO_LOG_LEVEL", "INFO")},
}
