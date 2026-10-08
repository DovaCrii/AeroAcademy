from . import game


def player(request):
    """Nivel, XP y título para la cabecera, más lo que aún no se le celebró a la persona."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or getattr(user, "status", "approved") != "approved":
        return {}
    info = game.level_info(user)
    return {
        "player": {
            **info,
            "title": game.displayed_title(user, info["level"]),
            **game.celebrations(user, info["level"]),
        }
    }
