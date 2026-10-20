"""Registro de por dónde entra cada persona (D42): un receptor de `user_logged_in`.

Guarda solo la fecha de la última entrada por cada vía (Tailscale, contraseña o puerta pública), sin IP ni navegador.
Si algo falla al guardarla, se anota el tipo de error y la persona entra igual: esto nunca puede impedir un acceso.
"""

import logging

from django.contrib.auth import BACKEND_SESSION_KEY
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import timezone

from .models import LoginTrace

logger = logging.getLogger("apps.accounts")

TAILSCALE_BACKEND = "apps.accounts.backends.TailscaleBackend"


def trace_field(request) -> str:
    """Qué campo de `LoginTrace` corresponde a esta entrada. La puerta pública manda sobre el backend."""
    if getattr(request, "public_door", False):
        return "last_public_at"
    session = getattr(request, "session", None)
    backend = session.get(BACKEND_SESSION_KEY, "") if session is not None else ""
    return "last_tailscale_at" if backend == TAILSCALE_BACKEND else "last_password_at"


@receiver(user_logged_in, dispatch_uid="accounts.login_trace")
def record_login(sender, request, user, **kwargs):
    if request is None or not getattr(user, "pk", None):
        return
    field = {trace_field(request): timezone.now()}
    try:
        # Una sola consulta cuando ya hay fila (lo normal); la primera vez, además, un INSERT. Sin transacción propia:
        # esto corre en la petición de entrada y no debe sumarle viajes a la base.
        if not LoginTrace.objects.filter(person=user).update(**field):
            LoginTrace.objects.create(person=user, **field)
    except Exception as exc:  # noqa: BLE001 - el registro nunca impide entrar
        logger.warning("No se pudo registrar la vía de entrada (%s)", type(exc).__name__)
