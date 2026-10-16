"""Equipo de obra y BIM (HD-5): tablet, laptop con cubo BIM, rollo de planos, escalímetro, tablilla, calculadora,
cono de tránsito y taza."""

from ... import hd
from . import Canvas

CUBE = [  # cubo isométrico BIM de 12×12: cara de arriba blanca, lado izquierdo gris, derecho oscuro y arista de luz
    ".....KK.....",
    "...KKWWKK...",
    ".KKWWWWWWKK.",
    "KWWWWWWWWWWK",
    "KKKWWWWWWKKK",
    "KZZKKWWKKDDK",
    "KZZZKWWKDDDK",
    "KZZZKWWKDDDK",
    "KZZZKWWKDDDK",
    ".KZZKWWKDDK.",
    "..KZKWWKDK..",
    "...KKKKKK...",
]


def _tablet():
    c = Canvas()
    c.rect(62, 46, 16, 17, "D")
    c.fill(63, 47, 14, 15, "V")
    c.paste(64, 48, CUBE)
    c.paste(68, 61, ["ZZ"])  # botón de inicio
    c.hand(60, 60)
    return c.sprite()


def _laptop(screen):
    c = Canvas()
    c.rect(59, 44, 20, 16, "D")  # tapa
    c.fill(61, 46, 16, 12, "V")
    screen(c)
    c.rect(58, 60, 22, 3, "Z")  # base con teclado
    c.paste(64, 61, ["kkkkkkkkkkkk"])
    c.hand(60, 62)
    return c.sprite()


def _bim_screen(c):
    c.paste(63, 46, CUBE)


def _laptop_bim():
    return _laptop(_bim_screen)


def _plans_roll():
    c = Canvas()
    c.rect(65, 40, 9, 26, "W")
    c.fill(66, 42, 7, 1, "I")
    for y in (45, 61):
        c.fill(66, y, 7, 2, "R")
    c.fill(66, 52, 3, 6, "C")  # tramo azul de un plano
    c.paste(65, 40, ["KKKKKKKKK"])
    c.hand(61, 60)
    return c.sprite()


def _scale_ruler():
    c = Canvas()
    c.rect(10, 28, 6, 43, "Y")
    for y in range(30, 70, 3):
        c.paste(10, y, ["KKK"])
    c.paste(12, 28, ["K"])
    c.hand(16, 62)
    return c.sprite()


def _clipboard():
    c = Canvas()
    c.rect(62, 46, 15, 19, "N")
    c.rect(64, 49, 11, 14, "W")
    c.rect(66, 44, 7, 4, "Z")  # pinza
    for y in (52, 55, 58, 61):
        c.paste(66, y, ["kkkkkkk"])
    c.paste(65, 52, ["G"])
    c.paste(65, 55, ["G"])
    c.hand(60, 62)
    return c.sprite()


def _calculator():
    c = Canvas()
    c.rect(64, 50, 11, 16, "D")
    c.fill(66, 52, 7, 3, "V")
    for row in range(3):
        for col in range(3):
            c.fill(66 + col * 3, 57 + row * 3, 2, 2, "Q" if col == 2 else "Z")
    c.hand(60, 61)
    return c.sprite()


def _traffic_cone():
    c = Canvas()
    for i, y in enumerate(range(64, 77)):
        half = 1 + i * 4 // 12  # el cono se ensancha hacia la base
        c.paste(70 - half - 1, y, ["K" + "X" * (2 * half) + "K"])
    c.paste(69, 64, ["KK"])
    c.paste(67, 69, ["KxxxxK"])
    c.paste(66, 72, ["KxxxxxxK"])
    c.rect(64, 76, 13, 2, "X")
    c.paste(64, 76, ["KKKKKKKKKKKKK"])
    return c.sprite()


def _mug():
    c = Canvas()
    c.paste(66, 50, ["..W...W", "...W.W.", "..W...W", "...W..."][:3])
    c.rect(64, 56, 9, 10, "R")
    c.paste(65, 57, ["WW"])
    c.rect(72, 58, 4, 6, None, "K")  # asa
    c.fill(64, 57, 1, 1, "K")
    c.hand(60, 60)
    return c.sprite()


hd.HD["prop"].update(
    {
        "tablet": _tablet(),
        "laptop_bim": _laptop_bim(),
        "plans_roll": _plans_roll(),
        "scale_ruler": _scale_ruler(),
        "clipboard": _clipboard(),
        "calculator": _calculator(),
        "traffic_cone": _traffic_cone(),
        "mug": _mug(),
    }
)
