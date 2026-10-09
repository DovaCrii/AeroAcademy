"""Diploma interno de la Academia: solo para nuestras rutas, nunca para cursos de fabricantes.

Reglas
- Nuestra = la plataforma de la ruta está en `settings.INTERNAL_PLATFORMS` (por defecto `interna`, la misma de la ruta
  DGAC). Autodesk, Bentley, etc. entregan su propio certificado y se registran como credencial.
- Se gana al completar la ruta al 100 % (misiones sin retirar marcadas y preguntas acertadas al menos una vez). La ruta
  DGAC tiene su propia regla: aprobar la prueba de conocimientos (`apps.dgac`), que ya emite la credencial.
- Al ganarlo se emite, una sola vez, una credencial interna verificada por el sistema (sin archivo). El XP y las
  insignias salen de `game.refresh`, como con cualquier credencial. Quitar una misión después no la borra ni la duplica.
- Nada de lo que muestra el diploma sale de un correo: usa `person.name`.
"""

import hashlib
import re
from datetime import date

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe

from apps.credentials import services as credential_services
from apps.credentials.models import Credential
from apps.gamification import game
from apps.gamification.models import XPEvent
from apps.notifications import services as notifications
from apps.paths.models import LearningPath, Level

ISSUER = "Academia LEV Digital 101"
DGAC_ROUTE = (
    "dgac-rpas"  # misma constante que apps.dgac (sin importar la app: dgac depende de esta)
)
DGAC_CREDENTIAL_ID = "DGAC-RPAS-INTERNO"
SHEET = "D-101"


# --- qué rutas son nuestras ---------------------------------------------------------------------------------------


def is_internal(path) -> bool:
    """La ruta es de la Academia (plataforma interna). Datos, no código: ver `INTERNAL_PLATFORMS`."""
    platform = getattr(path, "platform", None)
    return bool(platform and platform.slug in set(getattr(settings, "INTERNAL_PLATFORMS", ())))


def is_test_route(path) -> bool:
    """Rutas cuyo diploma lo gana una prueba y no el 100 % de misiones (hoy solo DGAC)."""
    return path.slug == DGAC_ROUTE


def has_diploma(path) -> bool:
    """Esta ruta puede tener diploma: es nuestra, está publicada y no es de cursos externos."""
    return (
        path is not None
        and path.is_published
        and path.kind == LearningPath.Kind.STRUCTURED
        and is_internal(path)
    )


def credential_id(path) -> str:
    return DGAC_CREDENTIAL_ID if is_test_route(path) else f"DIPLOMA-{path.slug}"


def url_for(path, person=None, *, viewer=None) -> str:
    base = reverse("diplomas:detail", args=[path.slug])
    if person is not None and viewer is not None and person.pk != viewer.pk:
        return f"{base}?persona={person.pk}"
    return base


def diploma_url(viewer, cred):
    """«Ver diploma» en el detalle de una credencial emitida por el sistema para una ruta nuestra; si no, None."""
    path = cred.path
    if not (cred.kind == Credential.Kind.INTERNAL and not cred.file and has_diploma(path)):
        return None
    if cred.credential_id != credential_id(path) or not can_view(viewer, cred.owner):
        return None
    return url_for(path, cred.owner, viewer=viewer)


# --- permisos -----------------------------------------------------------------------------------------------------


def can_view(viewer, owner) -> bool:
    return viewer.pk == owner.pk or viewer.is_lead


# --- ¿lo ganó? ----------------------------------------------------------------------------------------------------


def credential_for(person, path):
    return Credential.objects.filter(
        owner=person, kind=Credential.Kind.INTERNAL, credential_id=credential_id(path)
    ).first()


def route_complete(person, path) -> bool:
    """Todas las misiones sin retirar marcadas y todas las preguntas sin retirar acertadas."""
    state = game._structured_state(person, path)
    return bool(state["levels"]) and state["complete_levels"] == state["levels"]


def earned(person, path) -> bool:
    """Una vez emitido, el diploma no se pierde por desmarcar una misión; la ruta DGAC solo existe con credencial."""
    if not has_diploma(path):
        return False
    if credential_for(person, path) is not None:
        return True
    return not is_test_route(path) and route_complete(person, path)


# --- emisión (idempotente) ------------------------------------------------------------------------------------------


