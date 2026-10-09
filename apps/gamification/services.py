"""Avatar de las personas: configuración, validación de piezas desbloqueadas y tarjetas del editor.

Cada persona tiene una carrera (el campo se llama `class` por compatibilidad) que trae su propio look. El editor
agrupa las carreras por disciplina, muestra cada miniatura con el aspecto real de la opción y recomienda lo que calza
con la carrera elegida.
"""

import json
import secrets
from functools import lru_cache
from pathlib import Path

from django.conf import settings

from . import avatar, game, sheet
from .avatar import careers, engine

# categoría → (título en español, tipo de selector)
SECTIONS = [
    ("Tu carrera", [("class", "Elige tu carrera")]),
    ("Quién eres", [("body", "Cuerpo")]),
    (
        "Cara",
        [
            ("skin", "Tono de piel"),
            ("eyes", "Ojos"),
            ("eye_color", "Color de ojos"),
            ("brows", "Cejas"),
            ("mouth", "Boca"),
        ],
    ),
    (
        "Pelo",
        [("hair", "Peinado"), ("hair_color", "Color de pelo"), ("facial_hair", "Barba y bigote")],
    ),
    (
        "Ropa de trabajo",
        [
            ("outfit", "Ropa"),
            ("outfit_color", "Color de la ropa"),
            ("neckwear", "Cuello"),
            ("pin", "Pin de solapa"),
            ("legwear", "Parte de abajo"),
            ("pants_color", "Color del pantalón"),
        ],
    ),
    (
        "Cabeza y herramientas",
        [
            ("headwear", "Casco, gorro o sombrero"),
            ("headwear_color", "Color del casco o gorro"),
            ("glasses", "Lentes"),
            ("glasses_color", "Color de lentes"),
            ("prop", "Herramienta en la mano"),
        ],
    ),
    ("Fondo y marco", [("background", "Fondo"), ("frame", "Marco")]),
]
TILE_CATEGORIES = {
    "body",
    "eyes",
    "brows",
    "mouth",
    "hair",
    "facial_hair",
    "glasses",
    "headwear",
    "neckwear",
    "outfit",
    "legwear",
    "prop",
    "pin",
    "background",
}
# Estas se ven mejor con el cuerpo entero (herramientas, piernas y fondos no caben en el busto).
FULL_VIEW = {"legwear", "prop", "background"}
INT_KEYS = {key for key, allowed in engine.CHOICES.items() if isinstance(allowed, range)}
# Lo que trae el look de una carrera: si la persona no tocó nada de esto, al cambiar de carrera se viste con su look.
LOOK_KEYS = tuple(next(iter(careers.CAREERS.values()))["look"])
# categoría → clave de `careers` donde está lo recomendado (paletas de colores o listas de piezas)
RECOMMENDED = {
    "outfit": ("outfits", None),
    "outfit_color": ("palette", "outfit_color"),
    "headwear": ("headwear", None),
    "headwear_color": ("palette", "headwear_color"),
    "glasses": ("glasses", None),
    "prop": ("props", None),
    "pants_color": ("palette", "pants_color"),
    "background": ("palette", "background"),
}


def unlocked_badges(person) -> set:
    return game.unlocked_badges(person)


def gates(person) -> dict:
    """Lo que la persona ya desbloqueó (insignias y nivel), listo para `clean_config(**gates)`."""
    return {"unlocked": unlocked_badges(person), "level": game.level_info(person)["level"]}


@lru_cache(maxsize=1)
def _badge_names():
    path = Path(settings.BASE_DIR) / "seed" / "insignias.json"
    try:
        return {
            b["slug"]: b["name"] for b in json.loads(path.read_text(encoding="utf-8"))["badges"]
        }
    except (OSError, ValueError, KeyError):
        return {}


def badge_name(slug) -> str:
    return _badge_names().get(slug, slug)


def person_config(person) -> dict:
    """Configuración vigente: la guardada o, si no hay, el avatar inicial de su login."""
    stored = person.avatar_config if isinstance(person.avatar_config, dict) else {}
    cfg = stored or avatar.default_config(person.login, person.character_class)
    if person.character_class and "class" not in cfg:
        cfg = {**cfg, "class": person.character_class}
    kwargs = {"unlocked": unlocked_badges(person)}
    if any(cfg.get(group) in pieces for group, pieces in engine.LEVEL_UNLOCKS.items()):
        kwargs["level"] = game.level_info(person)["level"]  # solo si usa algo que pide nivel
    return avatar.clean_config(cfg, **kwargs)


def coerce(data) -> dict:
    """Convierte lo que llega de un formulario (todo texto) a los tipos de la configuración."""
    cfg = {}
    for key in engine.DEFAULTS:
        if key not in data:
            continue
        value = data[key]
        if key in INT_KEYS:
            try:
                value = int(value)
            except (TypeError, ValueError):
                continue
        cfg[key] = value
    return cfg


def clean_from_form(person, data) -> dict:
    """Configuración resultante de un formulario (guardar o vista previa).

    Si la persona cambió de carrera y no tocó nada de su ropa, gorro, lentes, herramienta o fondo, se viste con el look
    de la nueva carrera. Así funciona igual sin JavaScript (con JS, el editor además marca esas opciones al elegirla).
    """
    gate = gates(person)
    base = person_config(person)
    submitted = coerce(data)
    cfg = avatar.clean_config({**base, **submitted}, **gate)
    changed_career = cfg["class"] != base["class"]
    touched = any(cfg[key] != base[key] for key in LOOK_KEYS)
    if changed_career and not touched:
        cfg = avatar.apply_career(cfg, cfg["class"], **gate)
    return cfg


