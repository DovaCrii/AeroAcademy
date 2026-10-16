"""Avatar de las personas: configuración, validación de piezas desbloqueadas y tarjetas del editor.

Cada persona tiene una carrera (el campo se llama `class` por compatibilidad) que trae su propio look. El editor
agrupa las carreras por disciplina, muestra cada miniatura con el aspecto real de la opción y recomienda lo que calza
con la carrera elegida.
"""

import json
import logging
import secrets
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.urls import reverse
from django.utils.safestring import mark_safe

from . import avatar, game, sheet
from .avatar import careers, engine
from .avatar import views as avatar_views
from .avatar.parts import poses

logger = logging.getLogger(__name__)

POSE_DEFAULT = poses.DEFAULT_POSE

# Secciones del editor (acordeón): slug, título, grupos «clave → título» y cómo se resume la elección actual.
# Cada clave de `engine.CHOICES` tiene su propio <fieldset>; nada del catálogo se quita.
SECTIONS = [
    {
        "slug": "carrera",
        "title": "Carrera",
        "fields": [("class", "Elige tu carrera")],
        "summary": [("class", "{}")],
    },
    {
        "slug": "cuerpo-cara",
        "title": "Cuerpo y cara",
        "fields": [
            ("body", "Cuerpo"),
            ("skin", "Tono de piel"),
            ("eyes", "Ojos"),
            ("eye_color", "Color de ojos"),
            ("brows", "Cejas"),
            ("mouth", "Boca"),
        ],
        "summary": [("body", "{}"), ("skin", "piel {}"), ("eyes", "ojos {}")],
    },
    {
        "slug": "pelo",
        "title": "Pelo",
        "fields": [
            ("hair", "Peinado"),
            ("hair_color", "Color de pelo"),
            ("facial_hair", "Barba y bigote"),
        ],
        "summary": [("hair", "{}"), ("hair_color", "{}"), ("facial_hair", "{}")],
    },
    {
        "slug": "ropa",
        "title": "Ropa",
        "fields": [
            ("outfit", "Ropa"),
            ("outfit_color", "Color de la ropa"),
            ("neckwear", "Cuello"),
            ("pin", "Pin de solapa"),
            ("legwear", "Parte de abajo"),
            ("pants_color", "Color del pantalón"),
        ],
        "summary": [("outfit", "{}"), ("outfit_color", "{}")],
    },
    {
        "slug": "casco-herramientas",
        "title": "Casco y herramientas",
        "fields": [
            ("headwear", "Casco, gorro o sombrero"),
            ("headwear_color", "Color del casco o gorro"),
            ("glasses", "Lentes"),
            ("glasses_color", "Color de lentes"),
            ("prop", "Herramienta en la mano"),
        ],
        "summary": [("headwear", "{}"), ("glasses", "{}"), ("prop", "{}")],
    },
    {
        "slug": "fondo-marco",
        "title": "Fondo y marco",
        "fields": [
            ("background", "Fondo"),
            ("frame", "Marco"),
            ("show_badges", "Insignias en mi avatar"),
        ],
        "summary": [("background", "{}"), ("frame", "marco {}"), ("show_badges", "insignias {}")],
    },
]
SECTION_SLUGS = tuple(sec["slug"] for sec in SECTIONS)
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
# Miniatura de cada categoría: (vista, ancho en px). Cada ancho es un múltiplo entero del ancho de la vista, y los
# recortes por zona (ojos, boca, torso, piernas) dejan el HTML liviano: una zona de ojos son 120 celdas, no 1024.
TILE_VIEWS = {
    "body": ("bust", 48),
    "eyes": ("zone:eyes", 48),
    "brows": ("zone:eyes", 48),
    "glasses": ("zone:glasses", 60),
    "mouth": ("zone:mouth", 48),
    "hair": ("top", 48),
    "headwear": ("top", 48),
    "facial_hair": ("head", 48),
    "neckwear": ("zone:neck", 48),
    "outfit": ("zone:torso", 48),
    "pin": ("zone:pin", 48),
    "legwear": ("zone:legs", 48),
    "background": ("zone:bg", 48),
}
CHIP_VIEW = ("head", 32)  # chip de carrera: la cabeza a 2×
# Opciones sin dibujo ni color: se eligen por su texto.
TEXT_CATEGORIES = {"show_badges"}
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


