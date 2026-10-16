"""Equipo de captura y RPA (HD-4): control de dron con su dron en el aire, escáner láser en trípode y cámara."""

from ... import hd
from . import Canvas
from .survey import _tripod

CONTROLLER = [
    ".Z............Z.",
    ".Z............Z.",
    "KKKKKKKKKKKKKKKK",
    "KDDDDKKKKKKDDDDK",
    "KDKKDKVVVVKDKKDK",
    "KDKWDKVCCVKDKWDK",
    "KDDDDKVVVVKDDDDK",
    "KDRDDKKKKKKDDGDK",
    ".KDDDDDDDDDDDDK.",
    "..KKKKKKKKKKKK..",
]
DRONE = [
    "ZZZZZZZ........ZZZZZZZ",
    "...KK............KK...",
    "...KK............KK...",
    "..KDDKKKKKKKKKKKKDDK..",
    "...KKDDDDDCCDDDDDKK...",
    ".....KDDDVVVVDDDK.....",
    "......KKDDQQDDKK......",
    "........K....K........",
    ".......KK....KK.......",
]


def _drone_controller():
    c = Canvas()
    c.paste(62, 53, CONTROLLER)
    c.hand(60, 60)
    held = c.sprite()
    d = Canvas()
    d.paste(56, 1, DRONE)  # el dron flota en el carril del aire
    return [held, d.sprite()]


def _laser_scanner():
    c = Canvas()
    _tripod(c, 69, 62, 78, 8)
    c.rect(64, 56, 11, 6, "D")  # base giratoria
    c.rect(65, 44, 9, 12, "I")  # cabezal
    c.fill(67, 47, 5, 4, "K")  # ventana del láser
    c.fill(68, 48, 3, 2, "Q")
    c.paste(65, 52, ["KKKKKKKKK"])
    c.disc(69, 43, 2, "Z")
    c.hand(61, 61)
    return c.sprite()


def _camera():
    c = Canvas()
    c.rect(62, 55, 15, 9, "D")  # cuerpo
    c.rect(66, 52, 6, 3, "Z")  # visor
    c.disc(70, 59, 3, "K", edge="K")
    c.disc(70, 59, 2, "C")
    c.put(69, 58, "W")
    c.paste(63, 56, ["QQ"])  # botón de disparo
    c.paste(62, 55, ["KKKKKKKKKKKKKKK"])
    c.hand(60, 61)
    return c.sprite()


hd.HD["prop"].update(
    {
        "drone_controller": _drone_controller(),
        "laser_scanner": _laser_scanner(),
        "camera": _camera(),
    }
)