def save_config(person, data) -> dict:
    cfg = clean_from_form(person, data)
    person.avatar_config = cfg
    person.character_class = cfg["class"]
    person.save(update_fields=["avatar_config", "character_class", "updated_at"])
    sheet.sync_profile(person)
    return cfg


def random_config(person) -> dict:
    """«Sorpréndeme»: combinación al azar que siempre calza con la carrera de la persona."""
    return avatar.surprise(secrets.token_hex(6), person_config(person)["class"], **gates(person))


def svg_sized(cfg, size, *, title="Avatar", view="full", frame=True):
    svg = avatar.render_svg(cfg, title=title, view=view, frame=frame)
    return svg.replace("<svg ", f'<svg width="{size}" height="{size}" ', 1)


def career_card(cfg) -> dict:
    """Tarjeta de la carrera elegida: nombre, título de juego, disciplina y bonos."""
    slug = cfg["class"]
    data = careers.CAREERS[slug]
    return {
        "slug": slug,
        "name": data["name"],
        "title": data["title"],
        "tagline": data["tagline"],
        "discipline": careers.DISCIPLINE_LABELS[data["discipline"]],
        "accent": data["accent"],
        "bonus": _bonus(data),
    }


def _bonus(data):
    names = dict(sheet.ATTRIBUTES)
    return [
        {"code": code, "name": names[code], "value": value} for code, value in data["bonus"].items()
    ]


def preview_context(cfg, person) -> dict:
    """Todo lo que pinta la vista previa (la página y el fragmento en vivo)."""
    return {
        "big": svg_sized(cfg, 192, title=f"Avatar de {person.name}", view="full"),
        "medium": svg_sized(cfg, 96, view="full"),
        "small": svg_sized(cfg, 64, view="full"),
        "bust": svg_sized(cfg, 32, view="bust"),
        "card": career_card(cfg),
    }


def _recommended(key, cfg_class):
    """Valores recomendados por la carrera para una categoría (vacío si no hay recomendación)."""
    spec = RECOMMENDED.get(key)
    if not spec:
        return ()
    group, sub = spec
    data = careers.CAREERS[cfg_class]
    return tuple(data[group][sub] if sub else data[group])


def _tile_cfg(cfg, key, option_id, gate):
    if key == "class":
        return avatar.apply_career(cfg, option_id, **gate)
    return {**cfg, key: option_id}


def _career_clusters(cfg, gate):
    clusters = []
    for slug, label, members in careers.by_discipline():
        options = []
        for career in members:
            data = careers.CAREERS[career]
            look = avatar.apply_career(cfg, career, **gate)
            options.append(
                {
                    "id": career,
                    "label": data["name"],
                    "title": data["title"],
                    "tagline": data["tagline"],
                    "accent": data["accent"],
                    "bonus": _bonus(data),
                    "selected": cfg["class"] == career,
                    "locked": False,
                    "need": "",
                    "svg": svg_sized(look, 72, title=data["name"], view="full", frame=False),
                    "look": json.dumps({k: look[k] for k in LOOK_KEYS}),
                }
            )
        if options:
            clusters.append({"slug": slug, "label": label, "options": options})
    return clusters


def editor_sections(cfg, person):
    """Secciones del editor; las de estilo llevan una miniatura que muestra la opción de verdad.

    Las miniaturas parten de la configuración actual, así que con otra carrera cambian la ropa, el gorro y el fondo
    que se ven. Las opciones que la carrera recomienda salen primero y llevan una marca.
    """
    catalog = avatar.catalog()
    gate = gates(person)
    have, level = gate["unlocked"], gate["level"]
    sections = []
    for title, fields in SECTIONS:
        groups = []
        for key, label in fields:
            if key == "class":
                groups.append(
                    {
                        "key": key,
                        "label": label,
                        "options": [],
                        "clusters": _career_clusters(cfg, gate),
                        "tiles": False,
                        "careers": True,
                    }
                )
                continue
            recommended = _recommended(key, cfg["class"])
            options = []
            for opt in catalog[key]:
                need = engine.UNLOCKS.get(key, {}).get(opt["id"])
                need_level = engine.LEVEL_UNLOCKS.get(key, {}).get(opt["id"], 0)
                item = {
                    "id": opt["id"],
                    "label": opt["label"],
                    "color": opt.get("color"),
                    "selected": cfg[key] == opt["id"],
                    "locked": bool(need and need not in have) or need_level > level,
                    "need": badge_name(need) if need and need not in have else "",
                    "need_level": need_level if need_level > level else 0,
                    "rec": opt["id"] in recommended,
                }
                if key in TILE_CATEGORIES:
                    item["svg"] = svg_sized(
                        _tile_cfg(cfg, key, opt["id"], gate),
                        64 if key in FULL_VIEW else 56,
                        title=opt["label"],
                        view="full" if key in FULL_VIEW else "bust",
                        frame=False,
                    )
                options.append(item)
            if recommended:
                options.sort(key=lambda o: not o["rec"])  # estable: lo recomendado primero
            groups.append(
                {
                    "key": key,
                    "label": label,
                    "options": options,
                    "tiles": key in TILE_CATEGORIES,
                    "has_rec": bool(recommended),
                }
            )
        sections.append({"title": title, "groups": groups})
    return sections
