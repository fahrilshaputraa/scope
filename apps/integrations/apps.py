from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.integrations"
    label = "integrations"
    verbose_name = "Integrasi Microsoft"

    def ready(self):
        from . import signals  # noqa: F401  (Teams event queue receivers)
