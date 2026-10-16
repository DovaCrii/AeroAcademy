"""Geometría de las figuras (docs/MEJORAS_UX.md P1-9): pura, sin consultas, con coordenadas enteras.

Las plantillas de `worlds/figures/*.html` solo dibujan lo que sale de aquí. Todo es entero o texto ya formateado: con
el idioma en español, Django escribiría `12,5` en un atributo SVG y rompería el dibujo. El texto largo se recorta
(`clip`) para caber en su caja; el nombre completo va en `<title>` y en el `aria-label`.

Una *estación* es la unidad que dibuja la figura: un nivel en las rutas estructuradas y un curso en las externas
(varias solo tienen un capítulo). Su forma común (`station`) la arman `progress.services` y `progress.external`.
"""

W = 760  # ancho común del lienzo (viewBox 0 0 760 H)


def clip(text, limit):
    """Texto recortado con «…» para que una etiqueta no se salga de su caja (el nombre completo va en `title`)."""
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: max(limit - 1, 1)].rstrip() + "…"


def station(code, name, pct, complete, *, fid, say, noun, marks=(), extra=0):
    """Estación de una figura. `say` es el estado dicho en palabras para el `aria-label`."""
    return {
        "code": code,
        "short": name,
        "pct": pct,
        "complete": complete,
        "fid": fid,
        "say": say,
        "noun": noun,
        "marks": list(marks),
        "extra": extra,
        "current": False,
        "started": pct > 0,
    }


def layout(kind, stations, *, current_code=None, labels=None, pct=0):
    """Geometría de la figura `kind` (`Figure.layout`) para estas estaciones, o None si la figura usa otra fuente.

    `building`, `road-profile` y `flight-plan` se dibujan con `_floors`, `_journey` y `_waypoints`.
    """
    fn = LAYOUTS.get(kind)
    if fn is None:
        return None
    items = [{**s, "idx": i, "current": s["code"] == current_code} for i, s in enumerate(stations)]
    out = fn(items, labels or {}, pct)
    done = sum(1 for s in items if s["complete"])
    return {"items": items, "total": len(items), "done": done, "pct": pct, **out}


def _marks(s, mx, my):
    """Ancla de las marcas del equipo: (mx, my) es el centro de la primera; las siguientes van 22 px a la derecha."""
    s["mx"], s["my"] = mx, my
    s["marks"] = [{**m, "dx": 22 * k} for k, m in enumerate(s["marks"])]
    s["more_dx"] = 22 * len(s["marks"])


def _stack(items, labels, pct):
    """Pila de capas sin cotas: una banda por estación, la primera abajo."""
    n = len(items)
    top, pitch = 22, 46
    for i, s in enumerate(items):
        y = top + (n - 1 - i) * pitch
        s.update(
            y=y,
            mid=y + 22,
            label=clip(s["short"], 34),
            fill_w=round(380 * s["pct"] / 100),
        )
        _marks(s, 560, y + 18)
    return {"w": W, "h": top + n * pitch + 18}


LAYOUTS = {"stack": _stack}
