import logging
from urllib.parse import urlparse

from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from . import services

logger = logging.getLogger("apps.core")


def home(request):
    """Ventana de bienvenida. Contadores vivos y misión sugerida llegan con el Bloque 12b."""
    return render(request, "core/home.html", services.home_context(request.user))


def healthz(request):
    """Estado del servicio para el instalador y el monitoreo (solo responde a peticiones del proxy local)."""
    with connection.cursor() as cur:
        cur.execute("SELECT 1")
    return JsonResponse({"ok": True})


def _referer_path(request) -> str:
    """Solo la ruta del referente y solo si es de este sitio (nada de query ni hosts externos)."""
    referer = request.META.get("HTTP_REFERER", "")
    if not referer:
        return "-"
    parsed = urlparse(referer)
    if parsed.netloc and parsed.netloc != request.get_host():
        return "-"
    return (parsed.path or "/")[:200]


def not_found(request, exception=None):
    """404 propia. Mismo texto para «no existe» y «no tienes acceso» (no revela qué existe).

    Se registra la ruta (sin query) y el origen interno, solo de personas con sesión y sin ningún dato personal.
    """
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        logger.info("404 %s ref=%s", request.path[:200], _referer_path(request))
    return render(request, "core/404.html", status=404)


def forbidden(request, exception=None):
    return render(request, "core/403.html", status=403)
