"""Guías rápidas por nivel de ruta: viven en seed/rutas/<slug>.json (clave `guide` de cada nivel), versionadas."""

import json
import re
from pathlib import Path

from django.conf import settings
from django.templatetags.static import static
from django.urls import reverse

from apps.core import private_files

_CACHE = {}
# Infografías por nivel (clave `images` del nivel en la semilla): solo SVG estáticos propios.
_IMAGE = re.compile(r"^core/img/[a-z0-9_/-]+\.svg$")


_SLUG = re.compile(r"^[A-Za-z0-9_-]{1,60}$")


def _route_file(slug):
    """JSON de la ruta: `seed/rutas/<slug>.json` y, si no existe, el de la carpeta privada de cursos."""
    if not isinstance(slug, str) or not _SLUG.match(slug):
        return None
    seed = Path(settings.BASE_DIR) / "seed" / "rutas" / f"{slug}.json"
    if seed.is_file():
        return seed
    private = Path(settings.PRIVATE_COURSES_DIR) / slug / "ruta.json"
    return private if private.is_file() else None


def _route_json(slug):
    file = _route_file(slug)
    if file is None:
        return {}
    try:
        stamp = (str(file), file.stat().st_mtime_ns)
    except OSError:
        return {}
    cached = _CACHE.get(slug)
    if cached and cached[0] == stamp:
        return cached[1]
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    _CACHE[slug] = (stamp, data)
    return data


# --- diapositivas (clave `slides` del nivel): solo presentación, no tocan códigos ni claves de avance ----------------

CALLOUTS = {
    "dato": "Dato",
    "ojo": "Ojo con esto",
    "ejemplo": "Ejemplo",
    "en-terreno": "En terreno",
}
MAX_SLIDES = 30
_PRIV = "priv:"


def photo_path(slug, name):
    """Ruta segura de una foto privada del curso (`<PRIVATE_COURSES_DIR>/<slug>/fotos/<name>`), o None."""
    if not isinstance(slug, str) or not _SLUG.match(slug):
        return None
    return private_files.safe_file(Path(settings.PRIVATE_COURSES_DIR) / slug / "fotos", name)


def _text(value, limit):
    return value.strip()[:limit] if isinstance(value, str) else ""


def _strings(value, limit, cap):
    if not isinstance(value, list):
        return []
    return [t for t in (_text(v, cap) for v in value) if t][:limit]


DIAGRAM_KINDS = {
    "equipo": "Equipo",
    "dato": "Dato",
    "proceso": "Proceso",
    "producto": "Producto",
    "persona": "Persona",
}
MAX_NODES, MAX_EDGES, MAX_STEPS = 12, 16, 12
_ID = re.compile(r"^[a-z0-9_-]{1,24}$")
# Tarjeta de 22 % × 15 % del lienzo 16:9 (viewBox 160 × 90): las flechas nacen y terminan en su borde.
NODE_W, NODE_H = 22.0, 15.0


def _num(value, default):
    if isinstance(value, bool) or not isinstance(value, int | float):
        return default
    return min(100.0, max(0.0, float(value)))


