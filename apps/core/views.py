from django.shortcuts import render


def home(request):
    """Portada provisoria del Bloque 0; la portada real llega en el Bloque 12."""
    return render(request, "core/home.html")
