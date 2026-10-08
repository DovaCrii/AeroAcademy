"""Audita que las piezas de avatar encajen entre sí (lentes con ojos, gorros con peinados, barba con boca…).

Uso (desde la raíz del repositorio):
    python tools/audit_avatar.py              # informe de problemas
Para ver las combinaciones: python tools/preview_avatar.py salida.png --matrix glasses eyes
Sale con código 1 si hay problemas.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.gamification.avatar import audit  # noqa: E402


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    problems = audit.run_all()
    for problem in problems:
        print("✗", problem)
    print(f"{'✔ todo encaja' if not problems else f'{len(problems)} problema(s)'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
