"""Valida que las piezas de arte cumplan el contrato de cada categoría (ver los docstrings de `parts/*.py`).

Se usa en las pruebas y desde la línea de comandos:  python tools/validate_part.py hair face outfits
"""

from importlib import import_module

from .art import GRID

# categoría → (módulo, atributo, ¿tiene back/front?, claves permitidas, rango de filas permitido, ids obligatorios)
SPECS = {
    "hair": ("hair", "HAIR", True, "KHhj", (0, 27),
             ["bald", "buzz", "short", "side_part", "quiff", "curly", "afro", "long", "wavy", "ponytail", "bun",
              "bob", "braids", "mohawk"]),
    "eyes": ("face", "EYES", False, "KEeWw", (8, 13), ["dot", "iris", "happy", "lashes", "wink"]),
    "brows": ("face", "BROWS", False, "HhjK", (6, 10), ["normal", "thick", "thin", "none", "raised"]),
    "mouths": ("face", "MOUTHS", False, "KMmW", (13, 17), ["smile", "neutral", "grin", "open", "smirk", "surprised"]),
    "facial_hair": ("facial_hair", "FACIAL_HAIR", False, "HhjK", (10, 18),
                    ["none", "stubble", "mustache", "goatee", "beard", "full_beard"]),
    "headwear": ("headwear", "HEADWEAR", True, "KTtUWYRCNZ", (0, 13),
                 ["none", "cap", "beanie", "hardhat", "explorer", "propeller", "headphones", "headband", "beret",
                  "bucket", "bump_cap", "legionnaire", "hardhat_lamp"]),
    "glasses": ("glasses", "GLASSES", False, "FLgKEWC", (8, 13),
                ["none", "round", "square", "aviator", "goggles", "sunglasses", "monocle", "safety", "fpv"]),
    "outfits": ("outfits", "OUTFITS", False, "OoAaWKYRCNZGDQ", (20, 28),
                ["tshirt", "hoodie", "hivis_vest", "field_vest", "jacket", "apron", "labcoat", "shirt_tie",
                 "flight_jacket", "sweater", "surveyor_jacket", "blazer", "overalls", "bim_hoodie", "hse_vest",
                 "polo", "cardigan"]),
    "neckwear": ("outfits", "NECKWEAR", False, "OoAaWKYRCNZSs", (18, 25),
                 ["none", "lanyard", "scarf", "tie", "bandana"]),
    "props": ("props", "PROPS", False, "KWYRCNZGDQSs", (0, 31),
              ["none", "tablet", "prism_pole", "drone_controller", "scale_ruler", "mug", "gnss_rover",
               "plans_roll", "wrench", "clipboard", "calculator", "camera", "laser_scanner"]),
    "pins": ("props", "PINS", False, "KWYRCNZ", (20, 27), ["none", "compass", "hardhat_pin", "theodolite_pin"]),
}  # fmt: skip

LABEL_ATTR = {
    "hair": "LABELS", "eyes": "LABELS_EYES", "brows": "LABELS_BROWS", "mouths": "LABELS_MOUTHS",
    "facial_hair": "LABELS", "headwear": "LABELS", "glasses": "LABELS", "outfits": "LABELS_OUTFITS",
    "neckwear": "LABELS_NECKWEAR", "props": "LABELS_PROPS", "pins": "LABELS_PINS",
}  # fmt: skip


def load(category):
    module_name, attr, *_ = SPECS[category]
    module = import_module(f"apps.gamification.avatar.parts.{module_name}")
    return getattr(module, attr), getattr(module, LABEL_ATTR[category])


def _check_rows(errors, where, rows, allowed, y_range):
    low, high = y_range
    if not isinstance(rows, dict):
        errors.append(f"{where}: debe ser un dict de filas")
        return
    for y, line in rows.items():
        if not isinstance(y, int) or not low <= y <= high:
            errors.append(f"{where}: fila {y!r} fuera del rango {low}..{high}")
        if not isinstance(line, str) or len(line) != GRID:
            errors.append(
                f"{where}: fila {y} mide {len(line) if isinstance(line, str) else '?'}, debe medir {GRID}"
            )
            continue
        bad = {c for c in line if c != "." and c not in allowed}
        if bad:
            errors.append(
                f"{where}: fila {y} usa claves no permitidas {sorted(bad)} (permitidas: {allowed})"
            )


