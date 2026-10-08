"""Ropa del torso y cuello. Contrato:

OUTFITS = {id: rows}   DECORAN las celdas 'O' del cuerpo base (x 6..25 · y 20..27): solo se aplican donde el cuerpo
                       tiene ropa. No cambian la silueta. Úsalas para costuras, cuellos, bolsillos, franjas, capucha.
                       Filas permitidas: y 20..28.
NECKWEAR = {id: rows}  se pinta SOBRE el cuello y el pecho (x 12..19 · y 18..24), sin restricción de celdas.
                       Filas permitidas: y 18..25.
LABELS_OUTFITS / LABELS_NECKWEAR = {id: nombre en español}.
Claves de color permitidas: O (ropa), o (sombra), A (acento), a (acento oscuro), W, K, Y, R, C, N, Z; en NECKWEAR también S y s (piel).
La ropa va con el color que elija la persona (O/o/A/a): usa esas claves para lo principal y las fijas solo para detalles
(botones, franjas reflectantes en Y/W).

OUTFITS ids obligatorios: tshirt, hoodie, hivis_vest (chaleco reflectante), field_vest (chaleco de campo con bolsillos),
jacket, apron (delantal de taller), labcoat (bata), shirt_tie (camisa), flight_jacket (chaqueta de vuelo), sweater.
NECKWEAR ids obligatorios: none, lanyard (credencial colgada), scarf (bufanda), tie (corbata), bandana.

Mapa útil: cuello x14..17 (y18..19); hombros y20; torso x8..23 y20..27; mangas x5..6 y x25..26 (y21..25);
el eje de simetría queda entre x15 y x16.
"""

from ..art import full, sym

LABELS_OUTFITS = {
    "tshirt": "Polera",
    "hoodie": "Polerón con capucha",
    "hivis_vest": "Chaleco reflectante",
    "field_vest": "Chaleco de campo",
    "jacket": "Chaqueta con cierre",
    "apron": "Delantal de taller",
    "labcoat": "Bata",
    "shirt_tie": "Camisa",
    "flight_jacket": "Chaqueta de vuelo",
    "sweater": "Sweater",
}
LABELS_NECKWEAR = {
    "none": "Sin accesorio",
    "lanyard": "Credencial",
    "scarf": "Bufanda",
    "tie": "Corbata",
    "bandana": "Pañuelo",
}


def _o(*lines):
    """Arma las filas y20..y27. Cada línea es (manga/borde x5..7, torso x8..15) y se espeja al otro lado."""
    rows = {}
    for i, (sl, tor) in enumerate(lines):
        if len(sl) != 3 or len(tor) != 8:
            raise ValueError(f"línea {i}: manga 3 y torso 8 caracteres: {sl!r} {tor!r}")
        rows[20 + i] = sym("." * 5 + sl + tor)
    return rows


def _n(rows_by_y):
    """Filas de accesorio de cuello: {y: mitad izquierda de 16}."""
    return {y: sym(left) for y, left in rows_by_y.items()}


def _put(rows, y, x, ch):
    """Cambia un solo píxel (detalles asimétricos)."""
    r = rows[y]
    rows[y] = full(r[:x] + ch + r[x + 1 :])


_tshirt = _o(
    ("...", "....aaaa"),
    ("...", "o....aaa"),
    ("...", "o......."),
    ("...", "o......."),
    ("...", "o......."),
    ("oo.", "o......."),
    ("...", "o......."),
    ("...", "oooooooo"),
)

_hoodie = _o(
    ("...", ".AAooooo"),
    ("...", "..AAAoo."),
    ("...", ".....W.."),
    ("...", ".....W.."),
    ("...", ".....a.."),
    ("oo.", ".ooooooo"),
    ("...", ".o.....o"),
    ("aaa", "aaaaaaaa"),
)

_hivis = _o(
    ("aa.", "..YY.AAA"),
    ("AA.", "..YY..AA"),
    ("AA.", "..YY...K"),
    ("AA.", "..YY...K"),
    ("aa.", "..YY...K"),
    ("YYY", "YYYYYYYY"),
    ("AA.", "..YY...K"),
    ("...", "..YY...K"),
)

_field = _o(
    ("aa.", "...aaaaa"),
    ("AA.", "...AAaaa"),
    ("AA.", ".aaaa..K"),
    ("AA.", ".aOOa..K"),
    ("AA.", ".aaaa..K"),
    ("aa.", "......ZK"),
    ("AA.", ".aaaa..K"),
    ("...", ".aOOa..o"),
)

_jacket = _o(
    ("...", "..aaaaaa"),
    ("...", "...aAAAZ"),
    ("...", "......AZ"),
    ("...", "......oZ"),
    ("...", ".oooo.oZ"),
    ("aa.", "......oZ"),
    ("...", "......oZ"),
    ("aaa", "aaaaaaZa"),
)

