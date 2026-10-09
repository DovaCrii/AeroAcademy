"""Preguntas frecuentes de la ayuda, por tema, y búsqueda local (sin JS, sin el modelo, sin base de datos).

Cada tema lleva su garabato (`core/img/doodles/<doodle>.svg`) y un color de acento (`data-t` en el CSS).
Las respuestas son cortas a propósito: lo largo vive en las guías de `apps/assistant/help/*.md`.
"""

import re
import unicodedata

from django.urls import reverse

from .search import HELP_DIR

# (id, título, bajada, garabato, [(pregunta, respuesta, url_name | None, texto del enlace)])
TOPICS = [
    {
        "id": "empezar",
        "title": "Empezar",
        "tagline": "Tu primer día en la academia, sin vueltas.",
        "doodle": "hero-ideas",
        "items": [
            (
                "¿Qué es Levantamiento Digital 101?",
                "La academia del equipo: rutas por empresa de software, certificados con vencimiento, foro y un "
                "juego de XP para no perder el ritmo. AeroAcademy es la plataforma donde vive.",
                "core:home",
                "Ir a la portada",
            ),
            (
                "¿Por dónde empiezo?",
                "Arma tu hoja de personaje, abre una ruta y marca tu primera misión. La portada siempre te "
                "sugiere la próxima. Son cuatro pasos y se tachan solos.",
                "paths:index",
                "Ver las rutas",
            ),
            (
                "¿Dónde encuentro cada cosa?",
                "Arriba están Rutas, Catálogo, Certificados, Foro y Equipo. Lo demás (Documentos, Conocimiento, "
                "Gremio, DGAC y esta Ayuda) está en «Más».",
                None,
                "",
            ),
        ],
    },
    {
        "id": "rutas",
        "title": "Rutas y misiones",
        "tagline": "Campañas con mapa, capítulos y banderita al final.",
        "doodle": "rutas",
        "items": [
            (
                "¿Qué es una ruta?",
                "Una campaña de una empresa de software (Autodesk, Bentley…) con capítulos y misiones. Algunas "
                "se marcan paso a paso y otras se completan con el certificado oficial del curso.",
                "paths:index",
                "Explorar rutas",
            ),
            (
                "¿Cómo marco una misión?",
                "Entra a la ruta, abre el capítulo y marca la misión cuando la termines. Si te equivocas, "
                "la desmarcas y el XP se ajusta solo, sin duplicarse.",
                None,
                "",
            ),
            (
                "¿Dónde busco un curso suelto?",
                "En el Catálogo: un solo buscador para cursos, módulos, tutoriales y exámenes, con filtros por "
                "plataforma, tipo y gratuito.",
                "catalog:resources",
                "Abrir el catálogo",
            ),
        ],
    },
    {
        "id": "certificados",
        "title": "Certificados",
        "tagline": "Tu repositorio de credenciales, con avisos de vencimiento.",
        "doodle": "certificados",
        "items": [
            (
                "¿Cómo subo un certificado?",
                "En Certificados elige «Subir certificado»: PDF, PNG o JPG de hasta 10 MB. Es privado: solo tú y "
                "los responsables pueden abrirlo.",
                "credentials:create",
                "Subir uno ahora",
            ),
            (
                "¿Por qué mi certificado está «en revisión»?",
                "Un responsable lo valida antes de darte el XP y marcar la misión. Si lo editas, vuelve a revisión.",
                "credentials:mine",
                "Mis certificados",
            ),
            (
                "¿Me avisan cuando uno vence?",
                "Sí. La campana te avisa antes del vencimiento y puedes exportar la evidencia para una licitación.",
                "credentials:expirations",
                "Ver vencimientos",
            ),
        ],
    },
    {
        "id": "xp",
        "title": "XP y niveles",
        "tagline": "Puntos, títulos e insignias para celebrar lo avanzado.",
        "doodle": "doodle-sparks",
        "items": [
            (
                "¿Cuánto XP gano?",
                "10 por misión, 25 por capítulo y 150 por campaña completa. Un certificado verificado vale 100, "
                "una habilitación 300 y una certificación oficial 500.",
                None,
                "",
            ),
            (
                "¿Qué es «101 · NV 1» en la cabecera?",
                "Es tu progreso dentro de Levantamiento Digital 101: «NV» es tu nivel y la barra, lo que falta "
                "para el siguiente. Al lado ves tu título, por ejemplo Aprendiz de Cota.",
                "gamification:my_sheet",
                "Mi hoja de personaje",
            ),
            (
                "¿Se pierde el XP?",
                "Solo si un certificado deja de estar verificado: su XP y sus insignias se retiran hasta que se "
                "verifique otra vez.",
                None,
                "",
            ),
        ],
    },
    {
        "id": "foro",
        "title": "Foro y notas",
        "tagline": "Preguntar es de profesionales.",
        "doodle": "foro",
        "items": [
            (
                "¿Cómo hago una consulta?",
                "Abre un hilo en el foro, elige disciplina y cuenta qué probaste. Cuando alguien te ayuda, marcas "
                "su respuesta como aceptada.",
                "community:thread_new",
                "Abrir un hilo",
            ),
            (
                "¿Qué son las notas de una ruta?",
                "Tips y avisos que el equipo deja dentro de cada ruta para quien viene detrás.",
                "community:forum",
                "Ir al foro",
            ),
        ],
    },
    {
        "id": "nala",
        "title": "Nala",
        "tagline": "La golden del gremio: busca, resume y empuja.",
        "doodle": "nala",
        "items": [
            (
                "¿Qué puede responderme Nala?",
                "Lo que el equipo ya dejó en la academia: rutas, glosarios, notas, foro, artículos y esta ayuda, "
                "con enlaces a sus fuentes.",
                "assistant:page",
                "Hablar con Nala",
            ),
            (
                "¿Ve mis certificados?",
                "Nunca. Tampoco tus datos de contacto, y no guarda lo que preguntas. Hay un límite de preguntas por "
                "día. Si está durmiendo, usa el buscador de esta página.",
                None,
                "",
            ),
        ],
    },
    {
        "id": "dgac",
        "title": "DGAC",
        "tagline": "Habilitaciones y trámites de vuelo, ordenados.",
        "doodle": "dgac",
        "items": [
            (
                "¿Qué hay en la sección DGAC?",
                "Un espacio para las habilitaciones y el material de captura con drones (RPA) que pide la "
                "autoridad aeronáutica.",
                "dgac:home",
                "Abrir DGAC",
            ),
        ],
    },
    {
        "id": "cuenta",
        "title": "Cuenta y acceso",
        "tagline": "Quién eres, qué ves y por qué.",
        "doodle": "equipo",
        "items": [
            (
                "Entré y dice «esperando aprobación»",
                "Es normal la primera vez: entras con tu cuenta de Tailscale y un responsable te da acceso. "
                "Cuando te aprueban, la portada se abre sola.",
                None,
                "",
            ),
            (
                "¿Cómo cambio mi perfil o mi avatar?",
                "En tu hoja de personaje: clase, titular, avatar y la vista de juego o profesional.",
                "gamification:edit_sheet",
                "Editar mi perfil",
            ),
            (
                "¿Funciona en el teléfono?",
                "Sí, y se puede instalar como app desde el navegador. El tema claro u oscuro se cambia con el "
                "botón ◐ de la cabecera.",
                None,
                "",
            ),
        ],
    },
]


