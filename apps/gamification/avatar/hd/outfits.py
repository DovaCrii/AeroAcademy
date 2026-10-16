"""Ropa HD (HD-7): detalle de cada prenda a la resolución de la figura de 64×64.

Cada prenda parte de su decoración de 32 escalada ×2 y le suma detalle encima: bolsillos, cierres, botones, solapas,
franjas reflectantes y parches. El motor pinta la ropa **solo sobre las celdas `O` del cuerpo** (`only_on`), así que un
detalle nunca cambia la silueta: lo que cae fuera del torso se descarta solo.

Mapa (figura de 64): torso x 16..47 · y 40..55, mangas x 8..15 y 48..55, cuello x 28..35, eje de simetría entre x 31 y 32,
pecho izquierdo x 20..29 y derecho x 34..43. Claves: `O o A a` (el color elegido) y las fijas `W K Y R C Z k` para
detalles pequeños (botones, franjas); nunca `1..5`.
"""

from .. import engine
from . import HD, sprite, up2

LEFT, RIGHT = 20, 38  # esquinas de los bolsillos del pecho


class Torso:
    """Filas de una prenda en coordenadas de la figura de 64, con utilidades de dibujo."""

    def __init__(self, name):
        self.rows = {y: list(row) for y, row in up2(engine.OUTFITS[name]).items()}

    def put(self, x, y, ch):
        row = self.rows.setdefault(y, ["."] * 64)
        if 0 <= x < 64:
            row[x] = ch

    def paste(self, x, y, lines):
        for j, line in enumerate(lines):
            for i, ch in enumerate(line):
                if ch != ".":
                    self.put(x + i, y + j, ch)

    def fill(self, x, y, w, h, ch):
        for j in range(h):
            for i in range(w):
                self.put(x + i, y + j, ch)

    def pocket(self, x, y, w=6, h=5, edge="a", flap="A"):
        """Bolsillo con tapa: borde de 1 celda y una tapa de una fila arriba."""
        self.fill(x, y, w, h, edge)
        self.fill(x + 1, y + 1, w - 2, h - 2, ".")
        self.fill(x, y, w, 1, flap)

    def zipper(self, y0, y1, x=31):
        for y in range(y0, y1 + 1):
            self.put(x, y, "k")
            self.put(x + 1, y, "Z" if y % 2 else "k")
        self.paste(x - 1, y0, ["ZZZZ"])  # cabeza del cierre

    def buttons(self, y0, y1, step=4, ch="W"):
        for y in range(y0, y1 + 1, step):
            self.fill(31, y, 2, 2, ch)

    def stripe(self, y, x0=16, x1=47, ch="Y", dot="k"):
        """Franja reflectante de 2 filas con puntadas."""
        self.fill(x0, y, x1 - x0 + 1, 2, ch)
        for x in range(x0, x1 + 1, 4):
            self.put(x, y + 1, dot)

    def line(self, x0, y0, x1, y1, ch):
        steps = max(abs(x1 - x0), abs(y1 - y0))
        for i in range(steps + 1):
            t = i / steps if steps else 0
            self.put(round(x0 + (x1 - x0) * t), round(y0 + (y1 - y0) * t), ch)

    def sprite(self):
        ys = sorted(y for y, row in self.rows.items() if any(c != "." for c in row))
        xs = [i for y in ys for i, c in enumerate(self.rows[y]) if c != "."]
        x0, x1 = min(xs), max(xs)
        rows = [
            "".join(self.rows.get(y, ["."] * 64)[x0 : x1 + 1]) for y in range(ys[0], ys[-1] + 1)
        ]
        return sprite((x0, ys[0]), rows)


def _tshirt():
    t = Torso("tshirt")
    t.paste(22, 44, ["AAAA", "AWWA", "AAAA"])  # logo del pecho
    t.fill(16, 54, 32, 1, "k")  # dobladillo
    return t.sprite()


def _hoodie():
    t = Torso("hoodie")
    t.paste(27, 44, ["W", "W", "W", "W", "W"])  # cordones
    t.paste(36, 44, ["W", "W", "W", "W", "W"])
    t.fill(24, 50, 16, 5, "o")  # bolsillo canguro
    t.fill(25, 51, 14, 3, ".")
    t.fill(30, 50, 3, 5, "k")
    return t.sprite()


def _hivis():
    t = Torso("hivis_vest")
    t.stripe(44)
    t.stripe(50)
    t.zipper(40, 55)
    t.pocket(LEFT, 46, 6, 3)
    return t.sprite()


def _field():
    t = Torso("field_vest")
    t.pocket(LEFT, 44, 7, 6)
    t.pocket(RIGHT, 44, 7, 6)
    t.paste(23, 46, ["W", "W"])  # lápiz en el bolsillo
    t.pocket(LEFT, 51, 7, 4, flap="a")
    t.pocket(RIGHT, 51, 7, 4, flap="a")
    t.zipper(40, 55)
    return t.sprite()


