"""Motor del avatar pixel-art de 32×32 (docs/AVATARES_PIXEL.md).

Orden de capas (de atrás hacia adelante):
  pelo (atrás) → gorro (atrás) → cuerpo → ropa → accesorio de cuello → vello facial → nariz → boca → ojos
  → cejas → lentes → pelo (frente) → gorro (frente)
Todo sale del catálogo: nada que escriba la persona entra al SVG.
"""

import hashlib
import random

from . import backgrounds, careers, palettes
from .art import GRID
from .parts import body, face, facial_hair, glasses, hair, headwear, outfits, props

BODIES = tuple(body.LABELS_BODY)
LEGWEAR = tuple(body.LEGWEAR)
HAIR = hair.HAIR
EYES, BROWS, MOUTHS = face.EYES, face.BROWS, face.MOUTHS
FACIAL_HAIR = facial_hair.FACIAL_HAIR
HEADWEAR = headwear.HEADWEAR
GLASSES = glasses.GLASSES
OUTFITS, NECKWEAR = outfits.OUTFITS, outfits.NECKWEAR
PROPS, PINS = props.PROPS, props.PINS

# Lentes que tapan el ojo a propósito (cristal oscuro u ojos pintados dentro); el resto deja ver los ojos.
OPAQUE_GLASSES = {"sunglasses", "goggles", "fpv"}
# Ventana de la cara (ojos, nariz y boca): el pelo y los gorros no dibujan aquí.
FACE_X, FACE_Y = range(11, 21), range(10, 17)

CLASSES = careers.SLUGS  # las carreras del gremio (el campo se llama `class` por compatibilidad)
CLASS_LABELS = {slug: data["name"] for slug, data in careers.CAREERS.items()}
FRAME_LABELS = {
    "common": "Común",
    "bronze": "Bronce",
    "rare": "Raro",
    "epic": "Épico",
    "legendary": "Legendario",
}

# Ropa y color de partida de cada carrera (la persona puede cambiarlos). El look completo está en `careers.py`.
CLASS_DEFAULTS = {
    slug: {key: data["look"][key] for key in ("outfit", "outfit_color", "background")}
    for slug, data in careers.CAREERS.items()
}

# Piezas que se desbloquean con una insignia (slug de seed/insignias.json); el resto es libre.
UNLOCKS = {
    "headwear": {
        "hardhat": "primer-trofeo",
        "hardhat_lamp": "primer-trofeo",
        "explorer": "explorador-multivendor",
        "propeller": "constructor-de-puentes",
        "headphones": "mentor",
    },
    "glasses": {"goggles": "alas-dgac"},
    "frame": {
        "rare": "triada-autodesk",
        "epic": "reliquia-bentley",
        "legendary": "constructor-de-puentes",
    },
}

# Piezas que se desbloquean al llegar a un nivel de juego (el nivel sale de `game.level_info`).
LEVEL_UNLOCKS = {
    "frame": {"bronze": 3},
    "pin": {"hardhat_pin": 5, "theodolite_pin": 10},
}

DEFAULTS = {
    "class": "architect",
    "body": "neutral",
    "skin": 1,
    "hair": "short",
    "hair_color": 1,
    "eyes": "dot",
    "eye_color": 0,
    "brows": "normal",
    "mouth": "smile",
    "facial_hair": "none",
    "glasses": "none",
    "glasses_color": 0,
    "headwear": "none",
    "headwear_color": 0,
    "outfit": "shirt_tie",
    "outfit_color": 0,
    "neckwear": "none",
    "prop": "none",
    "pin": "none",
    "legwear": "pants",
    "pants_color": 0,
    "background": 0,
    "frame": "common",
}

