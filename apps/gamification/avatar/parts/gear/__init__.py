"""Equipo HD por disciplina (HD-4 y HD-5): herramientas del oficio dibujadas en el escenario de 80×80.

Un archivo por disciplina: `survey` (topografía), `capture` (captura y RPA), `build` (obra y BIM), `plant` (mecánica) y
`ai` (IA). Cada pieza se registra en `hd.HD["prop"][id]` como un sprite en coordenadas del escenario (`space="stage"`) o
como una lista de sprites cuando el equipo ocupa dos zonas (el control en la mano y el dron en el aire).

Contrato para quien dibuje equipo (docs/AVATAR_RESOLUCION.md, § 3):
  · carril derecho x 56..79 (la mano derecha está en x 60..63 · y 62..65), izquierdo x 0..23, aire y 0..11, suelo y 66..79;
  · ninguna celda en la ventana de la cara (x 30..49 · y 32..45), contorno `K`, interior `k`, ≤ 3 tonos por zona;
  · mínimo legible: herramienta de mano 12×12; alta 4×60; prisma 10×9; dron 22×9; estación en trípode 14×24;
  · claves de la paleta del avatar (`K W Y R C N Z G D Q S k I V X x g`), nunca `1..5`;
  · «se reconoce sin leer el nombre» a 160 px sobre `#0F2A4D` y sobre `#FAF8F3`.

`Canvas` ayuda a dibujar formas simples (rectángulos, discos, líneas) y recorta el sprite a su caja.
"""

from ... import hd


class Canvas:
    """Lienzo del tamaño del escenario: se dibuja con coordenadas absolutas y `sprite()` recorta a la caja usada."""

    def __init__(self):
        self.grid = [["."] * hd.STAGE for _ in range(hd.STAGE)]

    def put(self, x, y, ch):
        if 0 <= x < hd.STAGE and 0 <= y < hd.STAGE:
            self.grid[y][x] = ch

    def rect(self, x, y, w, h, fill=None, edge="K"):
        """Rectángulo relleno (`fill`) con borde de 1 celda (`edge`)."""
        for j in range(h):
            for i in range(w):
                border = i in (0, w - 1) or j in (0, h - 1)
                if border and edge:
                    self.put(x + i, y + j, edge)
                elif not border and fill:
                    self.put(x + i, y + j, fill)

    def fill(self, x, y, w, h, ch):
        for j in range(h):
            for i in range(w):
                self.put(x + i, y + j, ch)

    def disc(self, cx, cy, r, fill, edge="K"):
        """Disco de radio `r` centrado en (cx, cy), con borde."""
        for y in range(cy - r - 1, cy + r + 2):
            for x in range(cx - r - 1, cx + r + 2):
                d = (x - cx) ** 2 + (y - cy) ** 2
                if d <= r * r:
                    self.put(x, y, fill)
                elif edge and d <= (r + 1) ** 2:
                    self.put(x, y, edge)

    def line(self, x0, y0, x1, y1, ch, width=1):
        """Línea entre dos puntos (Bresenham), de `width` celdas de ancho en horizontal."""
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            for k in range(width):
                self.put(x0 + k, y0, ch)
            if (x0, y0) == (x1, y1):
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def paste(self, x, y, rows):
        """Pega filas de texto (`.` es transparente)."""
        for j, line in enumerate(rows):
            for i, ch in enumerate(line):
                if ch != ".":
                    self.put(x + i, y + j, ch)

    def hand(self, x=60, y=62):
        """La mano derecha que sujeta la herramienta (4×4; en HD-7 se redibuja por pose)."""
        self.paste(x, y, [".KK.", "KSSK", "KSSK", ".KK."])

    def sprite(self, box=None):
        """Sprite recortado a la caja de lo dibujado (o a `box = (x0, y0, x1, y1)`)."""
        cells = [(x, y) for y, row in enumerate(self.grid) for x, ch in enumerate(row) if ch != "."]
        x0, y0, x1, y1 = box or (
            min(x for x, _ in cells),
            min(y for _, y in cells),
            max(x for x, _ in cells),
            max(y for _, y in cells),
        )
        rows = ["".join(self.grid[y][x0 : x1 + 1]) for y in range(y0, y1 + 1)]
        return hd.sprite((x0, y0), rows, space="stage")


from . import (  # noqa: E402,F401  (registran el equipo en `hd.HD["prop"]`)
    ai,
    build,
    capture,
    plant,
    survey,
)
