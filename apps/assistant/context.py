"""Armado del contexto que viaja al proveedor. Es la **lista blanca** de datos de docs/BOT.md.

Se envía: la pregunta, fragmentos visibles para todo el equipo, títulos de misiones pendientes y el nombre visible.
Nunca: credenciales (archivos, ID, URL de verificación, fechas), correos o logins, documentos restringidos, contenido
borrado u oculto, ni datos de otras personas fuera del foro y las notas visibles.
"""

from apps.core import dashboard
from apps.paths.models import LearningPath, Milestone
from apps.progress.models import MilestoneCheck

from . import search

QUESTION_MAX = 500
SNIPPET = 400
PENDING_LIMIT = 5

SYSTEM_PROMPT = (
    "Eres Teo, el asistente de la Academia LEV Digital 101 de AeroAcademy. Respondes en español, breve y cercano, "
    "como un colega de terreno. Los comandos de software van en inglés tal como aparecen en pantalla. Usa solo el "
    "CONTEXTO entregado para hablar de la academia, sus rutas, notas y foro, y menciona las fuentes por su número "
    "entre corchetes, por ejemplo [1]. Si el contexto no alcanza, dilo y sugiere abrir una consulta en el foro. "
    "Nunca inventes URLs, cursos ni certificaciones. No pidas ni repitas datos personales."
)


def clean_question(text):
    text = " ".join((text or "").split())
    if not text:
        raise ValueError("Escríbeme tu pregunta.")
    return text[:QUESTION_MAX]


def pending_titles(person):
    """Misión sugerida y hasta 5 misiones pendientes de esa ruta (solo títulos)."""
    mission = dashboard.suggested_mission(person)
    if mission is None:
        return []
    titles = [mission["title"]]
    path = mission["path"]
    if path.kind == LearningPath.Kind.STRUCTURED:
        done = set(
            MilestoneCheck.objects.filter(person=person, milestone__path=path).values_list(
                "milestone_id", flat=True
            )
        )
        for m in Milestone.objects.filter(path=path, retired=False):
            text = dashboard._plain(m.text)
            if m.pk not in done and text not in titles:
                titles.append(text)
            if len(titles) > PENDING_LIMIT:
                break
    return [f"{path.title}: {t}" for t in titles[:PENDING_LIMIT]]


def build(person, question, *, extra=None):
    """Devuelve (mensajes, fuentes). `extra` es texto ya visible para el equipo (ej.: un hilo a resumir)."""
    hits = search.search(question)
    blocks, sources = [], []
    for n, hit in enumerate(hits, start=1):
        blocks.append(f"[{n}] {hit['title']} ({hit['kind']})\n{hit['body'][:SNIPPET]}")
        sources.append({"n": n, "title": hit["title"], "url": hit["url"]})
    context = "\n\n".join(blocks) if blocks else "(sin resultados)"
    if extra:
        context = f"{extra}\n\n{context}"
    progress = "\n".join(f"- {t}" for t in pending_titles(person)) or "(sin misiones pendientes)"
    user = (
        f"CONTEXTO:\n{context}\n\n"
        f"MISIONES PENDIENTES DE {person.name}:\n{progress}\n\n"
        f"PREGUNTA:\n{question}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ], sources


def thread_text(thread, posts):
    """Texto de un hilo para resumirlo: solo lo visible (el llamador pasa mensajes no ocultos ni borrados)."""
    parts = [f"HILO: {thread.title}\n{thread.body[:1500]}"]
    for p in posts[:30]:
        parts.append(f"- {p.body[:600]}")
    return "\n".join(parts)