_apron = _o(
    ("...", "...a...."),
    ("...", "...a...."),
    ("...", "..aaaaaa"),
    ("...", "..AAAAAA"),
    ("...", "..AAAAAA"),
    ("...", "..AAaaaa"),
    ("...", "..AAaooo"),
    ("...", "..aaaaaa"),
)

_lab = _o(
    ("...", "..ooAAAA"),
    ("...", "...ooAAA"),
    ("...", "....ooAA"),
    ("...", ".....ooo"),
    ("...", ".ooo..oW"),
    ("aa.", ".o.o..oo"),
    ("...", ".ooo..oW"),
    ("...", "oooo..oo"),
)

_shirt = _o(
    ("...", "..aaWWOa"),
    ("...", "...aaaOa"),
    ("...", "......aW"),
    ("...", "......oW"),
    ("...", "......oO"),
    ("oo.", "......oW"),
    ("...", "......oO"),
    ("...", "......oW"),
)

_flight = _o(
    ("aa.", "..aaaaaa"),
    ("AA.", "..aAAAAZ"),
    ("AA.", ".aaa..oZ"),
    ("AA.", ".CCC..oZ"),
    ("aa.", ".CWC..oZ"),
    ("aa.", ".CCC..oZ"),
    ("...", "......oZ"),
    ("...", "aaaaaaZa"),
)

_sweater = _o(
    ("...", "..aaaaaa"),
    ("...", "...aaaoo"),
    ("...", "..o.o.o."),
    ("...", "..o.o.o."),
    ("...", "..o.o.o."),
    ("aa.", "..o.o.o."),
    ("...", "..o.o.o."),
    ("aaa", "aaaaaaaa"),
)

# detalles asimétricos
for _y, _x in ((22, 10), (22, 11), (23, 10), (23, 11)):
    _put(_tshirt, _y, _x, "A")
for _y in (23, 24, 25):
    for _x in (20, 21, 22):
        _put(_flight, _y, _x, "O")
for _x in (20, 21, 22):
    _put(_flight, 24, _x, "o")
    _put(_field, 22, 31 - _x - 0, "a") if False else None
_put(_field, 22, 10, "a")
_put(_field, 22, 11, "a")
_put(_apron, 24, 14, "Y")
_put(_apron, 24, 13, "R")
_put(_apron, 24, 18, "Z")
_put(_lab, 24, 11, "C")
_put(_lab, 25, 11, "R")
_put(_flight, 24, 11, "Y")
_put(_hoodie, 22, 18, "W")
_put(_hoodie, 23, 18, "W")

OUTFITS = {
    "tshirt": _tshirt,
    "hoodie": _hoodie,
    "hivis_vest": _hivis,
    "field_vest": _field,
    "jacket": _jacket,
    "apron": _apron,
    "labcoat": _lab,
    "shirt_tie": _shirt,
    "flight_jacket": _flight,
    "sweater": _sweater,
}

# ================================================================ NECKWEAR (y18..25)

# credencial: cordón en V y tarjeta
_lanyard = _n(
    {
        18: "............A...",
        19: "............A...",
        20: "............A...",
        21: ".............A..",
        22: ".............A..",
        23: "..............A.",
        24: "...........KKKKZ",
        25: "...........KWWWW",
    }
)
_put(_lanyard, 25, 13, "C")
_put(_lanyard, 25, 14, "C")

# bufanda: vuelta alrededor del cuello y cola colgando
_scarf = _n(
    {
        18: "...........AAAAA",
        19: "..........KAaAAA",
        20: "...........aAAAA",
    }
)
for _y, _row in {
    21: "." * 17 + "KAAAK" + "." * 10,
    22: "." * 17 + "KaAAK" + "." * 10,
    23: "." * 17 + "KAAAK" + "." * 10,
    24: "." * 17 + "KaAAK" + "." * 10,
    25: "." * 17 + "WKWKW" + "." * 10,
}.items():
    _scarf[_y] = full(_row)

# corbata
_tie = _n(
    {
        20: "...............a",
        21: "...............a",
        22: "..............aA",
        23: "..............AA",
        24: "..............AA",
        25: "...............A",
    }
)
_put(_tie, 23, 14, "a")
_put(_tie, 24, 17, "a")

# pañuelo al cuello (triángulo con lunares)
_bandana = _n(
    {
        18: "...........AAAAA",
        19: "..........KAAAAA",
        20: "............AAAA",
        21: ".............AAA",
        22: "..............AA",
        23: "...............A",
    }
)
_put(_bandana, 19, 13, "W")
_put(_bandana, 20, 16, "W")
_put(_bandana, 21, 14, "W")
_put(_bandana, 21, 17, "W")
_put(_bandana, 22, 15, "a")

NECKWEAR = {
    "none": {},
    "lanyard": _lanyard,
    "scarf": _scarf,
    "tie": _tie,
    "bandana": _bandana,
}
