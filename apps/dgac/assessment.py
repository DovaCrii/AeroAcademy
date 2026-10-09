"""La prueba de conocimientos RPAS: sorteo, corrección y vigencia.

La corrección es del lado del servidor: lo que sale de `draw` no lleva la respuesta correcta, y el intento guarda su
propia copia de lo preguntado (ver `KnowledgeAttempt`). Las reglas (25 preguntas, 80 %, 12 meses) son del dueño y
viven como constantes con nombre en `constants.py`.
"""

import calendar
import random
import re
from collections import OrderedDict

from . import constants, data

PASS_PERCENT = constants.PASS_PERCENT
QUESTIONS_PER_ATTEMPT = constants.QUESTIONS_PER_ATTEMPT
VALID_MONTHS = constants.VALID_MONTHS
NO_TOPIC = "General"

# Enumeración romana «I. II. III.»: se parte solo al mostrar, nunca en el dato ni en la copia del intento.
_ROMAN_SEQUENCE = ("I.", "II.", "III.", "IV.", "V.", "VI.", "VII.", "VIII.")
_ENUMERATOR = re.compile(r"(?<=\s)(?:I{1,3}|IV|VI{0,3})\.(?=\s)")


def enumerated_lines(text):
    """El enunciado partido en renglones cuando enumera `I.`/`II.`/`III.`; si no, una sola línea.

    Solo dispara con dos marcadores o más y en orden desde `I.`. Unir lo devuelto con un espacio reproduce el texto.
    """
    matches = list(_ENUMERATOR.finditer(text))
    markers = tuple(m.group(0) for m in matches)
    if len(markers) < 2 or markers != _ROMAN_SEQUENCE[: len(markers)]:
        return [text]
    bounds = [0, *[m.start() for m in matches], len(text)]
    parts = (text[a:b].strip() for a, b in zip(bounds, bounds[1:], strict=False))
    return [p for p in parts if p]


def draw(count=QUESTIONS_PER_ATTEMPT, seed=None):
    """`count` preguntas al azar, SIN la respuesta correcta (esa se resuelve al corregir, contra el banco).

    El sorteo real usa `SystemRandom`: dos personas rindiendo a la vez no reciben el mismo juego. La semilla existe
    solo para las pruebas.
    """
    bank = data.load_bank()
    chooser = random.Random(seed) if seed is not None else random.SystemRandom()  # noqa: S311
    picked = chooser.sample(bank, min(count, len(bank)))
    return [
        {"id": q["id"], "text": q["text"], "topic": q["topic"], "options": q["options"]}
        for q in picked
    ]


def grade(question_ids, given):
    """Corrige un intento. Devuelve `(filas, correctas, porcentaje, aprobado)`.

    `filas` es la copia que guarda el intento. Una pregunta sin responder cuenta como incorrecta y se dice
    (`given: ""`); el total es lo que se preguntó.
    """
    by_id = {q["id"]: q for q in data.load_bank()}
    rows = []
    for qid in question_ids:
        q = by_id.get(qid)
        answered = str(given.get(qid, "") or "")
        if q is None:  # ya no está en el banco: se conserva la marca y no se cuenta como buena
            rows.append(
                {"id": qid, "text": "Esta pregunta ya no está en el banco.", "topic": NO_TOPIC,
                 "options": [], "given": answered, "answer": "", "correct": False}
            )  # fmt: skip
            continue
        rows.append(
            {
                "id": q["id"],
                "text": q["text"],
                "topic": q["topic"] or NO_TOPIC,
                "options": q["options"],
                "given": answered,
                "answer": q["answer"],
                "correct": answered == q["answer"],
            }
        )
    correct = sum(1 for r in rows if r["correct"])
    percent = round(correct * 100 / (len(rows) or 1), 1)
    return rows, correct, percent, percent >= PASS_PERCENT


def option_text(row, key):
    for option in row["options"]:
        if option["key"] == key:
            return option["text"]
    return ""


def reinforce(rows):
    """Temas a reforzar: los que más se fallaron, con (fallos, total) por tema. Solo temas con algún fallo."""
    stats = OrderedDict()
    for r in rows:
        topic = r.get("topic") or NO_TOPIC
        missed, total = stats.get(topic, (0, 0))
        stats[topic] = (missed + (0 if r["correct"] else 1), total + 1)
    ranked = [
        {"topic": t, "missed": m, "total": n, "pct": round(100 * m / n)}
        for t, (m, n) in stats.items()
        if m
    ]
    return sorted(ranked, key=lambda x: (-x["missed"], x["topic"]))


def valid_until(taken_on):
    """Fecha en que el resultado deja de estar vigente: `VALID_MONTHS` después (29-feb cae al 28)."""
    months = taken_on.month - 1 + VALID_MONTHS
    year = taken_on.year + months // 12
    month = months % 12 + 1
    day = min(taken_on.day, calendar.monthrange(year, month)[1])
    return taken_on.replace(year=year, month=month, day=day)