def _norm(text):
    text = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


_WORDS = re.compile(r"[a-z0-9]{2,}")


def topics():
    """Temas con las URLs ya resueltas (reverse en cada petición)."""
    out = []
    for t in TOPICS:
        items = [
            {"q": q, "a": a, "url": reverse(name) if name else None, "link": link}
            for q, a, name, link in t["items"]
        ]
        out.append({**t, "items": items})
    return out


def guides():
    items = []
    for p in sorted(HELP_DIR.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        lines = text.splitlines()
        items.append(
            {
                "slug": p.stem,
                "title": lines[0].lstrip("# ").strip() if lines else p.stem,
                "body": " ".join(lines[1:]).strip(),
            }
        )
    return items


def search(query, limit=12):
    """Preguntas y guías que contienen todas las palabras (sin tildes ni mayúsculas). Devuelve (faq, guias)."""
    words = _WORDS.findall(_norm(query))
    if not words:
        return [], []

    def score(title, body):
        t, b = _norm(title), _norm(body)
        if not all(w in t or w in b for w in words):
            return 0
        return 1 + sum(2 for w in words if w in t)

    faq_hits = []
    for t in topics():
        for item in t["items"]:
            s = score(item["q"], item["a"] + " " + t["title"])
            if s:
                faq_hits.append((s, {**item, "topic": t["title"], "topic_id": t["id"]}))
    guide_hits = []
    for g in guides():
        s = score(g["title"], g["body"])
        if s:
            guide_hits.append((s, g))
    faq_hits.sort(key=lambda x: -x[0])
    guide_hits.sort(key=lambda x: -x[0])
    return [h for _, h in faq_hits[:limit]], [h for _, h in guide_hits[:limit]]
