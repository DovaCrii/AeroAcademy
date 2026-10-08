"""Convenciones del arte de los avatares (docs/AVATARES_PIXEL.md).

Grilla de 32×32. Cada pieza es un dict `{fila_y: "32 caracteres"}`; '.' es transparente.
Para arte simétrico se escribe solo la mitad izquierda (16 caracteres) con `sym()`.
"""

GRID = 32
HALF = GRID // 2

# Claves de color. Las claves de arriba cambian con la configuración de la persona; las de abajo son fijas.
COLOR_KEYS = {
    "K": "contorno",
    "S": "piel",
    "s": "piel (sombra)",
    "E": "ojo oscuro",
    "e": "iris (color de ojos)",
    "W": "blanco",
    "M": "interior de la boca",
    "m": "labios",
    "H": "pelo",
    "h": "pelo (luz)",
    "j": "pelo (sombra)",
    "O": "ropa",
    "o": "ropa (sombra)",
    "A": "ropa (acento)",
    "a": "ropa (acento oscuro)",
    "P": "pantalón",
    "p": "pantalón (sombra)",
    "B": "botas",
    "b": "botas (sombra)",
    "F": "marco de lentes",
    "L": "cristal de lentes",
    "g": "brillo de cristal",
    "T": "gorro / sombrero",
    "t": "gorro (sombra)",
    "U": "gorro (acento)",
    "Y": "amarillo fijo",
    "R": "rojo fijo",
    "C": "cian fijo",
    "N": "marrón fijo",
    "Z": "gris fijo",
}


def sym(left: str) -> str:
    """Espeja la mitad izquierda (16 caracteres) para armar una fila completa de 32."""
    if len(left) != HALF:
        raise ValueError(f"la mitad izquierda debe medir {HALF}, mide {len(left)}: {left!r}")
    return left + left[::-1]


def full(row: str) -> str:
    """Valida una fila completa de 32 caracteres."""
    if len(row) != GRID:
        raise ValueError(f"la fila debe medir {GRID}, mide {len(row)}: {row!r}")
    return row


def mix(left: str, right: str) -> str:
    """Fila con mitad izquierda y derecha distintas (asimetría)."""
    if len(left) != HALF or len(right) != HALF:
        raise ValueError("cada mitad debe medir 16")
    return left + right
