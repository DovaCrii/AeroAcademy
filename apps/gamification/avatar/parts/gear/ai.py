"""Equipo de IA (HD-5): laptop con un grafo de nodos en la pantalla."""

from ... import hd
from . import Canvas

# Pantalla de 15×9 (x 61..75 · y 49..57): nodos cian (`C`) y violeta-pantalla (`V`) unidos por líneas.
GRAPH = [
    "VVVVVVVVVVVVVVV",
    "VCCVVVVVVVVVCCV",
    "VCCkkVVVVVkkCCV",
    "VVVVkkCCkkVVVVV",
    "VVVVVkCCkVVVVVV",
    "VCCkkkVVkkkCCVV",
    "VCCVVVVVVVVCCVV",
    "VVVVVVVVVVVVVVV",
    "VVVVVVVVVVVVVVV",
]


def _laptop_ai():
    c = Canvas()
    c.rect(59, 47, 19, 13, "D")
    c.paste(61, 49, GRAPH)
    c.rect(58, 60, 21, 3, "Z")
    c.paste(64, 61, ["kkkkkkkkkk"])
    c.hand(60, 62)
    return c.sprite()


hd.HD["prop"]["laptop_ai"] = _laptop_ai()
