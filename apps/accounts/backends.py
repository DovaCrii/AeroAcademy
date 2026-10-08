from django.contrib.auth.backends import RemoteUserBackend

from . import services


class TailscaleBackend(RemoteUserBackend):
    """Crea la persona la primera vez que Tailscale la presenta (queda `pending`)."""

    def clean_username(self, username):
        return services.normalize_login(username)

    def configure_user(self, request, user, created=True):
        # Django 5.2 llama a este método en cada autenticación, no solo al crear la persona:
        # reiniciar el rol aquí degradaría a un lead o admin cada vez que inicia sesión.
        return services.init_new_person(user) if created else user
