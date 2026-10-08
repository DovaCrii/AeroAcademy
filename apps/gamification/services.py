"""Avatar de las personas: configuración, validación de piezas desbloqueadas y tarjetas del editor.

El XP, las insignias y los títulos llegan con el Bloque 13; hasta entonces `unlocked_badges()`
devuelve vacío y las piezas que piden una insignia aparecen bloqueadas.
"""

import json
import secrets
from functools import lru_cache
from pathlib import Path

from django.conf import settings

from . import avatar, game
from .avatar import engine

# categoría → (título en español, tipo de selector)
SECTIONS = [
    ("Quién eres", [("class", "Clase"), ("body", "Cuerpo")]),
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
        "Accesorios",
        [
            ("glasses", "Lentes"),
            ("glasses_color", "Color de lentes"),
            ("headwear", "Gorro o sombrero"),
            ("headwear_color", "Color del gorro"),
            ("neckwear", "Cuello"),
        ],
    ),
    (
        "Ropa",
        [
            ("outfit", "Ropa"),
            ("outfit_color", "Color de la ropa"),
            ("legwear", "Parte de abajo"),
            ("pants_color", "Color del pantalón"),
        ],
    ),
    ("Fondo y marco", [("background", "Fondo"), ("frame", "Marco")]),
]
TILE_CATEGORIES = {
    "class",
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
}
INT_KEYS = {key for key, allowed in engine.CHOICES.items() if isinstance(allowed, range)}


def unlocked_badges(person) -> set:
    return game.unlocked_badges(person)


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
    return avatar.clean_config(cfg, unlocked=unlocked_badges(person))


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
    base = person_config(person)
    return avatar.clean_config({**base, **coerce(data)}, unlocked=unlocked_badges(person))


def save_config(person, data) -> dict:
    cfg = clean_from_form(person, data)
    person.avatar_config = cfg
    person.character_class = cfg["class"]
    person.save(update_fields=["avatar_config", "character_class", "updated_at"])
    return cfg


def random_config(person) -> dict:
    cfg = avatar.default_config(secrets.token_hex(6), "")
    return avatar.clean_config(
        {**cfg, "class": person_config(person)["class"]}, unlocked=unlocked_badges(person)
    )


def svg_sized(cfg, size, *, title="Avatar", view="full", frame=True):
    svg = avatar.render_svg(cfg, title=title, view=view, frame=frame)
    return svg.replace("<svg ", f'<svg width="{size}" height="{size}" ', 1)


def editor_sections(cfg, person):
    """Secciones del editor; las de estilo llevan una miniatura con la configuración actual."""
    catalog = avatar.catalog()
    have = unlocked_badges(person)
    sections = []
    for title, fields in SECTIONS:
        groups = []
        for key, label in fields:
            options = []
            for opt in catalog[key]:
                need = engine.UNLOCKS.get(key, {}).get(opt["id"])
                item = {
                    "id": opt["id"],
                    "label": opt["label"],
                    "color": opt.get("color"),
                    "selected": cfg[key] == opt["id"],
                    "locked": bool(need and need not in have),
                    "need": badge_name(need) if need else "",
                }
                if key in TILE_CATEGORIES:
                    item["svg"] = svg_sized(
                        {**cfg, key: opt["id"]}, 56, title=opt["label"], view="bust", frame=False
                    )
                options.append(item)
            groups.append(
                {"key": key, "label": label, "options": options, "tiles": key in TILE_CATEGORIES}
            )
        sections.append({"title": title, "groups": groups})
    return sections
