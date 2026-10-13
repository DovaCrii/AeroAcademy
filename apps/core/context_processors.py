from django.conf import settings

from .suite import SPONSOR_TEXT, SUITE_AERO


def brand(request):
    from apps.accounts.views import has_password_session

    return {
        "BRAND_PLATFORM": settings.BRAND_PLATFORM,
        "BRAND_ACADEMY": settings.BRAND_ACADEMY,
        "SUITE_AERO": SUITE_AERO,
        "SPONSOR_TEXT": SPONSOR_TEXT,
        # «Salir» solo tiene efecto en sesiones con contraseña: quien entra por Tailscale vuelve a entrar al instante.
        "password_session": bool(getattr(request, "user", None) and request.user.is_authenticated)
        and has_password_session(request),
    }
