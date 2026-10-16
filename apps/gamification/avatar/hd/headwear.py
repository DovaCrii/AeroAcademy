"""Gorros HD (HD-6): los 12 gorros a la resolución de la figura de 64×64, con costuras, luces y detalles de cada oficio.

Cada gorro parte de su pieza de 32 escalada ×2 (misma silueta, misma copa, misma regla de la cara) y le suma detalle encima:
costuras, brillos, nervaduras, bandas y piezas. Un detalle **solo reemplaza celdas que ya tienen color**: nunca agranda ni
recorta la silueta, así el gorro grande y la miniatura cuentan lo mismo. El pase de acabado agrega la luz del borde.

Claves: las de la paleta del gorro (`K T t U`) y `W Y R C Z k g`; nunca `1..5`. Zona: x 6..57 · y 0..29. Los gorros no
tienen capa de atrás (`back` vacío).
"""

from .. import engine
from . import HD, sprite, up2


def _base(name):
    return {y: list(row) for y, row in up2(engine.HEADWEAR[name]["front"]).items()}


def _set(rows, y, x, text):
    """Pone `text` desde (x, y) solo sobre celdas que ya tienen color; un `.` en `text` deja la celda como está."""
    row = rows.get(y)
    if row is None:
        return
    for i, ch in enumerate(text):
        if ch != "." and 0 <= x + i < len(row) and row[x + i] != ".":
            row[x + i] = ch


def _mirror_x(x, width):
    """Columna izquierda de un detalle de ancho `width` reflejado respecto del centro (x 31,5)."""
    return 64 - x - width


def _pair(rows, y, x, text):
    """Un detalle y su espejo a la derecha."""
    _set(rows, y, x, text)
    _set(rows, y, _mirror_x(x, len(text)), text[::-1])


def _sprite(rows):
    ys = sorted(rows)
    xs = [i for y in ys for i, ch in enumerate(rows[y]) if ch != "."]
    x0, x1 = min(xs), max(xs)
    return {
        "front": sprite(
            (x0, ys[0]), ["".join(rows[y][x0 : x1 + 1]) for y in range(ys[0], ys[-1] + 1)]
        ),
        "back": None,
    }


def _hardhat(name):
    rows = _base(name)
    for y, x, text in ((6, 21, "UUU"), (7, 21, "UU"), (8, 20, "UU"), (9, 19, "U")):
        _set(rows, y, x, text)  # brillo del casco en la cúpula
    _set(rows, 15, 16, "t" * 32)  # sombra bajo la cúpula, encima del ala
    for y in range(6, 14):  # la cresta central tiene un filo más oscuro
        _set(rows, y, 31, "k.")
        _set(rows, y, 32, ".k")
    return _sprite(rows)


def _cap(name):
    rows = _base(name)
    _set(rows, 4, 30, "UUUU")  # botón de la cúpula
    for y in range(6, 12):  # costuras: una al centro y dos en diagonal
        _set(rows, y, 31, "tt")
    for y, x in ((6, 24), (7, 24), (8, 23), (9, 23), (10, 22), (11, 22)):
        _pair(rows, y, x, "tt")
    _set(rows, 7, 21, "UU")  # brillo
    _set(rows, 17, 20, "t" * 24)  # puntada de la visera
    return _sprite(rows)


def _beanie():
    rows = _base("beanie")
    for y in range(6, 10):  # nervaduras tejidas en la copa
        for x in (24, 28, 32, 36, 40):
            _set(rows, y, x, "t")
    _set(rows, 1, 28, "WW")  # el pompón esponjoso tiene brillos
    _set(rows, 2, 30, "WWW")
    _set(rows, 3, 34, "WW")
    return _sprite(rows)


def _explorer():
    rows = _base("explorer")
    for x in range(21, 43, 2):  # puntadas de la cinta
        _set(rows, 13, x, "k")
    _set(rows, 7, 22, "UU")  # brillo de la copa
    _set(rows, 17, 14, "kt" * 18)  # costura del ala
    return _sprite(rows)


def _propeller():
    rows = _base("propeller")
    _pair(rows, 2, 19, "WWWW")  # brillo de las aspas
    _pair(rows, 0, 18, "WW")
    _set(rows, 2, 30, "II")  # eje metálico
    _set(rows, 9, 24, "WW")  # brillo del casquete
    return _sprite(rows)


def _headphones():
    rows = _base("headphones")
    _set(rows, 6, 24, "WWWW")  # brillo del arco
    for y, x, text in ((21, 10, "gg"), (22, 10, "g")):
        _pair(rows, y, x, text)  # brillo de las copas
    for y in (22, 24):
        _pair(rows, y, 12, "kkkkkk")  # almohadillas
    return _sprite(rows)


def _headband():
    rows = _base("headband")
    _set(rows, 14, 20, "UUUUUU")
    _set(rows, 14, 38, "UUUUUU")
    for x in range(20, 44, 3):
        _set(rows, 16, x, "k")  # tejido de la cinta
    return _sprite(rows)


def _beret():
    rows = _base("beret")
    for y, x in ((8, 30), (9, 30), (10, 31), (11, 31), (12, 32)):
        _set(rows, y, x, "tt")  # pliegues de la tela
    _set(rows, 6, 22, "UU")
    return _sprite(rows)


def _bucket():
    rows = _base("bucket")
    _set(rows, 17, 16, "kt" * 17)  # puntadas del ala caída
    _set(rows, 7, 20, "UUU")
    _set(rows, 13, 20, "kUkUkUkUkUkUkUkUkUkUkU")  # costura de la cinta
    return _sprite(rows)


def _legionnaire():
    rows = _base("legionnaire")
    for y in (21, 23):  # nervaduras de los cubreorejas
        _set(rows, y, 16, "tttt")
        _set(rows, y, 44, "tttt")
    for y in range(6, 12):
        _set(rows, y, 31, "tt")
    _set(rows, 7, 21, "UU")
    return _sprite(rows)


HD["headwear"].update(
    {
        "hardhat": _hardhat("hardhat"),
        "hardhat_lamp": _hardhat("hardhat_lamp"),
        "cap": _cap("cap"),
        "bump_cap": _cap("bump_cap"),
        "beanie": _beanie(),
        "explorer": _explorer(),
        "propeller": _propeller(),
        "headphones": _headphones(),
        "headband": _headband(),
        "beret": _beret(),
        "bucket": _bucket(),
        "legionnaire": _legionnaire(),
    }
)
