"""Equipo de mecánica y planta (HD-5): llave inglesa, tramo de cañería con dos bridas al hombro y volante de válvula."""

from ... import hd
from . import Canvas


def _wrench():
    c = Canvas()
    c.rect(68, 40, 4, 31, "Z")  # mango
    c.paste(69, 42, ["I"] * 1)
    for y in range(44, 70):
        c.put(69, y, "I")
    c.rect(65, 34, 10, 8, "Z")  # cabeza
    c.fill(68, 34, 4, 5, ".")  # boca abierta
    c.paste(68, 34, ["K..K", "K..K", "K..K", "K..K", "KKKK"][:5])
    c.paste(65, 34, ["KKK", "KZK"])
    c.hand(61, 61)
    return c.sprite()


def _pipe_spool():
    c = Canvas()
    c.rect(56, 43, 24, 8, "Z")  # tubo
    c.fill(58, 44, 20, 1, "I")  # luz arriba
    c.fill(58, 49, 20, 1, "D")  # sombra abajo
    c.paste(66, 43, ["KkkK"] * 1)
    for x in (54, 77):  # bridas con pernos
        c.rect(x, 40, 4, 14, "I")
        c.put(x + 1, 42, "D")
        c.put(x + 1, 51, "D")
    c.hand(60, 52)
    return c.sprite()


def _valve_wheel():
    c = Canvas()
    c.disc(68, 57, 7, "R")
    c.disc(68, 57, 5, ".", edge="K")
    for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        for k in range(1, 6):
            c.put(68 + dx * k, 57 + dy * k, "K")
    c.disc(68, 57, 1, "Y")
    c.hand(60, 61)
    return c.sprite()


hd.HD["prop"].update(
    {
        "wrench": _wrench(),
        "pipe_spool": _pipe_spool(),
        "valve_wheel": _valve_wheel(),
    }
)
