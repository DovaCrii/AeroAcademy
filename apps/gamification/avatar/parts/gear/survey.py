"""Equipo de topografía (HD-4): jalón con prisma, rover GNSS, estación total sobre trípode y mira de nivelación."""

from ... import hd
from . import Canvas

PRISM = [
    "...KKKK...",
    "..KYYYYK..",
    ".KYKKKKYK.",
    "KYKCWCCKYK",
    "KYKWCCCKYK",
    "KYKCCCCKYK",
    ".KYKKKKYK.",
    "..KYYYYK..",
    "...KDDK...",
]
DOME = [
    "...KKKK...",
    "..KZZZZK..",
    ".KZIIIIZK.",
    "KZIIZZIIZK",
    "KDDDDDDDDK",
    "..KKKKKK..",
]


def _pole(c, x, y0, y1, stripes):
    """Jalón de 2 celdas de cuerpo y borde `K`; `stripes` da la clave de cada fila (franjas rojo/blanco)."""
    for y in range(y0, y1):
        c.put(x, y, "K")
        c.put(x + 1, y, stripes(y))
        c.put(x + 2, y, stripes(y))
        c.put(x + 3, y, "K")
    c.paste(x + 1, y1, ["KK"])


def _prism_pole():
    c = Canvas()
    c.paste(62, 1, PRISM)
    _pole(c, 65, 10, 72, lambda y: "R" if (y // 4) % 2 == 0 else "W")
    c.hand(61, 61)
    return c.sprite()


def _gnss_rover():
    c = Canvas()
    c.paste(62, 2, DOME)
    c.paste(65, 8, ["KDDK"] * 3)
    _pole(c, 65, 11, 72, lambda y: "I" if (y // 8) % 2 == 0 else "Z")
    for y in range(24, 72, 8):  # anillos amarillos de medición
        c.paste(65, y, ["KYYK"])
    c.paste(69, 52, ["KKKKKKKK", "KVVVVVVK", "KVCCCCVK", "KVVVVVVK", "KDDDDDDK", "KKKKKKKK"])
    c.hand(61, 61)
    return c.sprite()


def _tripod(c, cx, top, bottom, spread):
    """Trípode de patas de madera (`N`) con una plataforma en lo alto."""
    c.fill(cx - 7, top, 14, 2, "Z")
    c.rect(cx - 7, top, 14, 2, None, "K")
    for dx in (-spread, 0, spread):
        c.line(cx + dx // 3, top + 2, cx + dx, bottom, "K", width=1)
        c.line(cx + dx // 3 + 1, top + 2, cx + dx + 1, bottom, "N", width=2)
        c.line(cx + dx // 3 + 3, top + 2, cx + dx + 3, bottom, "K", width=1)


def _total_station():
    c = Canvas()
    _tripod(c, 69, 62, 78, 8)
    c.rect(64, 49, 11, 13, "D")  # cuerpo del instrumento
    c.rect(66, 46, 7, 3, "Z")  # asa
    c.fill(67, 52, 5, 4, "V")  # pantalla
    c.rect(67, 52, 5, 4, None, "K")
    c.disc(69, 59, 1, "C")
    c.rect(75, 51, 4, 6, "I")  # catalejo
    c.paste(75, 53, ["KKKK"])
    c.hand(61, 61)
    return c.sprite()


def _level_staff():
    c = Canvas()
    for y in range(3, 75):
        band = "K" if (y // 2) % 2 == 0 else "W"
        if y % 10 == 5:
            band = "R"
        c.paste(66, y, ["K" + band * 2 + "K"])
    c.paste(66, 2, ["KKKK"])
    c.paste(66, 75, ["KKKK"])
    c.hand(61, 61)
    return c.sprite()


hd.HD["prop"].update(
    {
        "prism_pole": _prism_pole(),
        "gnss_rover": _gnss_rover(),
        "total_station": _total_station(),
        "level_staff": _level_staff(),
    }
)
