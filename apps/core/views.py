from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from . import services


def home(request):
    """Ventana de bienvenida. Contadores vivos y misión sugerida llegan con el Bloque 12b."""
    return render(request, "core/home.html", services.home_context(request.user))


def healthz(request):
    """Estado del servicio para el instalador y el monitoreo (solo responde a peticiones del proxy local)."""
    with connection.cursor() as cur:
        cur.execute("SELECT 1")
    return JsonResponse({"ok": True})
