from django.conf import settings

from .suite import SPONSOR_TEXT, SUITE_AERO


def brand(request):
    return {
        "BRAND_PLATFORM": settings.BRAND_PLATFORM,
        "BRAND_ACADEMY": settings.BRAND_ACADEMY,
        "SUITE_AERO": SUITE_AERO,
        "SPONSOR_TEXT": SPONSOR_TEXT,
    }
