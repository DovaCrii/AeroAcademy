from django.apps import AppConfig


class CredentialsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.credentials"

    def ready(self):
        from . import signals  # noqa: F401  (registra el borrado del archivo)
