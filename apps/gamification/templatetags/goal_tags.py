from django import template

from .. import goals

register = template.Library()


@register.inclusion_tag("gamification/_next_goal.html", takes_context=True)
def next_goal(context, path=None, limit=1):
    """«Próximo logro» de la persona que mira: en una ruta (`{% next_goal path %}`) o en general.

    Solo se calcula para quien está conectado (nunca para otra persona) y no pinta nada si no hay logro pendiente.
    """
    user = context.get("user") or getattr(context.get("request"), "user", None)
    if user is None or not getattr(user, "pk", None):
        return {"goals": []}
    return {"goals": goals.next_goals(user, path=path, limit=limit)}
