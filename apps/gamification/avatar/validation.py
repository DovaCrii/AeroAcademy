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
                  "bucket"]),
    "glasses": ("glasses", "GLASSES", False, "FLgKEW", (8, 13),
                ["none", "round", "square", "aviator", "goggles", "sunglasses", "monocle"]),
    "outfits": ("outfits", "OUTFITS", False, "OoAaWKYRCNZ", (20, 28),
                ["tshirt", "hoodie", "hivis_vest", "field_vest", "jacket", "apron", "labcoat", "shirt_tie",
                 "flight_jacket", "sweater"]),
    "neckwear": ("outfits", "NECKWEAR", False, "OoAaWKYRCNZSs", (18, 25),
                 ["none", "lanyard", "scarf", "tie", "bandana"]),
}  # fmt: skip

LABEL_ATTR = {
    "hair": "LABELS", "eyes": "LABELS_EYES", "brows": "LABELS_BROWS", "mouths": "LABELS_MOUTHS",
    "facial_hair": "LABELS", "headwear": "LABELS", "glasses": "LABELS", "outfits": "LABELS_OUTFITS",
    "neckwear": "LABELS_NECKWEAR",
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