def svg_sized(
    cfg,
    size,
    *,
    title="Avatar",
    view="full",
    frame=None,
    layers="figure",
    decorative=False,
    bg_alt=None,
    pattern=True,
    halo=True,
    backdrop=True,
    pose=None,
    badge=None,
    inline=True,
):
    """SVG de una vista con `size` px de ancho; cada celda mide un número entero de píxeles.

    Un tamaño que no es múltiplo del ancho de la vista es un error de la plantilla: en DEBUG lanza `ValueError`; en
    producción se redondea hacia abajo al múltiplo válido y se deja un aviso (sin datos personales).
    """
    width = size
    if not avatar_views.valid_width(view, size):
        if settings.DEBUG:
            raise ValueError(f"tamaño {size} no es múltiplo entero de la vista {view!r}")
        logger.warning("Avatar: tamaño %s no es entero para la vista %s", size, view)
        width = avatar_views.snap_width(view, size)
    _x, _y, cells_w, cells_h = avatar_views.box(view)
    height = width * cells_h // cells_w
    svg = avatar.render_svg(
        cfg,
        title=title,
        view=view,
        layers=layers,
        decorative=decorative,
        bg_alt=bg_alt,
        pattern=pattern,
        halo=halo,
        inline=inline,
        backdrop=backdrop,
        pose=pose or POSE_DEFAULT,
        badge=badge,
    )
    return svg.replace("<svg ", f'<svg width="{width}" height="{height}" ', 1)


def avatar_badge(person, cfg):
    """Rareza de la insignia más alta que el avatar de `person` muestra (parche de manga y adhesivo del casco).

    Solo cuenta lo que ya es público en la vitrina de su hoja (insignias ganadas y no retiradas) y solo si la persona no
    lo ocultó (`show_badges`). Al dibujo llega la rareza, nunca el nombre de la insignia ni nada de credenciales.
    """
    if not cfg["show_badges"]:
        return None
    from .models import PersonBadge

    earned = set(
        PersonBadge.objects.filter(person=person, badge__retired=False).values_list(
            "badge__rarity", flat=True
        )
    )
    return next((rarity for rarity in engine.BADGE_ORDER if rarity in earned), None)


def auto_background(person, cfg=None):
    """Fondo claro para quien aún no guardó su avatar: el SVG lleva el oscuro y el claro y el tema decide."""
    if person.avatar_config:
        return None  # lo que se eligió se respeta
    cfg = cfg or person_config(person)
    return careers.light_background(cfg["class"])


def framed(svg, cfg, *, level=None, large=False):
    """Contenedor HTML con el marco de rareza (y la placa «NV n»): el marco vive fuera del SVG."""
    plate = (
        f'<span class="av-plate" data-nv="{int(level)}" aria-hidden="true"></span>' if level else ""
    )
    size = " av-frame--lg" if large else ""
    return mark_safe(  # noqa: S308 (el SVG sale del catálogo y `frame` es una clave validada)
        f'<span class="av-frame av-frame--{cfg["frame"]}{size}">{svg}{plate}</span>'
    )


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


def valid_pose(raw) -> str:
    """La pose de la vista previa (no se guarda): solo vale una de la lista cerrada."""
    return raw if raw in poses.POSES else POSE_DEFAULT


def preview_context(cfg, person, pose=None) -> dict:
    """Todo lo que pinta la vista previa (la página y el fragmento en vivo)."""
    level = game.level_info(person)["level"]
    pose = valid_pose(pose)
    big = svg_sized(
        cfg,
        240,
        title=f"Avatar de {person.name}",
        view="stage",
        pose=pose,
        badge=avatar_badge(person, cfg),
    )
    return {
        "big": framed(big, cfg, level=level, large=True),
        "head": svg_sized(cfg, 32, view="head", decorative=True),
        "card": career_card(cfg),
        "low_contrast": not engine.outfit_stands_out(cfg),
        "wearing": wearing(cfg, person),
        "pose": pose,
        "poses": [{"id": key, "label": label} for key, label in poses.LABELS_POSES.items()],
    }


def wearing(cfg, person) -> list:
    """«Lo que lleva»: de dónde viene cada pieza que el avatar trae puesta (insignia, nivel u oficio).

    Solo la ve la persona dueña del avatar. `cfg` ya viene limpio con lo desbloqueado, así que solo salen piezas
    ganadas; nunca entra nada de credenciales.
    """
    labels = {
        key: {o["id"]: o["label"] for o in options}
        for key, options in avatar.catalog().items()
        if isinstance(options, list)
    }

    def name(key):
        label = labels[key].get(cfg[key], cfg[key])
        return f"Marco {label.lower()}" if key == "frame" else label

    items = []
    for key, pieces in engine.UNLOCKS.items():
        need = pieces.get(cfg[key])
        if need:
            items.append(f"{name(key)} · insignia «{badge_name(need)}»")
    for key, pieces in engine.LEVEL_UNLOCKS.items():
        level = pieces.get(cfg[key])
        if level:
            items.append(f"{name(key)} · NV {level}")
    look = careers.CAREERS[cfg["class"]]["look"]
    if cfg["prop"] != "none" and cfg["prop"] == look["prop"]:
        items.append(f"{name('prop')} · de tu oficio")
    return items