def _edge_point(a, b):
    """Punto del borde de la tarjeta `a` en dirección a `b` (coordenadas en %), para no dibujar bajo la tarjeta."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == 0 and dy == 0:
        return a
    t = min(
        (NODE_W / 2) / abs(dx) if dx else float("inf"),
        (NODE_H / 2) / abs(dy) if dy else float("inf"),
        0.5,
    )
    return a[0] + dx * t, a[1] + dy * t


def _diagram(raw):
    """Diagrama de tarjetas y flechas de una diapositiva (clave `diagram`), validado, o None.

    Nodos: id, label, sub, kind, x, y (centro, en % de un lienzo 16:9). Aristas: from, to, label, flow (punto que viaja).
    `steps`: grupos de ids (de nodos o de aristas `<from>-<to>`) que aparecen de a uno; lo que no figura en ningún grupo
    se ve desde el inicio. Sin `steps` todo se ve. Lo inválido se ignora; tope de 12 nodos y 16 aristas.
    """
    if not isinstance(raw, dict) or not isinstance(raw.get("nodes"), list):
        return None
    nodes, by_id = [], {}
    for n in raw["nodes"]:
        if len(nodes) >= MAX_NODES:
            break
        if not isinstance(n, dict) or not isinstance(n.get("id"), str) or not _ID.match(n["id"]):
            continue
        if n["id"] in by_id or not _text(n.get("label"), 40):
            continue
        node = {
            "id": n["id"],
            "label": _text(n.get("label"), 40),
            "sub": _text(n.get("sub"), 60),
            "kind": n.get("kind") if n.get("kind") in DIAGRAM_KINDS else "dato",
            "x": _num(n.get("x"), 50.0),
            "y": _num(n.get("y"), 50.0),
            "step": 0,
        }
        node["kind_label"] = DIAGRAM_KINDS[node["kind"]]
        nodes.append(node)
        by_id[node["id"]] = node
    if not nodes:
        return None
    edges, edge_ids = [], {}
    for e in raw.get("edges") if isinstance(raw.get("edges"), list) else []:
        if len(edges) >= MAX_EDGES:
            break
        if not isinstance(e, dict):
            continue
        a, b = by_id.get(e.get("from")), by_id.get(e.get("to"))
        if a is None or b is None or a is b:
            continue
        eid = f"{a['id']}-{b['id']}"
        if eid in edge_ids:
            continue
        p1, p2 = (
            _edge_point((a["x"], a["y"]), (b["x"], b["y"])),
            _edge_point((b["x"], b["y"]), (a["x"], a["y"])),
        )
        edge = {
            "id": eid,
            "from": a["label"],
            "to": b["label"],
            "label": _text(e.get("label"), 40),
            "flow": e.get("flow") is True,
            "x1": round(p1[0], 2),
            "y1": round(p1[1], 2),
            "x2": round(p2[0], 2),
            "y2": round(p2[1], 2),
            "mx": round((p1[0] + p2[0]) / 2, 2),
            "my": round((p1[1] + p2[1]) / 2, 2),
            "step": 0,
        }
        # el mismo trazo en unidades del viewBox (160 × 90)
        edge.update(
            sx1=round(p1[0] * 1.6, 2),
            sy1=round(p1[1] * 0.9, 2),
            sx2=round(p2[0] * 1.6, 2),
            sy2=round(p2[1] * 0.9, 2),
        )
        edges.append(edge)
        edge_ids[eid] = edge
    groups = 1
    raw_steps = raw.get("steps")
    if isinstance(raw_steps, list):
        used = []
        for group in raw_steps[:MAX_STEPS]:
            ids = [i for i in (group if isinstance(group, list) else []) if isinstance(i, str)]
            ids = [
                i
                for i in ids
                if (i in by_id or i in edge_ids) and i not in {u for g in used for u in g}
            ]
            if ids:
                used.append(ids)
        for k, ids in enumerate(used):
            for i in ids:
                (by_id.get(i) or edge_ids[i])["step"] = k  # el grupo 0 se ve desde el inicio
        groups = max(1, len(used))
    return {
        "nodes": nodes,
        "edges": edges,
        "parts": list(
            range(1, groups)
        ),  # controles «Siguiente parte» (uno por cada grupo después del primero)
        "total": groups,
    }


def _image_url(slug, image):
    """URL de la imagen de una diapositiva, o "" (sin imagen válida o foto privada que no está instalada)."""
    if image.startswith(_PRIV):
        name = image[len(_PRIV) :]
        if photo_path(slug, name) is None:
            return ""
        return reverse("cursos:foto", args=[slug, name])
    return static(image) if _IMAGE.match(image) else ""


def slides_for(path_slug, level_code):
    """Diapositivas validadas del nivel (lista de dict, posiblemente vacía).

    Cada una: title, body, points, image (tal como está en la semilla), image_url ("" si no hay o falta la foto),
    caption, callout ({kind, label, text} o None) y terms. Lo inválido se descarta sin romper la página.
    """
    level = next(
        (lv for lv in _route_json(path_slug).get("levels", []) if lv.get("code") == level_code),
        None,
    )
    raw = level.get("slides") if isinstance(level, dict) else None
    if not isinstance(raw, list):
        return []
    slides = []
    for item in raw[:MAX_SLIDES]:
        if not isinstance(item, dict):
            continue
        title = _text(item.get("title"), 160)
        if not title:
            continue
        image = _text(item.get("image"), 120)
        if image.startswith(_PRIV):
            valid = private_files.is_safe_name(image[len(_PRIV) :])
        else:
            valid = bool(_IMAGE.match(image))
        image = image if valid else ""
        callout = item.get("callout")
        if (
            isinstance(callout, dict)
            and callout.get("kind") in CALLOUTS
            and _text(callout.get("text"), 600)
        ):
            callout = {
                "kind": callout["kind"],
                "label": CALLOUTS[callout["kind"]],
                "text": _text(callout["text"], 600),
            }
        else:
            callout = None
        slides.append(
            {
                "title": title,
                "body": _text(item.get("body"), 4000),
                "points": _strings(item.get("points"), 8, 300),
                "image": image,
                "image_url": _image_url(path_slug, image) if image else "",
                "caption": _text(item.get("caption"), 300),
                "callout": callout,
                "terms": _strings(item.get("terms"), 12, 60),
                "diagram": _diagram(item.get("diagram")),
            }
        )
    return slides


def guide_for(path_slug, level_code):
    """Guía del nivel (dict) o None. Campos: title, do, commands, mistakes, essential, software."""
    for level in _route_json(path_slug).get("levels", []):
        if level.get("code") == level_code:
            guide = level.get("guide")
            return guide if isinstance(guide, dict) and guide.get("do") else None
    return None


def guide_context(path, current):
    """Contexto para pintar la guía: resuelve el curso esencial entre los recursos del nivel."""
    if not current:
        return None
    guide = guide_for(path.slug, current["level"].code)
    if not guide:
        return None
    target = guide.get("essential", "")
    link = None
    for lr in current.get("resources", []) or []:
        if lr.resource.title == target and lr.resource.url:
            link = lr.resource
            break
    images = images_for(path.slug, current["level"].code)
    return {
        "guide": guide,
        "essential": link,
        "code": current["level"].code,
        "images": images,
        "figures": [{"src": i, "caption": image_title(i)} for i in images],
    }


_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
_TITLES = {}


def image_title(image):
    """Texto del <title> del SVG (pie de figura y alt); vacío si no hay o no se encuentra."""
    if image in _TITLES:
        return _TITLES[image]
    text = ""
    try:
        from django.contrib.staticfiles import finders

        found = finders.find(image)
        if found:
            head = Path(found).read_text(encoding="utf-8")[:4000]
            m = _TITLE.search(head)
            if m:
                text = re.sub(r"\s+", " ", m.group(1)).strip()
                if len(text) > 150:
                    text = text[:150].rsplit(" ", 1)[0].rstrip(",;:. ") + "…"
    except (OSError, ValueError):
        text = ""
    _TITLES[image] = text
    return text


def images_for(path_slug, level_code):
    """Infografías del nivel (rutas de estáticos validadas), en el orden de la semilla."""
    for level in _route_json(path_slug).get("levels", []):
        if level.get("code") == level_code:
            images = level.get("images") or []
            return [i for i in images if isinstance(i, str) and _IMAGE.match(i)][:3]
    return []
