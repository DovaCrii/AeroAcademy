from django.shortcuts import render

from . import services


def home(request):
    """Ventana de bienvenida. Contadores vivos y misión sugerida llegan con el Bloque 12b."""
    return render(request, "core/home.html", services.home_context(request.user))
