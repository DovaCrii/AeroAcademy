"""Imprime el cuerpo base con regla de coordenadas, para dibujar piezas encima.

Uso:  python tools/show_base.py            # cuerpo base
      python tools/show_base.py hair=long  # con otras piezas ya compuestas (solo para ver el contexto)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.gamification.avatar import engine  # noqa: E402
from apps.gamification.avatar.art import GRID  # noqa: E402


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    cfg = dict(arg.split("=", 1) for arg in argv if "=" in arg)
    grid = engine.compose(engine.clean_config(cfg))
    print("     " + "".join(str(i // 10) for i in range(GRID)))
    print("     " + "".join(str(i % 10) for i in range(GRID)))
    for y, row in enumerate(grid):
        print(f"{y:>3}  " + "".join(row))


if __name__ == "__main__":
    main(sys.argv[1:])