def _notify(person, path, cred):
    notifications.notify(
        person,
        "diploma",
        f"Tu diploma de «{path.title if path else cred.display_title}» está listo",
        "Lámina D-101, revisó Nala. Puedes imprimirlo o guardarlo como PDF.",
        url=url_for(path) if path else "/certificados/",
        key=f"diploma:{cred.credential_id}",
    )


@transaction.atomic
def ensure_issued(person, path):
    """Emite la credencial del diploma si la persona lo ganó y aún no la tiene. Devuelve la credencial o None."""
    if not has_diploma(path):
        return None
    cred = credential_for(person, path)
    if cred is not None:
        return cred
    if is_test_route(path) or not route_complete(person, path):
        return None  # DGAC la emite su prueba; el resto necesita el 100 %
    cred = credential_services.issue_system_credential(
        person,
        credential_id(path),
        {
            "title": f"Diploma · {path.title}",
            "issuer": ISSUER,
            "platform": path.platform,
            "review_comment": "Verificada por el sistema: ruta interna completada al 100 %.",
            "issued_on": timezone.localdate(),
            "path": path,
            "visibility": Credential.Visibility.TEAM,
        },
    )
    _notify(person, path, cred)
    return cred


def on_progress(person, path) -> None:
    """Gancho tras marcar una misión o responder una pregunta (apps.progress.services)."""
    if has_diploma(path) and not is_test_route(path):
        ensure_issued(person, path)


# --- datos para dibujar el diploma ----------------------------------------------------------------------------------

_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def _hours(levels) -> str:
    """Suma las horas estimadas de los niveles («2 h», «15 a 25 h»): un número, o «lo–hi» si hay rangos."""
    lo = hi = 0.0
    for level in levels:
        nums = [float(n.replace(",", ".")) for n in _NUMBER.findall(level.estimated_hours or "")]
        if nums:
            lo += min(nums)
            hi += max(nums)
    if not hi:
        return ""

    def fmt(x):
        return f"{x:g}".replace(".", ",")

    return f"{fmt(lo)} h" if lo == hi else f"{fmt(lo)}–{fmt(hi)} h"


def xp_earned(person, path, cred=None) -> int:
    """XP que dejó la ruta: misiones, capítulos, preguntas, la campaña y la credencial del diploma."""
    from django.db.models import Q, Sum

    from apps.paths.models import Milestone, QuizQuestion

    q = Q(source=f"path:{path.slug}")
    q |= Q(
        source__in=[
            f"milestone:{pk}"
            for pk in Milestone.objects.filter(path=path).values_list("pk", flat=True)
        ]
    )
    q |= Q(
        source__in=[
            f"quiz:{pk}"
            for pk in QuizQuestion.objects.filter(path=path).values_list("pk", flat=True)
        ]
    )
    q |= Q(
        source__in=[
            f"chapter:{pk}" for pk in Level.objects.filter(path=path).values_list("pk", flat=True)
        ]
    )
    if cred is not None:
        q |= Q(source=f"credential:{cred.pk}")
    return XPEvent.objects.filter(person=person).filter(q).aggregate(t=Sum("points"))["t"] or 0


def verification_code(cred, person, when: date) -> str:
    """Código mono del diploma: hash de la credencial, la persona y la fecha. No hay URL de verificación externa."""
    raw = f"{cred.pk if cred else 0}|{person.pk}|{when.isoformat()}"
    digest = hashlib.sha256(raw.encode()).hexdigest().upper()
    return "D101-" + "-".join(digest[i : i + 4] for i in (0, 4, 8, 12))