def _jacket():
    t = Torso("jacket")
    t.zipper(40, 55)
    t.pocket(LEFT, 50, 6, 4)
    t.pocket(RIGHT + 2, 50, 6, 4)
    return t.sprite()


def _apron():
    t = Torso("apron")
    t.fill(24, 42, 16, 1, "k")  # cinta del cuello
    t.pocket(26, 48, 12, 6, edge="a", flap="a")
    t.paste(30, 44, ["WW", "WW"])  # bolsillo con herramienta
    return t.sprite()


def _lab():
    t = Torso("labcoat")
    t.line(24, 41, 31, 48, "k")  # solapas
    t.line(39, 41, 32, 48, "k")
    t.pocket(LEFT, 50, 7, 5, edge="o", flap="o")
    t.pocket(RIGHT, 50, 7, 5, edge="o", flap="o")
    t.paste(22, 47, ["R", "R", "R"])  # lapicera roja
    t.buttons(46, 54, step=3)
    return t.sprite()


def _shirt():
    t = Torso("shirt_tie")
    t.buttons(42, 54, step=3)
    t.pocket(LEFT, 45, 6, 5, edge="o", flap="o")
    return t.sprite()


def _flight():
    t = Torso("flight_jacket")
    t.paste(22, 44, ["CCCCCC", "CWWWWC", "CWCCWC", "CWWWWC", "CCCCCC"])  # parche de piloto
    t.zipper(40, 55)
    t.fill(16, 52, 32, 3, "o")  # puño elástico
    return t.sprite()


def _sweater():
    t = Torso("sweater")
    for y in range(44, 54):  # trenzas de punto
        for x in (22, 26, 30, 34, 38, 42):
            t.put(x, y, "o" if y % 4 < 2 else "a")
    return t.sprite()


def _surveyor():
    t = Torso("surveyor_jacket")
    t.stripe(48)
    t.stripe(52)
    t.zipper(40, 55)
    t.pocket(LEFT, 42, 7, 5)
    t.paste(22, 43, ["WWW"])
    return t.sprite()


def _blazer():
    t = Torso("blazer")
    t.line(22, 41, 31, 51, "o")  # solapas
    t.line(23, 41, 31, 50, "o")
    t.line(41, 41, 32, 51, "o")
    t.line(40, 41, 32, 50, "o")
    t.paste(38, 46, ["WWW", "WRW"])  # pañuelo de bolsillo
    t.buttons(52, 54, step=2, ch="k")
    return t.sprite()


def _overalls():
    t = Torso("overalls")
    t.pocket(26, 44, 12, 7, edge="o", flap="o")
    t.fill(22, 42, 3, 3, "Y")  # botones de los tirantes
    t.fill(39, 42, 3, 3, "Y")
    t.paste(29, 46, ["kkkk", "kYYk"])
    return t.sprite()


def _bim_hoodie():
    t = Torso("bim_hoodie")
    t.paste(27, 44, ["W", "W", "W", "W", "W"])
    t.paste(36, 44, ["W", "W", "W", "W", "W"])
    t.paste(28, 46, [".KKKK.", "KCWWCK", "KCCCCK", ".KKKK."])  # logo de cubo BIM
    t.fill(24, 51, 16, 3, "o")
    return t.sprite()


def _hse():
    t = Torso("hse_vest")
    t.stripe(44)
    t.stripe(50)
    t.zipper(40, 55)
    t.pocket(LEFT, 46, 6, 3)
    t.paste(RIGHT, 45, ["GGGG", "GWWG", "GGGG"])  # cruz de seguridad
    return t.sprite()


def _polo():
    t = Torso("polo")
    t.buttons(41, 47, step=3)
    t.paste(RIGHT + 2, 44, ["AAA", "AWA"])  # logo corporativo
    return t.sprite()


def _cardigan():
    t = Torso("cardigan")
    t.buttons(42, 54, step=3, ch="Y")
    t.pocket(LEFT, 48, 6, 5, edge="o", flap="o")
    t.pocket(RIGHT + 2, 48, 6, 5, edge="o", flap="o")
    return t.sprite()


HD["outfit"].update(
    {
        "tshirt": _tshirt(),
        "hoodie": _hoodie(),
        "hivis_vest": _hivis(),
        "field_vest": _field(),
        "jacket": _jacket(),
        "apron": _apron(),
        "labcoat": _lab(),
        "shirt_tie": _shirt(),
        "flight_jacket": _flight(),
        "sweater": _sweater(),
        "surveyor_jacket": _surveyor(),
        "blazer": _blazer(),
        "overalls": _overalls(),
        "bim_hoodie": _bim_hoodie(),
        "hse_vest": _hse(),
        "polo": _polo(),
        "cardigan": _cardigan(),
    }
)