def validate_category(category):
    """Devuelve la lista de errores de una categoría (vacía si todo está bien)."""
    _, _, layered, allowed, y_range, required = SPECS[category]
    errors = []
    parts, labels = load(category)
    for pid in required:
        if pid not in parts:
            errors.append(f"{category}: falta el id obligatorio «{pid}»")
        if pid not in labels:
            errors.append(f"{category}: falta la etiqueta en español de «{pid}»")
    for pid, art in parts.items():
        if pid not in labels:
            errors.append(f"{category}: «{pid}» no tiene etiqueta")
        if layered:
            if set(art) != {"back", "front"}:
                errors.append(
                    f"{category}/{pid}: debe tener exactamente las claves 'back' y 'front'"
                )
                continue
            for layer in ("back", "front"):
                _check_rows(errors, f"{category}/{pid}/{layer}", art[layer], allowed, y_range)
        else:
            _check_rows(errors, f"{category}/{pid}", art, allowed, y_range)
    return errors


def validate_all(categories=None):
    errors = []
    for category in categories or SPECS:
        errors += validate_category(category)
    return errors


# --- piezas HD (`hd.HD`) -----------------------------------------------------------------------------------------

# categoría de `hd.HD` → clave de `engine.CHOICES`
HD_OPTIONS = {
    "eyes": "eyes", "brows": "brows", "mouth": "mouth", "glasses": "glasses", "facial_hair": "facial_hair",
    "headwear": "headwear", "hair": "hair", "outfit": "outfit", "neckwear": "neckwear", "pin": "pin",
    "prop": "prop",
}  # fmt: skip
HD_ENGINE_KEYS = set("12345")  # solo las pone el motor


def _check_sprite(errors, where, art, category, allowed_keys):
    from .hd import MAX_COLORS, ZONES

    if not isinstance(art, dict) or not {"at", "rows", "space"} <= set(art):
        errors.append(f"{where}: debe ser un sprite() con at, rows y space")
        return
    rows, (ax, ay) = art["rows"], art["at"]
    if not rows or not all(isinstance(line, str) for line in rows):
        errors.append(f"{where}: rows debe ser una lista de textos")
        return
    if len({len(line) for line in rows}) != 1:
        errors.append(f"{where}: todas las filas deben medir lo mismo")
    used = {ch for line in rows for ch in line} - {"."}
    if used & HD_ENGINE_KEYS:
        errors.append(f"{where}: usa claves del motor {sorted(used & HD_ENGINE_KEYS)}")
    if used - allowed_keys:
        errors.append(f"{where}: claves fuera de la paleta {sorted(used - allowed_keys)}")
    if len(used) > MAX_COLORS:
        errors.append(f"{where}: usa {len(used)} colores (máximo {MAX_COLORS})")
    expected_space = "stage" if category == "prop" else "figure"
    if art["space"] != expected_space:
        errors.append(f"{where}: el espacio debe ser {expected_space!r}")
    x0, y0, x1, y1 = ZONES[category]
    width, height = max(len(line) for line in rows), len(rows)
    if not (x0 <= ax and y0 <= ay and ax + width - 1 <= x1 and ay + height - 1 <= y1):
        errors.append(
            f"{where}: la caja ({ax},{ay})+{width}×{height} sale de su zona {(x0, y0, x1, y1)}"
        )


def validate_hd(categories=None):
    """Errores de las piezas HD registradas: ids conocidos, claves, caja, colores y ventana de la cara."""
    from . import engine, hd
    from .hd.compose import FACE_X, FACE_Y
    from .hd.render import palette_hd

    errors = []
    allowed = set(palette_hd(engine.clean_config({}))) - HD_ENGINE_KEYS
    for category in categories or list(hd.HD):
        if category not in hd.HD:
            errors.append(f"hd/{category}: categoría desconocida")
            continue
        options = {"default"} if category == "nose" else set(engine.CHOICES[HD_OPTIONS[category]])
        for option, art in hd.HD[category].items():
            if option not in options:
                errors.append(f"hd/{category}: «{option}» no es una opción del catálogo")
                continue
            if hd.CATEGORIES[category]:
                sprites = {"front": art["front"], "back": art["back"]}
            elif isinstance(art, list):  # equipo en varias zonas (el control y el dron)
                sprites = {str(i): piece for i, piece in enumerate(art)}
            else:
                sprites = {"": art}
            for part, sprite in sprites.items():
                where = f"hd/{category}/{option}" + (f"/{part}" if part else "")
                if sprite is None:
                    continue
                _check_sprite(errors, where, sprite, category, allowed)
                if (
                    category in {"prop", "headwear", "hair"}
                    and isinstance(sprite, dict)
                    and "rows" in sprite
                ):
                    ax, ay = sprite["at"]
                    if sprite["space"] == "figure":
                        ax, ay = ax + hd.OFFSET[0], ay + hd.OFFSET[1]
                    clash = [
                        (ax + i, ay + j)
                        for j, line in enumerate(sprite["rows"])
                        for i, ch in enumerate(line)
                        if ch != "." and ax + i in FACE_X and ay + j in FACE_Y
                    ]
                    if clash and category == "prop":
                        errors.append(
                            f"{where}: dibuja sobre la ventana de la cara ({len(clash)} celdas)"
                        )
    return errors
