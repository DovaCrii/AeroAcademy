#!/usr/bin/env python3
"""Comprobación previa a producción de AeroAcademy: si termina en verde, el código está listo para subir a la VM.

    python tools/preflight.py            # todo, incluida la suite de pruebas
    python tools/preflight.py --rapido   # sin pytest (para repetir tras un cambio pequeño)

No toca la VM ni la red: todo corre aquí, con una base y carpetas temporales y la configuración de producción real
(`config.settings.prod`). Requiere `uv`.
"""

import argparse
import os
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ["uv", "run", "python"]
results = []


def step(name, cmd, env=None, expect_ok=True, show=False):
    merged = {**os.environ, **(env or {})}
    done = subprocess.run(
        cmd, cwd=ROOT, env=merged, capture_output=True, text=True, encoding="utf-8"
    )
    ok = (done.returncode == 0) == expect_ok
    results.append((name, ok))
    print(("✔ " if ok else "✘ ") + name)
    if (not ok or show) and (done.stdout or done.stderr):
        print(
            "    "
            + "\n    ".join(((done.stdout or "") + (done.stderr or "")).strip().splitlines()[-25:])
        )
    return done


def secrets_check():
    """Ninguna clave en el repositorio y ningún archivo de configuración con secretos versionado."""
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True
    ).stdout.splitlines()
    bad_files = [
        f for f in tracked if f in (".env", "deploy/centro.env") or f.endswith((".sqlite3", ".db"))
    ]
    leaks = subprocess.run(
        ["git", "grep", "-nE", r"nvapi-[A-Za-z0-9_-]{8,}", "--", ".", ":!tests/*"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    ok = not bad_files and not leaks
    results.append(("Sin secretos ni bases de datos versionados", ok))
    print(("✔ " if ok else "✘ ") + "Sin secretos ni bases de datos versionados")
    for line in bad_files + leaks.splitlines():
        print("    " + line)


def line_endings_check():
    """Los scripts y unidades de systemd deben tener finales de línea LF (en Linux, CRLF los rompe)."""
    bad = [
        str(p.relative_to(ROOT))
        for p in (ROOT / "deploy").iterdir()
        if p.is_file() and b"\r\n" in p.read_bytes()
    ]
    results.append(("Scripts de deploy con finales de línea LF", not bad))
    print(("✔ " if not bad else "✘ ") + "Scripts de deploy con finales de línea LF")
    for name in bad:
        print("    CRLF en " + name)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--rapido", action="store_true", help="no corre pytest")
    args = parser.parse_args(argv)

    print("== Código ==")
    step("ruff (lint)", ["uv", "run", "ruff", "check", "."])
    step("ruff (formato)", ["uv", "run", "ruff", "format", "--check", "."])
    step("manage.py check", [*PY, "manage.py", "check"])
    step("Migraciones al día", [*PY, "manage.py", "makemigrations", "--check", "--dry-run"])

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        env = {
            "DJANGO_SETTINGS_MODULE": "config.settings.prod",
            "SECRET_KEY": secrets.token_urlsafe(64),
            "ALLOWED_HOSTS": "preflight.tailnet.ts.net",
            "BOOTSTRAP_ADMINS": "admin@preflight.cl",
            "DATABASE_PATH": str(tmp / "db.sqlite3"),
            "MEDIA_ROOT": str(tmp / "media"),
            "STATIC_ROOT": str(tmp / "static"),
            "NIM_API_KEY": "",
        }
        print("\n== Producción (config.settings.prod, base y carpetas temporales) ==")
        step(
            "Migraciones y semillas sobre una base nueva", [*PY, "manage.py", "migrate", "-v0"], env
        )
        step("seed_catalog --dry-run", [*PY, "manage.py", "seed_catalog", "--dry-run"], env)
        step(
            "check --deploy sin avisos graves",
            [*PY, "manage.py", "check", "--deploy", "--fail-level", "ERROR"],
            env,
        )
        step("collectstatic", [*PY, "manage.py", "collectstatic", "--noinput", "-v0"], env)
        step(
            "Humo: recorrido de las páginas con la configuración de producción",
            [*PY, "tools/_smoke_prod.py"],
            env,
            show=True,
        )
        step(
            "Sin DEBUG ni identidad simulada en producción",
            [
                *PY,
                "-c",
                "import django,os;django.setup();from django.conf import settings as s;assert not s.DEBUG and not s.DEV_REMOTE_USER",
            ],
            env,
        )
        step(
            "Falta SECRET_KEY: producción se niega a arrancar",
            [*PY, "manage.py", "check"],
            {**env, "SECRET_KEY": ""},
            expect_ok=False,
        )
        step(
            "Falta ALLOWED_HOSTS: producción se niega a arrancar",
            [*PY, "manage.py", "check"],
            {**env, "ALLOWED_HOSTS": ""},
            expect_ok=False,
        )

    print("\n== Repositorio y despliegue ==")
    secrets_check()
    line_endings_check()
    for name in ("install.sh", "backup.sh", "centro.service", "centro.env.plantilla"):
        ok = (ROOT / "deploy" / name).is_file()
        results.append((f"deploy/{name} existe", ok))
        print(("✔ " if ok else "✘ ") + f"deploy/{name} existe")

    if not args.rapido:
        print("\n== Pruebas ==")
        step("pytest", ["uv", "run", "pytest", "-q"])

    failed = [name for name, ok in results if not ok]
    print()
    if failed:
        print(f"✘ {len(failed)} comprobación(es) fallaron:")
        for name in failed:
            print("   · " + name)
        return 1
    print("✔ Todo en verde: listo para subir a la VM (ver docs/PRODUCCION.md).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
