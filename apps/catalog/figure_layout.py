"""Geometría de las figuras (docs/MEJORAS_UX.md P1-9): pura, sin consultas, con coordenadas enteras.

Las plantillas de `worlds/figures/*.html` solo dibujan lo que sale de aquí. Todo es entero o texto ya formateado: con
el idioma en español, Django escribiría `12,5` en un atributo SVG y rompería el dibujo. El texto largo se recorta
(`clip`) para caber en su caja; el nombre completo va en `<title>` y en el `aria-label`.

Una *estación* es la unidad que dibuja la figura: un nivel en las rutas estructuradas y un curso en las externas
(varias solo tienen un capítulo). Su forma común (`station`) la arman `progress.services` y `progress.external`.
"""

import math

W = 760  # ancho común del lienzo (viewBox 0 0 760 H)


def clip(text, limit):
    """Texto recortado con «…» para que una etiqueta no se salga de su caja (el nombre completo va en `title`)."""
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: max(limit - 1, 1)].rstrip() + "…"


def station(code, name, pct, complete, *, fid, say, noun, marks=(), extra=0, alias=""):
    """Estación de una figura. `say` es el estado dicho en palabras para el `aria-label`; `alias`, el nombre corto
    del rótulo (el completo va en `<title>` y en el `aria-label`)."""
    return {
        "code": code,
        "short": name,
        "alias": alias,
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
    items, seen = [], False
    for i, s in enumerate(stations):
        # En rutas externas varias estaciones comparten capítulo: solo la primera marca «estás aquí».
        here = s["code"] == current_code and not seen
        seen = seen or here
        items.append({**s, "idx": i, "current": here})
    out = fn(items, labels or {}, pct)
    done = sum(1 for s in items if s["complete"])
    return {"items": items, "total": len(items), "done": done, "pct": pct, **out}


def _marks(s, mx, my, limit=3):
    """Ancla de las marcas del equipo: (mx, my) es el centro de la primera; las siguientes van 22 px a la derecha.

    Con un `limit` menor se muestran menos iniciales y el resto se suma a «+n» (figuras apretadas).
    """
    s["mx"], s["my"] = mx, my
    shown = s["marks"][:limit]
    s["extra"] += len(s["marks"]) - len(shown)
    s["marks"] = [{**m, "dx": 22 * k} for k, m in enumerate(shown)]
    s["more_dx"] = 22 * len(shown)


def _stack(items, labels, pct):
    """Pila de capas sin cotas: una banda por estación, la primera abajo."""
    n = len(items)
    top, pitch = 22, 46
    for i, s in enumerate(items):
        y = top + (n - 1 - i) * pitch
        s.update(
            y=y,
            mid=y + 22,
            label=clip(s["alias"] or s["short"], 34),
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


def _grid(n, max_per_row, pitch_x):
    """Centros (columna, fila, x) de una grilla centrada y equilibrada (6 estaciones: 3 + 3, no 5 + 1)."""
    rows = max(1, -(-n // max_per_row))
    per_row = max(1, -(-n // rows))
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
            label=clip(s["alias"] or s["short"], 20),
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
            label=clip(s["alias"] or s["short"], 18),
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


def _survey(items, labels, pct):
    """Perfil topográfico: una estación por punto de referencia (PR) sobre el terreno, con su caída al datum.

    El tramo entre dos PR es trazo firme cuando el primero está levantado y punteado si falta. Los rótulos se alternan
    en dos alturas para que quepan aun con 13 puntos.
    """
    n = len(items)
    left, right, datum = 70, 690, 262
    step = (right - left) / (n - 1) if n > 1 else 0
    chars = max(8, min(18, int((2 * step - 12) / 7.8))) if n > 1 else 18
    for i, s in enumerate(items):
        x = round(left + step * i) if n > 1 else W // 2
        y = round(150 + 34 * math.sin(i * 1.3) + 12 * math.cos(i * 2.9))
        s.update(
            x=x,
            y=y,
            tri=f"{x},{y - 14} {x - 10},{y + 4} {x + 10},{y + 4}",
            label=clip(s["alias"] or s["short"], chars),
            ty_name=38
            + (i % 2) * 26,  # dos filas fijas de rótulos, con un trazo hasta el triángulo
            lead_y1=44 + (i % 2) * 26,
            lead_y2=y - 17,
            ty_pct=y + 24,
            drop_y=y + 5,
        )
        _marks(s, x - 11, y + 46, 3 if step >= 66 else 1)
    segments = [
        {"x1": a["x"], "y1": a["y"], "x2": b["x"], "y2": b["y"], "done": a["complete"]}
        for a, b in zip(items, items[1:], strict=False)
    ]
    ground = " ".join(f"{s['x']},{s['y']}" for s in items)
    return {
        "w": W,
        "h": 316,
        "datum": datum,
        "segments": segments,
        "ground": f"{items[0]['x']},{datum} {ground} {items[-1]['x']},{datum}" if items else "",
        "ticks": [100, 140, 180, 220],
    }


def _tiles(items, labels, pct):
    """Del escaneo al gemelo: cada fase es un recuadro de 5 × 5 puntos que se encienden con el avance (nube); al
    completarla se le traza la malla y se enciende el sensor."""
    n = len(items)
    per_row, cells = _grid(n, 5, 152)
    top, pitch, side = 56, 168, 84
    for s, (_col, row, cx) in zip(items, cells, strict=True):
        y0 = top + row * pitch
        lit = -(-25 * s["pct"] // 100)
        dots = [
            {"x": cx - 28 + c * 14, "y": y0 + 14 + r * 14, "on": r * 5 + c < lit}
            for r in range(5)
            for c in range(5)
        ]
        mesh = " ".join(
            [f"M{cx - 28} {y0 + 14 + k * 14}H{cx + 28}" for k in range(5)]
            + [f"M{cx - 28 + k * 14} {y0 + 14}V{y0 + 70}" for k in range(5)]
            + [f"M{cx - 28 + k * 14} {y0 + 14}l14 14" for k in range(4)]
        )
        s.update(
            cx=cx,
            y0=y0,
            x0=cx - side // 2,
            side=side,
            dots=dots,
            mesh=mesh if s["complete"] else "",
            sensor_x=cx + side // 2 - 10,
            sensor_y=y0 + 10,
            label=clip(s["alias"] or s["short"], 18),
            ty_code=y0 + 106,
            ty_name=y0 + 122,
            ty_pct=y0 + 138,
        )
        _marks(s, cx - 22, y0 + 156)
    rows = (n + per_row - 1) // per_row
    return {"w": W, "h": top + rows * pitch, "chips": _chips(labels, 74, w=100, gap=28)}


def _iso(items, labels, pct):
    """Isométrico de tuberías: la línea sube y baja a 30°; cada tramo es una válvula (bowtie) que se abre al completarlo.
    El tramo de tubería hacia la válvula siguiente se pinta cuando la anterior está lista (fluye)."""
    n = len(items)
    spacing = min(110, 620 // max(n - 1, 1)) if n > 1 else 0
    dy = round(spacing * 0.577)
    x_start = (W - spacing * (n - 1)) // 2
    chars = max(8, min(18, int((2 * spacing - 12) / 7.8))) if n > 1 else 18
    low = 214
    for i, s in enumerate(items):
        x = x_start + spacing * i
        up = i % 2 == 1
        y = low - dy if up else low
        s.update(
            x=x,
            y=y,
            valve=f"M{x - 10} {y - 8}L{x + 10} {y + 8}V{y - 8}L{x - 10} {y + 8}Z",
            wheel=f"M{x - 6} {y - 20}H{x + 6}M{x} {y - 8}V{y - 20}",
            label=clip(s["alias"] or s["short"], chars),
            ty_name=y - 40 if up else y + 40,
            ty_meta=y - 26 if up else y + 56,
        )
        _marks(s, x - 11, y + 28 if up else y + 76, 3 if spacing >= 66 else 1)
    pipes = [
        {"x1": a["x"], "y1": a["y"], "x2": b["x"], "y2": b["y"], "done": a["complete"]}
        for a, b in zip(items, items[1:], strict=False)
    ]
    return {"w": W, "h": 310, "pipes": pipes, "chips": _chips(labels, 296, w=80, gap=40)}


def _lanes(items, labels, pct):
    """Flujo de documentos: tres carriles (WIP, Compartido, Publicado); cada documento está en el carril de su avance:
    sin empezar → WIP, en curso → Compartido, completo → Publicado."""
    names = list(labels.get("lanes", ("WIP", "Compartido", "Publicado")))
    lane_w, gap, top, pitch = 226, 20, 50, 62
    count = [0] * len(names)
    for s in items:
        lane = 2 if s["complete"] else 1 if s["started"] else 0
        x = 20 + lane * (lane_w + gap)
        y = top + count[lane] * pitch
        count[lane] += 1
        s.update(
            lane=lane,
            x=x,
            y=y,
            w=lane_w,
            bar_w=round((lane_w - 20) * s["pct"] / 100),
            label=clip(s["alias"] or s["short"], 22),
            page=f"M{x + 12} {y + 12}h12l6 6v18h-18z",
            fold=f"M{x + 24} {y + 12}v6h6",
        )
        _marks(s, x + lane_w - 46, y + 24, 2)
    heads = [
        {
            "x": 20 + k * (lane_w + gap),
            "w": lane_w,
            "text": text,
            "cx": 20 + k * (lane_w + gap) + lane_w // 2,
            "a1": 20 + k * (lane_w + gap) + lane_w + 3,
            "a2": 20 + k * (lane_w + gap) + lane_w + gap - 3,
            "arrow": k < len(names) - 1,
        }
        for k, text in enumerate(names)
    ]
    return {"w": W, "h": max(170, top + max(count) * pitch + 8), "heads": heads}


LAYOUTS = {
    "iso": _iso,
    "lanes": _lanes,
    "stack": _stack,
    "pipeline": _pipeline,
    "cylinders": _cylinders,
    "survey": _survey,
    "tiles": _tiles,
}
