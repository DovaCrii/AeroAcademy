from . import services


def bell(request):
    """Campana de la cabecera: contador y los últimos avisos."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or getattr(user, "status", "approved") != "approved":
        return {}
    return {
        "bell": {
            "unread": services.unread_count(user),
            "items": services.recent(user, services.BELL_LIMIT),
        }
    }
