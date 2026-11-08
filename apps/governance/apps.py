from django.apps import AppConfig


class GovernanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.governance"
    label = "governance"
    verbose_name = "Tata kelola (approval, change request, deliverable)"

    def ready(self):
        from . import changes  # noqa: F401  (mendaftarkan handler change request/deliverable)
