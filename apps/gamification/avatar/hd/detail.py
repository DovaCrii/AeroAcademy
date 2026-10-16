"""Pase de acabado de la figura HD: luz y sombra en el borde, y esquinas redondeadas.

Todo se calcula de la propia figura (sin dibujar a mano): el contorno doble que sale de escalar ×2 el contorno de 1
celda se parte en una mitad exterior (queda `K`, el contorno) y una interior que pasa a la luz o la sombra del relleno
vecino. Las líneas finas (boca, ojos, cejas) y las piezas HD de 1 celda no se tocan.
"""

# Relleno → tono de sombra / de luz. Las claves «1..4» solo las pone este pase (ver `palette_hd`).
SHADE = {"S": "s", "O": "o", "H": "j", "P": "p", "T": "t", "B": "b"}
LIGHT = {"S": "1", "O": "2", "H": "h", "P": "4", "T": "3"}


def detail_pass(grid):
    """Modifica `grid` (matriz cuadrada de claves) y la devuelve."""
    size = len(grid)
    src = [row[:] for row in grid]

    def at(x, y):
        return src[y][x] if 0 <= x < size and 0 <= y < size else "."

    for y in range(size):
        for x in range(size):
            if src[y][x] != "K":
                continue
            if "." in (at(x + 1, y), at(x - 1, y), at(x, y + 1), at(x, y - 1)):
                # esquina exterior de un bloque 2×2: se recorta (redondea el escalón)
                if (
                    at(x - 1, y) == "."
                    and at(x, y - 1) == "."
                    and at(x + 1, y) == "K"
                    and at(x, y + 1) == "K"
                    and at(x + 1, y + 1) not in ".K"
                ):
                    grid[y][x] = "."
                continue
            # mitad interior del contorno doble: arriba/izquierda → luz; abajo/derecha → sombra
            for (dx, dy), table in (
                ((0, -1), LIGHT),
                ((-1, 0), LIGHT),
                ((0, 1), SHADE),
                ((1, 0), SHADE),
            ):
                if at(x + dx, y + dy) == "K" and at(x + 2 * dx, y + 2 * dy) == ".":
                    fill = at(x - dx, y - dy)
                    if fill in table:
                        grid[y][x] = table[fill]
                    elif fill in SHADE:
                        grid[y][x] = SHADE[fill]
                    break
    return grid
