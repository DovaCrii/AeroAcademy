from django.conf import settings

from .suite import SPONSOR_TEXT, SUITE_AERO


def brand(request):
    from apps.accounts.views import has_password_session

    return {
        "BRAND_PLATFORM": settings.BRAND_PLATFORM,
        "BRAND_ACADEMY": settings.BRAND_ACADEMY,
        "SUITE_AERO": SUITE_AERO,
        "SPONSOR_TEXT": SPONSOR_TEXT,
        "SHOW_SUITE_AERO": settings.SHOW_SUITE_AERO,
        # Sesión por contraseña (cambian textos de espera y cuenta); «Salir» está disponible para todas (D41).
        "password_session": bool(getattr(request, "user", None) and request.user.is_authenticated)
        and has_password_session(request),
    }
