"""«Próximo logro»: qué le falta a una persona para la siguiente insignia (y el título que trae) en las rutas.

Reutiliza las reglas de `rules.py` (`progress`) y el contexto de rutas de `game.py`; no calcula nada propio.
Solo cubre las insignias de avance en rutas (`rules.PROGRESS_TYPES`): lo demás ya tiene su pista en la vitrina.
"""

from . import game, rules
from .models import Badge, Title


def _missing_text(rule, done, total):
    left = total - done
    kind = rule["type"]
    if kind == "path_complete":
        return f"Te falta {left} % de la ruta"
    if kind == "paths_complete":
        return f"Te falta completar {left} ruta{'s' if left != 1 else ''} 101"
    if kind == "general_complete":
        return f"Completa {left} ruta{'s' if left != 1 else ''} de conocimiento general más"
    if kind == "quiz_correct":
        return f"Te falta{'n' if left != 1 else ''} {left} pregunta{'s' if left != 1 else ''} por acertar"
    return f"Te falta{'n' if left != 1 else ''} {left} paso{'s' if left != 1 else ''} del capítulo (misiones y preguntas)"


def next_goals(person, path=None, limit=2):
    """Logros de ruta aún sin ganar, del más cerca al más lejos.

    Con `path`, solo los que dependen de esa ruta. Cada uno trae `badge`, `done`, `total`, `pct`, `text`
    (qué falta) y `titles` (los títulos que desbloquea).
    """
    held = game.unlocked_badges(person)
    ctx = game.PathContext(person)
    rows = []
    for badge in Badge.objects.filter(retired=False):
        rule = badge.rule
        if rule.get("type") not in rules.PROGRESS_TYPES or badge.slug in held:
            continue
        if path is not None and not rules.touches(rule, path.slug, ctx):
            continue
        done, total = rules.progress(rule, ctx.pct, ctx)
        if done >= total:
            continue  # se otorga en la próxima evaluación
        rows.append(
            {
                "badge": badge,
                "done": done,
                "total": total,
                "pct": int(100 * done / total),
                "text": _missing_text(rule, done, total),
                "titles": [],
            }
        )
    rows.sort(key=lambda r: (-r["pct"], r["badge"].order))
    rows = rows[:limit]
    if rows:
        by_badge = {r["badge"].pk: r for r in rows}
        for title in Title.objects.filter(badge__in=by_badge, retired=False).order_by("order"):
            if not title.character_class or title.character_class == person.character_class:
                by_badge[title.badge_id]["titles"].append(title)
    return rows