CHOICES = {  # clave de configuración → opciones válidas
    "class": CLASSES,
    "body": BODIES,
    "skin": range(len(palettes.SKINS)),
    "hair": HAIR,
    "hair_color": range(len(palettes.HAIR_COLORS)),
    "eyes": EYES,
    "eye_color": range(len(palettes.EYE_COLORS)),
    "brows": BROWS,
    "mouth": MOUTHS,
    "facial_hair": FACIAL_HAIR,
    "glasses": GLASSES,
    "glasses_color": range(len(palettes.GLASSES_COLORS)),
    "headwear": HEADWEAR,
    "headwear_color": range(len(palettes.HEADWEAR_COLORS)),
    "outfit": OUTFITS,
    "outfit_color": range(len(palettes.OUTFIT_COLORS)),
    "neckwear": NECKWEAR,
    "prop": PROPS,
    "pin": PINS,
    "legwear": LEGWEAR,
    "pants_color": range(len(palettes.PANTS_COLORS)),
    "background": range(len(palettes.BACKGROUNDS)),
    "frame": palettes.FRAMES,
}


# --- configuración -----------------------------------------------------------------------------------------


def clean_config(config=None, *, unlocked=None, level=None):
    """Configuración válida. Con `unlocked` (slugs de insignias) y `level` (nivel de juego) descarta lo que aún no
    se ganó."""
    cfg = dict(DEFAULTS)
    cls = (config or {}).get("class")
    if cls in CLASS_DEFAULTS:
        cfg.update(CLASS_DEFAULTS[cls])
    for key, value in (config or {}).items():
        if key in cfg and not isinstance(value, (list, dict)):
            cfg[key] = value
    for key, allowed in CHOICES.items():
        value = cfg[key]
        if isinstance(value, bool) or value not in allowed:
            cfg[key] = DEFAULTS[key]
    if unlocked is not None:
        have = set(unlocked)
        for group in ("headwear", "glasses", "frame"):
            need = UNLOCKS[group].get(cfg[group])
            if need and need not in have:
                cfg[group] = DEFAULTS[group]
    if level is not None:
        for group, pieces in LEVEL_UNLOCKS.items():
            if pieces.get(cfg[group], 0) > level:
                cfg[group] = DEFAULTS[group]
    return cfg


def default_config(seed: str, character_class: str = ""):
    """Avatar inicial determinista a partir del login: la misma persona siempre se ve igual."""
    d = hashlib.sha256(seed.strip().lower().encode("utf-8")).digest()
    free_hair, free_hw = list(HAIR), [h for h in HEADWEAR if h not in UNLOCKS["headwear"]]
    cfg = {
        "class": character_class
        if character_class in CLASS_DEFAULTS
        else CLASSES[d[0] % len(CLASSES)],
        "body": BODIES[d[1] % len(BODIES)],
        "skin": d[2] % len(palettes.SKINS),
        "hair": free_hair[d[3] % len(free_hair)],
        "hair_color": d[4] % len(palettes.HAIR_COLORS),
        "eyes": list(EYES)[d[5] % len(EYES)],
        "eye_color": d[6] % len(palettes.EYE_COLORS),
        "brows": list(BROWS)[d[7] % len(BROWS)],
        "mouth": list(MOUTHS)[d[8] % len(MOUTHS)],
        "legwear": LEGWEAR[d[9] % len(LEGWEAR)],
        "pants_color": d[10] % len(palettes.PANTS_COLORS),
        "headwear": free_hw[d[11] % len(free_hw)] if d[12] % 4 == 0 else "none",
        "headwear_color": d[13] % len(palettes.HEADWEAR_COLORS),
        "facial_hair": list(FACIAL_HAIR)[d[14] % len(FACIAL_HAIR)] if d[15] % 3 == 0 else "none",
        "glasses": [g for g in GLASSES if g not in UNLOCKS["glasses"]][d[16] % 3]
        if d[17] % 3 == 0
        else "none",
    }
    cfg["prop"] = careers.CAREERS[cfg["class"]]["look"]["prop"]
    return clean_config(cfg)


