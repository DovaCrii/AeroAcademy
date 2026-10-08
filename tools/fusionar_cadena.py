#!/usr/bin/env python3
"""Fusiona la cadena de PR apilados de AeroAcademy, en orden, con las reglas de docs/FUSIONES.md.

Lo corre **la persona** (el agente no fusiona). Por defecto solo muestra el plan (simulación).

    python tools/fusionar_cadena.py                  # plan y comprobaciones, no cambia nada
    python tools/fusionar_cadena.py --ejecutar       # fusiona de verdad, pidiendo confirmación escrita
    python tools/fusionar_cadena.py --ejecutar --hasta 8   # fusiona hasta el PR #8 inclusive

Reglas que aplica: solo el primer PR apunta a `main`; cada uno se fusiona con *merge commit* (nunca squash ni rebase:
romperían los PR de arriba); antes de fusionar uno, se reapunta a `main` y se espera a que su CI quede en verde; si algo
falla, se detiene. Requiere `gh` autenticado.
"""

import argparse
import json
import subprocess
import sys
import time

BASE = "main"
POLL_SECONDS, POLL_TIMEOUT = 15, 900


def gh(*args, check=True):
    result = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8")
    if check and result.returncode != 0:
        raise SystemExit(f"gh {' '.join(args)} falló:\n{result.stderr.strip()}")
    return result.stdout


def open_prs():
    fields = "number,title,baseRefName,headRefName,mergeable,statusCheckRollup,isDraft"
    return json.loads(gh("pr", "list", "--state", "open", "--limit", "100", "--json", fields))


def build_chain(prs, base=BASE):
    """Ordena los PR de la cadena (base → punta). Lanza ValueError si no es una cadena lineal."""
    by_base = {}
    for pr in prs:
        if pr["baseRefName"] in by_base:
            raise ValueError(
                f"Dos PR apuntan a «{pr['baseRefName']}»: #{by_base[pr['baseRefName']]['number']} y #{pr['number']}."
            )
        by_base[pr["baseRefName"]] = pr
    chain, cursor = [], base
    while cursor in by_base:
        pr = by_base[cursor]
        chain.append(pr)
        cursor = pr["headRefName"]
    loose = [pr["number"] for pr in prs if pr not in chain]
    if loose:
        raise ValueError(f"PR fuera de la cadena: {', '.join('#' + str(n) for n in loose)}.")
    return chain


def ci_state(pr):
    """'ok', 'fallo' o 'pendiente' según los chequeos del PR."""
    checks = pr.get("statusCheckRollup") or []
    if not checks:
        return "pendiente"
    results = [(c.get("conclusion") or c.get("state") or "").upper() for c in checks]
    if any(r in ("FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED") for r in results):
        return "fallo"
    if all(r in ("SUCCESS", "NEUTRAL", "SKIPPED") for r in results):
        return "ok"
    return "pendiente"


def problems(pr):
    """Lo que impide fusionar este PR ahora (lista vacía = listo)."""
    out = []
    if pr.get("isDraft"):
        out.append("es un borrador")
    if pr.get("mergeable") == "CONFLICTING":
        out.append("tiene conflictos")
    state = ci_state(pr)
    if state != "ok":
        out.append(f"CI {state}")
    return out


def show_plan(chain):
    print(f"Cadena de {len(chain)} PR (orden de fusión):\n")
    ready = True
    for pr in chain:
        issues = problems(pr)
        ready &= not issues
        mark = "✔" if not issues else "✘"
        print(
            f"  {mark} #{pr['number']:<3} {pr['title']}  ({pr['baseRefName']} ← {pr['headRefName']})"
        )
        for issue in issues:
            print(f"        · {issue}")
    return ready


def wait_ready(number):
    waited = 0
    while waited <= POLL_TIMEOUT:
        pr = json.loads(
            gh("pr", "view", str(number), "--json", "number,mergeable,statusCheckRollup,isDraft")
        )
        if pr.get("mergeable") == "CONFLICTING":
            raise SystemExit(
                f"#{number} tiene conflictos tras reapuntarlo a {BASE}: resuélvelos y vuelve a correr."
            )
        state = ci_state(pr)
        if state == "ok" and pr.get("mergeable") != "UNKNOWN":
            return
        if state == "fallo":
            raise SystemExit(f"El CI de #{number} falló: revísalo en GitHub.")
        time.sleep(POLL_SECONDS)
        waited += POLL_SECONDS
    raise SystemExit(f"#{number}: el CI no terminó en {POLL_TIMEOUT // 60} minutos.")


def merge_chain(chain, upto):
    for pr in chain:
        number = pr["number"]
        if pr["baseRefName"] != BASE:
            print(f"#{number}: reapuntando a {BASE}…")
            gh("pr", "edit", str(number), "--base", BASE)
            wait_ready(number)
        print(f"#{number}: fusionando (merge commit)…")
        gh("pr", "merge", str(number), "--merge")
        print(f"#{number}: ✔ fusionado")
        if upto and number >= upto:
            break


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--ejecutar", action="store_true", help="fusiona de verdad (sin esto solo muestra el plan)"
    )
    parser.add_argument(
        "--hasta", type=int, default=0, help="fusiona hasta este número de PR, inclusive"
    )
    args = parser.parse_args(argv)

    try:
        chain = build_chain(open_prs())
    except ValueError as exc:
        raise SystemExit(f"La cadena no es lineal: {exc}") from exc
    if not chain:
        raise SystemExit("No hay PR abiertos que apunten a main.")
    selected = [pr for pr in chain if not args.hasta or pr["number"] <= args.hasta]
    ready = show_plan(selected)
    if not args.ejecutar:
        print("\nSimulación: no se cambió nada. Usa --ejecutar para fusionar.")
        return 0
    if not ready:
        raise SystemExit("\nHay PR que no están listos: corrígelos antes de fusionar.")
    phrase = f"FUSIONAR {len(selected)}"
    if input(f"\nEscribe «{phrase}» para fusionar {len(selected)} PR en orden: ").strip() != phrase:
        raise SystemExit("Cancelado.")
    merge_chain(selected, args.hasta)
    print("\nListo. Siguiente paso: docs/PRODUCCION.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
