"""Equipo de IA (HD-5): laptop con un grafo de nodos en la pantalla."""

from ... import hd
from . import Canvas

NODES = [(62, 47), (73, 47), (67, 50), (62, 53), (73, 53)]  # esquinas de nodos de 4×4 (x, y)
EDGES = [(0, 2), (1, 2), (2, 3), (2, 4)]


def _laptop_ai():
    c = Canvas()
    c.rect(59, 44, 20, 16, "D")
    c.fill(61, 46, 16, 12, "V")
    for a, b in EDGES:  # primero las líneas y encima los nodos
        (x0, y0), (x1, y1) = NODES[a], NODES[b]
        c.line(x0 + 1, y0 + 1, x1 + 1, y1 + 1, "k", width=2)
    for x, y in NODES:
        c.rect(x, y, 4, 4, "Y", edge="K")
        c.put(x + 1, y + 1, "W")
    c.rect(58, 60, 22, 3, "Z")
    c.paste(64, 61, ["kkkkkkkkkkkk"])
    c.hand(60, 62)
    return c.sprite()


hd.HD["prop"]["laptop_ai"] = _laptop_ai()