def _recommended(key, cfg_class):
    """Valores recomendados por la carrera para una categoría (vacío si no hay recomendación)."""
    spec = RECOMMENDED.get(key)
    if not spec:
        return ()
    group, sub = spec
    data = careers.CAREERS[cfg_class]
    return tuple(data[group][sub] if sub else data[group])


def _tip(item) -> str:
    """Texto corto de la opción (tooltip y lectores de pantalla): su nombre y, si falta algo, qué la desbloquea."""
    if item["need_level"]:
        return f"{item['label']}: se desbloquea en NV {item['need_level']}"
    if item["locked"]:
        return f"{item['label']}: se desbloquea con «{item['need']}»"
    return item["label"] + (" (recomendado para tu carrera)" if item["rec"] else "")


def _prop_view(prop_id):
    """Recorte justo de una herramienta (su caja más 1 celda) y ancho entero a la mayor escala que cabe en 64 px."""
    rows = engine.PROPS[prop_id]
    cells = [(x, y) for y, line in rows.items() for x, ch in enumerate(line) if ch != "."]
    if not cells:
        return (20, 12, 8, 8), 24
    x0, x1 = min(x for x, _ in cells), max(x for x, _ in cells)
    y0, y1 = min(y for _, y in cells), max(y for _, y in cells)
    x0, y0 = max(0, x0 - 1), max(0, y0 - 1)
    w, h = min(32, x1 + 2) - x0, min(32, y1 + 2) - y0
    scale = max(1, min(4, 64 // max(w, h)))
    return (x0, y0, w, h), w * scale


PIECE_KEYS = (
    *TILE_VIEWS,
    "prop",
    "class",
)  # categorías con miniatura (las carreras salen como chips)


def piece_size(key, option_id):
    """Ancho y alto en px de la miniatura de una opción (para las etiquetas `<img>`)."""
    if key == "prop":
        view, width = _prop_view(option_id)
    elif key == "class":
        view, width = CHIP_VIEW
    else:
        view, width = TILE_VIEWS[key]
    _x, _y, cells_w, cells_h = avatar_views.box(view)
    return width, width * cells_h // cells_w


def piece_svg(cfg, key, option_id) -> str:
    """Miniatura de una opción como archivo SVG suelto: solo la zona que cambia (ojos, torso…), la herramienta sola, la
    cabeza de la carrera o la muestra del fondo. Es función pura de la configuración y de la opción (se guarda en caché
    del navegador)."""
    look = _tile_cfg(cfg, key, option_id, {})
    if key == "prop":
        view, width = _prop_view(option_id)
        return svg_sized(
            look,
            width,
            view=view,
            layers="prop",
            decorative=True,
            pattern=False,
            halo=False,
            inline=False,
        )
    if key == "class":
        view, width = CHIP_VIEW
        return svg_sized(
            look, width, view=view, decorative=True, pattern=False, halo=False, inline=False
        )
    view, width = TILE_VIEWS[key]
    layers = "none" if key == "background" else "figure"
    return svg_sized(
        look,
        width,
        view=view,
        layers=layers,
        decorative=True,
        pattern=key == "background",
        halo=False,
        inline=False,
    )


# Código corto de una configuración para las URL de las miniaturas: un carácter (base 36) por clave de `CHOICES`, con el
# índice del valor. Así cada `<img>` pesa ~100 bytes en lugar del SVG entero.
_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"


def encode_cfg(cfg) -> str:
    out = []
    for key, allowed in engine.CHOICES.items():
        values = list(allowed)
        out.append(_ALPHABET[values.index(cfg[key])] if cfg[key] in values else "0")
    return "".join(out)


def decode_cfg(code) -> dict:
    """Configuración de un código (lo que no se entiende queda en su valor por defecto)."""
    cfg = {}
    for key, char in zip(engine.CHOICES, str(code or ""), strict=False):
        values = list(engine.CHOICES[key])
        index = _ALPHABET.find(char)
        if 0 <= index < len(values):
            cfg[key] = values[index]
    return avatar.clean_config(cfg)


def piece_src(code, key, option_id) -> str:
    return f"{reverse('gamification:avatar_piece', args=[key, option_id])}?c={code}"


def piece_option(key, raw):
    """El valor real de una opción a partir del texto de la URL (o `None` si no existe)."""
    if key not in PIECE_KEYS:
        return None
    return next((v for v in engine.CHOICES[key] if str(v) == raw), None)


def _tile_cfg(cfg, key, option_id, gate):
    if key == "class":
        return avatar.apply_career(cfg, option_id, **gate)
    return {**cfg, key: option_id}


def _career_clusters(cfg, gate, code):
    """Chips de carrera por disciplina: solo el busto con el look de la carrera y su nombre."""
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
                    "accent": data["accent"],
                    "selected": cfg["class"] == career,
                    "src": piece_src(code, "class", career),
                    "w": piece_size("class", career)[0],
                    "h": piece_size("class", career)[1],
                    "look": json.dumps({k: look[k] for k in LOOK_KEYS}),
                }
            )
        if options:
            clusters.append({"slug": slug, "label": label, "options": options})
    return clusters