def _coordinates(code: str) -> dict:
    """Coordenadas UTM de adorno, siempre las mismas para el mismo código (guiño a la lámina topográfica)."""
    n = int(code.replace("D101-", "").replace("-", ""), 16)
    east = 340_000 + n % 20_000
    north = 6_290_000 + (n // 20_000) % 20_000

    def spaced(v):
        return f"{v:,}".replace(",", " ")

    return {"east": spaced(east), "north": spaced(north), "east_raw": east, "north_raw": north}


def frame_svg(coords) -> str:
    """Marco de la lámina (viewBox 297 × 210 mm): doble borde, referencias de zona (1-8, A-F) arriba y a la izquierda,
    y coordenadas E/N en las marcas de abajo y de la derecha, como una hoja de plano. Solo números: es seguro."""
    left, right, top, bottom = 11, 286, 11, 199
    cols, rows = 8, 6
    cw, rh = (right - left) / cols, (bottom - top) / rows
    parts = [
        '<rect class="box b1" x="3" y="3" width="291" height="204"/>',
        f'<rect class="box b2" x="{left}" y="{top}" width="{right - left}" height="{bottom - top}"/>',
    ]
    d = []
    for i in range(cols + 1):  # divisiones de zona (arriba) y marcas menores
        x = left + i * cw
        d.append(f"M{x:.2f} {top}V3")
    for j in range(rows + 1):  # divisiones de zona (izquierda)
        y = top + j * rh
        d.append(f"M{left} {y:.2f}H3")
    for x in range(left, right + 1, 5):  # marcas menores abajo
        d.append(f"M{x} {bottom}v{4 if (x - left) % 25 == 0 else 1.6}")
    for y in range(top, bottom + 1, 5):  # marcas menores a la derecha
        d.append(f"M{right} {y}h{4 if (y - top) % 25 == 0 else 1.6}")
    parts.append(f'<path class="t" d="{"".join(d)}"/>')
    for i in range(cols):
        parts.append(
            f'<text x="{left + (i + 0.5) * cw:.2f}" y="8.2" text-anchor="middle">{i + 1}</text>'
        )
    for j in range(rows):
        parts.append(
            f'<text x="7" y="{top + (j + 0.5) * rh + 0.8:.2f}" text-anchor="middle">{"ABCDEF"[j]}</text>'
        )

    def spaced(v):
        return f"{v:,}".replace(",", "\u202f")

    for x in range(left, right - 20, 50):  # E crece hacia la derecha: 1 mm de hoja = 1 m
        parts.append(
            f'<text x="{x + 1}" y="205.2">E {spaced(coords["east_raw"] + x - left)}</text>'
        )
    for y in range(bottom, top + 30, -50):
        parts.append(
            f'<text transform="translate(291.4 {y - 1}) rotate(-90)">N {spaced(coords["north_raw"] + bottom - y)}</text>'
        )
    return mark_safe("".join(parts))  # noqa: S308


def build_context(person, path, cred, *, issued_on=None, title="", extra_facts=(), body=""):
    """Todo lo que dibuja `diplomas/diploma.html`. Sirve para el diploma de ruta y para el de la prueba DGAC."""
    when = issued_on or (cred.issued_on if cred and cred.issued_on else timezone.localdate())
    levels = list(Level.objects.filter(path=path).order_by("order")) if path else []
    code = verification_code(cred, person, when)
    coords = _coordinates(code)
    facts = [("Fecha", when.strftime("%d-%m-%Y"))]
    hours = _hours(levels)
    facts.append(("Horas", hours or "—"))
    if path is not None and not is_test_route(path):
        state = game._structured_state(person, path)
        facts.append(("Niveles", f"{len(state['complete_levels'])} de {len(state['levels'])}"))
    facts.extend(extra_facts)
    facts.append(("XP ganada", f"{xp_earned(person, path, cred) if path else 0}"))
    reviewer = getattr(cred, "reviewed_by", None) if cred else None
    return {
        "person": person,
        "name": person.name,
        "course": title or (path.title if path else ""),
        "route": path,
        "body": body,
        "facts": facts,
        "when": when,
        "code": code,
        "coords": coords,
        "frame": frame_svg(coords),
        "approver": reviewer.name if reviewer else "Sistema",
        "sheet": SHEET,
        "issuer": ISSUER,
    }


def diploma_context(person, path):
    """Contexto del diploma de una ruta del 100 %, o None si aún no lo ganó."""
    cred = ensure_issued(person, path) or credential_for(person, path)
    if cred is None:
        return None
    return build_context(person, path, cred, extra_facts=_expiry_fact(cred))


def _expiry_fact(cred):
    if cred.expires_on:
        return [("Vigente hasta", cred.expires_on.strftime("%d-%m-%Y"))]
    return []


def route_link(person, path):
    """Enlace al diploma para la portada de la ruta, o None si aún no lo ganó (o la ruta no emite diploma)."""
    return url_for(path) if earned(person, path) else None