def apply_career(config, slug, *, unlocked=None, level=None):
    """Viste la configuración con el look de una carrera (ropa, gorro, lentes, herramienta, fondo).

    Lo personal (cuerpo, piel, pelo, ojos, barba) no cambia. Lo bloqueado por insignias cae a su valor libre.
    """
    if slug not in careers.CAREERS:
        return clean_config(config, unlocked=unlocked, level=level)
    look = careers.CAREERS[slug]["look"]
    return clean_config({**(config or {}), **look, "class": slug}, unlocked=unlocked, level=level)


def _luminance(hex_color):
    channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(hex_a, hex_b):
    """Razón de contraste (1 a 21) entre dos colores #RRGGBB."""
    a, b = sorted((_luminance(hex_a), _luminance(hex_b)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def outfit_stands_out(cfg):
    """La ropa se distingue del fondo (si no, la figura se pierde)."""
    return contrast(palettes.OUTFIT_COLORS[cfg["outfit_color"]][1]["O"], background_for(cfg)) >= 1.5


NATURAL_HAIR = range(9)  # los 9 primeros colores de pelo son naturales; el resto son «de fantasía»


def surprise(seed, slug="", *, unlocked=None, level=None):
    """Combinación al azar que SIEMPRE calza: ropa, gorro, lentes, herramienta y fondo salen de la carrera.

    Con la misma semilla da el mismo avatar. Lo personal (cuerpo, cara, pelo) es libre; lo de oficio se toma de las
    listas y paletas curadas de la carrera, así el gorro no desentona con la ropa ni la ropa se pierde en el fondo.
    """
    rng = random.Random(str(seed))
    slug = slug if slug in careers.CAREERS else rng.choice(CLASSES)
    data = careers.CAREERS[slug]
    pal = data["palette"]
    free = [h for h in HEADWEAR if h not in UNLOCKS["headwear"]]
    hats = [h for h in data["headwear"] if h in free] or ["none"]
    background = rng.choice(pal["background"])
    colors = [
        c
        for c in pal["outfit_color"]
        if contrast(palettes.OUTFIT_COLORS[c][1]["O"], palettes.BACKGROUNDS[background][1]) >= 1.5
    ] or [data["look"]["outfit_color"]]
    outfit_color = rng.choice(colors)
    cfg = {
        "class": slug,
        "body": rng.choice(BODIES),
        "skin": rng.randrange(len(palettes.SKINS)),
        "hair": rng.choice([h for h in HAIR]),
        "hair_color": rng.choice(NATURAL_HAIR)
        if rng.random() < 0.85
        else rng.randrange(len(palettes.HAIR_COLORS)),
        "eyes": rng.choice(list(EYES)),
        "eye_color": rng.randrange(len(palettes.EYE_COLORS)),
        "brows": rng.choice(list(BROWS)),
        "mouth": rng.choice(list(MOUTHS)),
        "facial_hair": rng.choice(list(FACIAL_HAIR)) if rng.random() < 0.3 else "none",
        "outfit": rng.choice(data["outfits"]),
        "outfit_color": outfit_color,
        "neckwear": data["look"]["neckwear"] if rng.random() < 0.5 else "none",
        "legwear": "pants" if rng.random() < 0.85 else rng.choice(LEGWEAR),
        "pants_color": rng.choice(pal["pants_color"]),
        "headwear": rng.choice(hats) if rng.random() < 0.7 else "none",
        "headwear_color": rng.choice(pal["headwear_color"]),
        "glasses": rng.choice(data["glasses"]),
        "glasses_color": rng.randrange(len(palettes.GLASSES_COLORS)),
        "prop": rng.choice(data["props"]),
        "background": background,
    }
    return clean_config(cfg, unlocked=unlocked, level=level)


# --- composición -------------------------------------------------------------------------------------------


def _paint(grid, rows, only_on=None):
    for y, line in rows.items():
        for x, ch in enumerate(line):
            if ch == "." or not 0 <= y < GRID:
                continue
            if only_on is None or grid[y][x] in only_on:
                grid[y][x] = ch


def _hat_top(hat_art):
    rows = [y for y, line in hat_art["front"].items() if line.strip(".")]
    return min(rows) if rows else None


def _above(rows, top):
    """Quita las filas por encima de `top` (el pelo no asoma sobre la copa de un gorro)."""
    return rows if top is None else {y: line for y, line in rows.items() if y >= top}


def _off_face(rows):
    """Quita lo que caiga sobre ojos, nariz y boca: ni el pelo ni un gorro tapan la cara."""
    out = {}
    for y, line in rows.items():
        if y in FACE_Y:
            line = "".join("." if x in FACE_X else ch for x, ch in enumerate(line))
        out[y] = line
    return out


def compose(config):
    """Matriz 32×32 de claves de color ('.' = transparente) para una configuración ya limpia.

    Reglas de encaje (ver `audit.py`): los lentes transparentes se dibujan *debajo* de los ojos, así los ojos siempre
    se ven dentro del lente; los opacos (de sol, de piloto) van encima. Con gorro, el pelo se recorta por encima de la
    copa; y ni el pelo ni el gorro dibujan sobre la cara.
    """
    cfg = config
    grid = [["."] * GRID for _ in range(GRID)]
    hair_art, hat_art = HAIR[cfg["hair"]], HEADWEAR[cfg["headwear"]]
    top = _hat_top(hat_art)
    opaque = cfg["glasses"] in OPAQUE_GLASSES

    _paint(grid, _above(hair_art["back"], top))
    _paint(grid, hat_art["back"])
    _paint(grid, body.BASE)
    _paint(grid, body.BODY_PATCH[cfg["body"]])
    _paint(grid, body.LEGWEAR[cfg["legwear"]])
    _paint(grid, OUTFITS[cfg["outfit"]], only_on={"O"})
    _paint(grid, NECKWEAR[cfg["neckwear"]])
    _paint(grid, FACIAL_HAIR[cfg["facial_hair"]])
    _paint(grid, body.NOSE)
    _paint(grid, MOUTHS[cfg["mouth"]])
    if not opaque:
        _paint(grid, GLASSES[cfg["glasses"]])
    _paint(grid, EYES[cfg["eyes"]])
    _paint(grid, BROWS[cfg["brows"]])
    if opaque:
        _paint(grid, GLASSES[cfg["glasses"]])
    _paint(grid, _off_face(_above(hair_art["front"], top)))
    _paint(grid, _off_face(hat_art["front"]))
    _paint(grid, PINS[cfg["pin"]])
    _paint(grid, PROPS[cfg["prop"]])
    return grid


def palette_for(cfg):
    palette = dict(palettes.FIXED)
    palette.update(palettes.SKINS[cfg["skin"]][1])
    palette.update(palettes.HAIR_COLORS[cfg["hair_color"]][1])
    palette.update(palettes.EYE_COLORS[cfg["eye_color"]][1])
    palette.update(palettes.OUTFIT_COLORS[cfg["outfit_color"]][1])
    palette.update(palettes.PANTS_COLORS[cfg["pants_color"]][1])
    palette.update(palettes.GLASSES_COLORS[cfg["glasses_color"]][1])
    palette.update(palettes.HEADWEAR_COLORS[cfg["headwear_color"]][1])
    return palette


def background_for(cfg):
    return palettes.BACKGROUNDS[cfg["background"]][1]


def render_svg(config=None, *, title="Avatar", frame=True, view="full"):
    """SVG pixel-art. `view="bust"` recorta cabeza y hombros (para tamaños pequeños)."""
    cfg = clean_config(config)
    grid, palette = compose(cfg), palette_for(cfg)
    pad = 2 if frame else 0
    x0, y0, w, h = (0, 0, GRID, GRID) if view == "full" else (4, 2, 24, 24)
    vx, vy, vw, vh = x0 - pad, y0 - pad, w + 2 * pad, h + 2 * pad
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vx} {vy} {vw} {vh}" '
        f'shape-rendering="crispEdges" role="img" aria-label="{_esc(title)}">',
        f"<title>{_esc(title)}</title>",
        f'<rect x="{vx}" y="{vy}" width="{vw}" height="{vh}" fill="{background_for(cfg)}"/>',
    ]
    for color, d in backgrounds.pattern_paths(cfg["background"]):
        parts.append(f'<path fill="{color}" d="{d}"/>')
    # Un solo <path> por color: cada tramo horizontal es "M x y h largo v1 h-largo z".
    by_color = {}
    for y, row in enumerate(grid):
        x = 0
        while x < GRID:
            ch = row[x]
            if ch == ".":
                x += 1
                continue
            run = 1
            while x + run < GRID and row[x + run] == ch:
                run += 1
            by_color.setdefault(palette[ch], []).append(f"M{x} {y}h{run}v1h-{run}z")
            x += run
    for color, segments in by_color.items():
        parts.append(f'<path fill="{color}" d="{"".join(segments)}"/>')
    if frame:
        color, var = palettes.FRAMES[cfg["frame"]]
        fill = f"var({var},{color})"
        parts += [
            f'<rect x="{vx}" y="{vy}" width="{vw}" height="1" fill="{fill}"/>',
            f'<rect x="{vx}" y="{vy + vh - 1}" width="{vw}" height="1" fill="{fill}"/>',
            f'<rect x="{vx}" y="{vy}" width="1" height="{vh}" fill="{fill}"/>',
            f'<rect x="{vx + vw - 1}" y="{vy}" width="1" height="{vh}" fill="{fill}"/>',
        ]
    parts.append("</svg>")
    return "".join(parts)


