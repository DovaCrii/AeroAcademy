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


def _chips(labels, x0, y=8, w=100, h=26, gap=34):
    """Cinta de pasos de la figura («DATOS → MODELO → AGENTE»): cajas con una flecha entre cada par."""
    texts = list(labels.get("chips", ()))
    out = []
    for k, text in enumerate(texts):
        x = x0 + k * (w + gap)
        out.append(
            {
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "cx": x + w // 2,
                "cy": y + h // 2,
                "text": text,
                "a1": x + w + 6,  # flecha hacia la caja siguiente
                "a2": x + w + gap - 6,
                "arrow": k < len(texts) - 1,
            }
        )
    return out


def _grid(n, per_row, pitch_x):
    """Centros (columna, fila, x) de una grilla centrada: `per_row` estaciones por fila."""
    per_row = max(1, min(n, per_row))
    x0 = (W - per_row * pitch_x) // 2 + pitch_x // 2
    return per_row, [(i % per_row, i // per_row, x0 + (i % per_row) * pitch_x) for i in range(n)]


def _pipeline(items, labels, pct):
    """Pipeline de IA: capas apiladas dentro de una ventana de contexto; cada una es una fila de 10 celdas (*tokens*)
    que se encienden con el avance. A la derecha, un medidor con el avance de toda la ruta."""
    n = len(items)
    top, pitch, band_h = 76, 44, 40
    for i, s in enumerate(items):
        y = top + (n - 1 - i) * pitch
        lit = -(-s["pct"] // 10)  # techo: 1 % ya enciende la primera celda
        s.update(
            y=y,
            mid=y + band_h // 2,
            label=clip(s["short"], 20),
            fill_w=round(450 * s["pct"] / 100),
            cells=[{"x": 412 + k * 16, "on": k < lit} for k in range(10)],
        )
        _marks(s, 632, y + band_h // 2)
    height = n * pitch - 4
    return {
        "w": W,
        "h": top + n * pitch + 16,
        "top": top,
        "band_h": band_h,
        "window_h": n * pitch + 12,
        "chips": _chips(labels, 140),
        "meter": {
            "x": 716,
            "y": top,
            "w": 18,
            "h": height,
            "fill_h": round(height * pct / 100),
            "fill_y": top + height - round(height * pct / 100),
        },
    }


def _cylinders(items, labels, pct):
    """Flujo de datos: un cilindro (tabla/base de datos) por etapa que se llena con el avance; tuberías entre ellos."""
    n = len(items)
    per_row, cells = _grid(n, 5, 152)
    top, pitch, body_h, rx, ry = 56, 150, 50, 28, 9
    for s, (col, row, cx) in zip(items, cells, strict=True):
        y0 = top + row * pitch
        fill_h = round(body_h * s["pct"] / 100)
        s.update(
            cx=cx,
            y0=y0,
            x0=cx - rx,
            x1=cx + rx,
            y_top=y0 + ry,
            y_bot=y0 + ry + body_h,
            fill_y=y0 + ry + body_h - fill_h,
            fill_h=fill_h,
            label=clip(s["short"], 18),
            ty_code=y0 + 84,
            ty_name=y0 + 100,
            ty_pct=y0 + 116,
            pipe_y=y0 + 34,
            pipe=col < per_row - 1 and s["idx"] < n - 1,
        )
        _marks(s, cx - 22, y0 + 134)
    rows = (n + per_row - 1) // per_row
    return {
        "w": W,
        "h": top + rows * pitch,
        "rx": rx,
        "ry": ry,
        "chips": _chips(labels, 90, w=110, gap=40),
    }


LAYOUTS = {"stack": _stack, "pipeline": _pipeline, "cylinders": _cylinders}