def career_table(catalog) -> list:
    """Tabla «¿Qué trae cada carrera?»: oficio, lema, ropa, herramienta, fondo y bonos."""
    outfits = {o["id"]: o["label"] for o in catalog["outfit"]}
    props = {o["id"]: o["label"] for o in catalog["prop"]}
    backgrounds = {o["id"]: o["label"] for o in catalog["background"]}
    rows = []
    for _slug, label, members in careers.by_discipline():
        for career in members:
            data = careers.CAREERS[career]
            look = data["look"]
            rows.append(
                {
                    "id": career,
                    "name": data["name"],
                    "discipline": label,
                    "title": data["title"],
                    "tagline": data["tagline"],
                    "outfit": outfits.get(look["outfit"], ""),
                    "prop": props.get(look["prop"], ""),
                    "background": backgrounds.get(look["background"], ""),
                    "bonus": _bonus(data),
                }
            )
    return rows


def default_section(person) -> str:
    """Sección que se abre sola: la carrera si la persona nunca guardó su avatar, si no «Cuerpo y cara»."""
    return "cuerpo-cara" if person.avatar_config else "carrera"


def resolve_section(raw, person) -> str:
    """`?seccion=` solo vale si está en la lista cerrada; si no, la sección por defecto."""
    return raw if raw in SECTION_SLUGS else default_section(person)


def section_summary(cfg, section, catalog=None) -> str:
    """La elección actual de una sección en texto («Jopo, Castaño, Sin barba»), para el <summary>."""
    catalog = catalog or avatar.catalog()
    parts = []
    for key, template in section["summary"]:
        label = {o["id"]: o["label"] for o in catalog[key]}.get(cfg[key])
        if label:
            parts.append(template.format(label))
    return ", ".join(parts)


def editor_sections(cfg, person, open_slug=None):
    """Secciones del editor; las de estilo llevan una miniatura que muestra la opción de verdad.

    Las miniaturas parten de la configuración actual, así que con otra carrera cambian la ropa, el gorro y el fondo
    que se ven. Las opciones que la carrera recomienda salen primero y llevan una marca. Exactamente una sección
    viene abierta (`open`).
    """
    catalog = avatar.catalog()
    gate = gates(person)
    have, level = gate["unlocked"], gate["level"]
    open_slug = resolve_section(open_slug, person)
    code = encode_cfg(cfg)
    sections = []
    for number, section in enumerate(SECTIONS, start=1):
        groups = []
        for key, label in section["fields"]:
            if key == "class":
                groups.append(
                    {
                        "key": key,
                        "label": label,
                        "current": careers.CAREERS[cfg["class"]]["name"],
                        "options": [],
                        "clusters": _career_clusters(cfg, gate, code),
                        "table": career_table(catalog),
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
                item["tip"] = _tip(item)
                if key in TILE_CATEGORIES:
                    item["src"] = piece_src(code, key, opt["id"])
                    item["w"], item["h"] = piece_size(key, opt["id"])
                options.append(item)
            if recommended:
                options.sort(key=lambda o: not o["rec"])  # estable: lo recomendado primero
            current = next((o["label"] for o in options if o["selected"]), "")
            groups.append(
                {
                    "key": key,
                    "label": label,
                    "current": current,
                    "options": options,
                    "tiles": key in TILE_CATEGORIES,
                    "text": key in TEXT_CATEGORIES,
                    "has_rec": bool(recommended),
                }
            )
        sections.append(
            {
                "slug": section["slug"],
                "number": number,
                "title": section["title"],
                "summary": section_summary(cfg, section, catalog),
                "sum_spec": json.dumps(section["summary"]),
                "open": section["slug"] == open_slug,
                "has_rec": any(g.get("has_rec") for g in groups),
                "groups": groups,
            }
        )
    return sections