def _esc(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# --- catálogo para el editor ---------------------------------------------------------------------------------


def _options(ids, labels):
    return [{"id": i, "label": labels.get(i, i)} for i in ids]


def _swatches(entries, hex_key=None):
    out = []
    for index, (name, value) in enumerate(entries):
        color = value if isinstance(value, str) else value[hex_key]
        out.append({"id": index, "label": name, "color": color})
    return out


def catalog():
    """Todo lo que la persona puede elegir, con etiquetas en español, para el editor (Bloque 14)."""
    return {
        "class": _options(CLASSES, CLASS_LABELS),
        "body": _options(BODIES, body.LABELS_BODY),
        "skin": _swatches(palettes.SKINS, "S"),
        "hair": _options(HAIR, hair.LABELS),
        "hair_color": _swatches(palettes.HAIR_COLORS, "H"),
        "eyes": _options(EYES, face.LABELS_EYES),
        "eye_color": _swatches(palettes.EYE_COLORS, "e"),
        "brows": _options(BROWS, face.LABELS_BROWS),
        "mouth": _options(MOUTHS, face.LABELS_MOUTHS),
        "facial_hair": _options(FACIAL_HAIR, facial_hair.LABELS),
        "glasses": _options(GLASSES, glasses.LABELS),
        "glasses_color": _swatches(palettes.GLASSES_COLORS, "F"),
        "headwear": _options(HEADWEAR, headwear.LABELS),
        "headwear_color": _swatches(palettes.HEADWEAR_COLORS, "T"),
        "outfit": _options(OUTFITS, outfits.LABELS_OUTFITS),
        "outfit_color": _swatches(palettes.OUTFIT_COLORS, "O"),
        "neckwear": _options(NECKWEAR, outfits.LABELS_NECKWEAR),
        "prop": _options(PROPS, props.LABELS_PROPS),
        "pin": _options(PINS, props.LABELS_PINS),
        "legwear": _options(LEGWEAR, body.LABELS_LEGWEAR),
        "pants_color": _swatches(palettes.PANTS_COLORS, "P"),
        "background": _swatches(palettes.BACKGROUNDS),
        "careers": careers.CAREERS,
        "frame": [
            {"id": f, "label": FRAME_LABELS[f], "color": palettes.FRAMES[f][0]}
            for f in palettes.FRAMES
        ],
        "unlocks": UNLOCKS,
        "level_unlocks": LEVEL_UNLOCKS,
    }
