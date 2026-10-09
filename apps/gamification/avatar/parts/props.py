"""Herramientas en la mano (accesorio de oficio). Contrato:

PROPS = {id: rows}  con rows = {y: fila de 32 caracteres}; se pintan AL FINAL, encima de todo, y no tocan la cara.
Van al costado del cuerpo: a la derecha (x 23..31) o a la izquierda (x 0..8), y 0..31.
Claves de color fijas (no cambian con la configuración): K contorno, W blanco, Y amarillo, R rojo, C cian, N café,
Z gris, G verde, D gris oscuro, Q naranja, S/s piel (la mano).
LABELS_PROPS = {id: nombre en español}.

IDs obligatorios: none, tablet, prism_pole, drone_controller, scale_ruler, mug.
"""

from ..art import full

LABELS_PROPS = {
    "none": "Sin herramienta",
    "tablet": "Tablet",
    "prism_pole": "Jalón con prisma",
    "gnss_rover": "Rover GNSS",
    "drone_controller": "Control de dron",
    "scale_ruler": "Escalímetro",
    "mug": "Taza de café",
    "plans_roll": "Rollo de planos",
    "wrench": "Llave inglesa",
    "clipboard": "Tablilla de inspección",
    "calculator": "Calculadora",
    "camera": "Cámara de terreno",
    "laser_scanner": "Escáner láser",
}


def _p(x, *lines, y0):
    """Pieza: cada línea se coloca en la fila y0, y0+1, ... desde la columna x."""
    rows = {}
    for i, text in enumerate(lines):
        rows[y0 + i] = full("." * x + text + "." * (32 - x - len(text)))
    return rows


def _merge(*parts):
    rows = {}
    for part in parts:
        for y, line in part.items():
            old = rows.get(y)
            if old is None:
                rows[y] = line
            else:
                rows[y] = full(
                    "".join(b if b != "." else a for a, b in zip(old, line, strict=True))
                )
    return rows


# --- a la derecha ------------------------------------------------------------------------------------

_tablet = _p(
    24,
    "KKKKKKKK",
    "KCCWWWCK",
    "KCWCCCCK",
    "KCCCWWCK",
    "KKKKKKKK",
    y0=23,
)

_prism_pole = _merge(
    _p(28, ".KK.", "KYYK", "KRRK", "KYYK", ".KK.", y0=0),
    _p(28, *["KZWK"] * 6, y0=5),
    _p(28, *["KZWK", "KYWK", "KZWK", "KYWK", "KZWK", "KYWK"], y0=11),
    _p(28, *["KZWK"] * 8, y0=17),
    _p(26, "SSKZWK", "SSKZWK", y0=25),
    _p(28, "KZWK", "KZWK", y0=27),
    _p(29, "KK", "KK", "KK", y0=29),
)

_gnss_rover = _merge(
    _p(28, ".ZZ.", "ZWWZ", "KKKK", ".CK.", y0=0),
    _p(28, *["KDDK"] * 2, y0=4),
    _p(28, *["KZWK"] * 8, y0=6),
    _p(28, *["KZWK", "KYWK"] * 3, y0=14),
    _p(28, *["KZWK"] * 5, y0=20),
    _p(26, "SSKZWK", "SSKZWK", y0=25),
    _p(28, "KZWK", "KZWK", y0=27),
    _p(29, "KK", "KK", "KK", y0=29),
)

_drone_controller = _merge(
    _p(30, "Z", "Z", "Z", y0=20),
    _p(24, "Z", "Z", "Z", y0=21),
    _p(23, "KKKKKKKKK", "KDRDDDRDK", "KDDCCCDDK", "KDRDDDRDK", "KKKKKKKKK", y0=24),
)

_scale_ruler = _merge(
    _p(0, "KKKK", y0=13),
    _p(0, *["KYYK", "KYKK"] * 8, y0=14),
    _p(0, "KKKK", y0=30),
    _p(4, "S", "S", y0=25),
)

_mug = _p(
    26,
    ".W..W.",
    "..W...",
    "KKKK..",
    "KRRKK.",
    "KRWK.K",
    "KRRKK.",
    "KKKK..",
    y0=20,
)

_plans_roll = _merge(
    _p(
        28,
        ".KK.",
        "KWWK",
        "KWCK",
        "KWWK",
        "KRRK",
        "KWWK",
        "KWCK",
        "KWWK",
        "KWWK",
        "KRRK",
        "KWWK",
        "KWWK",
        ".KK.",
        y0=14,
    ),
    _p(27, "SS", "SS", y0=25),
)

_wrench = _merge(
    _p(28, "ZZ.Z", "ZZZZ", ".ZZ.", y0=11),
    _p(28, *[".ZD."] * 9, y0=14),
    _p(28, *[".ZD."] * 6, y0=23),
    _p(28, ".KK.", y0=29),
    _p(27, "SS", "SS", y0=25),
)

_clipboard = _p(
    26,
    "KKZZKK",
    "KNNNNK",
    "KWWWWK",
    "KWKKWK",
    "KWWWWK",
    "KWKKKK",
    "KWWWWK",
    "KKKKKK",
    y0=20,
)

_calculator = _p(
    27,
    "KKKKK",
    "KCCCK",
    "KDDDK",
    "KDRDK",
    "KDDDK",
    "KKKKK",
    y0=23,
)

_camera = _p(
    24,
    "..KKK.",
    ".KDDDKK",
    "KDKWKDDK",
    "KDKCKDRK",
    ".KDDDDK",
    "..KKKK",
    y0=23,
)


def _right(*lines, y0):
    """Como `_p`, pero cada línea queda pegada al borde derecho de la grilla."""
    rows = {}
    for i, text in enumerate(lines):
        rows[y0 + i] = full("." * (32 - len(text)) + text)
    return rows


_laser_scanner = _merge(
    _right("KKKKK", "KDQDK", "KDCDK", "KDDDK", "KKKKK", y0=12),
    _right("KZ", "KZ", y0=17),
    _right("KZZK", "K.ZK", "K..ZK", "K...ZK", "K....ZK", "K.....ZK", "K.....ZK", "K.....ZK", y0=19),
    _right("K......ZK", "K......ZK", "K.....KKK", y0=27),
)
# --- pines de solapa (pecho derecho de quien mira); se desbloquean por nivel ---------------------------------

LABELS_PINS = {
    "none": "Sin pin",
    "compass": "Brújula",
    "hardhat_pin": "Casquito de obra",
    "theodolite_pin": "Teodolito dorado",
}

PINS = {
    "none": {},
    "compass": _p(19, ".KK.", "KRWK", "KWRK", ".KK.", y0=21),
    "hardhat_pin": _p(19, ".YY.", "YYYY", "KKKK", y0=22),
    "theodolite_pin": _p(19, ".YY.", "KYYK", ".YY.", "Y..Y", y0=21),
}

PROPS = {
    "none": {},
    "tablet": _tablet,
    "prism_pole": _prism_pole,
    "gnss_rover": _gnss_rover,
    "drone_controller": _drone_controller,
    "scale_ruler": _scale_ruler,
    "mug": _mug,
    "plans_roll": _plans_roll,
    "wrench": _wrench,
    "clipboard": _clipboard,
    "calculator": _calculator,
    "camera": _camera,
    "laser_scanner": _laser_scanner,
}
