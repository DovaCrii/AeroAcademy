"""Prueba RPAS, diploma y credencial interna. La lógica vive aquí; las vistas solo la llaman.

Al aprobar se emite una credencial interna (tipo `internal`) verificada por el sistema y ligada a la ruta, y se
llama a `game.refresh`: el XP y las insignias salen del código normal del juego, no de uno paralelo.
"""

import secrets
from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Person, PersonStatus
from apps.catalog.models import Platform
from apps.credentials import services as credential_services
from apps.credentials.models import Credential
from apps.gamification import game
from apps.paths.models import LearningPath

from . import assessment, constants, data
from .models import KnowledgeAttempt

SESSION_KEY = "dgac_draws"
MAX_OPEN_DRAWS = 3  # pruebas abiertas a la vez (pestañas); las más viejas se descartan


# --- sorteo (vive en la sesión, no en el formulario) ---------------------------------------------------------------


def open_draw(session):
    """Sortea las preguntas y las deja en la sesión bajo un token. Devuelve `(token, preguntas)`."""
    questions = assessment.draw()
    token = secrets.token_urlsafe(9)
    draws = dict(session.get(SESSION_KEY) or {})
    draws[token] = [q["id"] for q in questions]
    for old in list(draws)[:-MAX_OPEN_DRAWS]:
        draws.pop(old)
    session[SESSION_KEY] = draws
    return token, questions


def take_draw(session, token):
    """Ids sorteados para ese token (y lo consume), o None si expiró o no existe."""
    draws = dict(session.get(SESSION_KEY) or {})
    ids = draws.pop(token, None)
    session[SESSION_KEY] = draws
    return ids


# --- intentos ------------------------------------------------------------------------------------------------------


def submit_attempt(person, question_ids, given, *, today=None):
    """Corrige, guarda el intento con su copia y, si aprueba, emite la credencial interna."""
    rows, correct, percent, passed = assessment.grade(question_ids, given)
    today = today or timezone.localdate()
    with transaction.atomic():
        attempt = KnowledgeAttempt.objects.create(
            person=person,
            taken_at=timezone.now(),
            question_count=len(rows),
            correct_count=correct,
            score_percent=percent,
            pass_percent=assessment.PASS_PERCENT,
            passed=passed,
            expires_on=assessment.valid_until(today) if passed else None,
            answers=rows,
        )
        if passed:
            attempt.credential = issue_credential(person, attempt, today)
            attempt.save(update_fields=["credential", "updated_at"])
    return attempt  # XP e insignias: `issue_system_credential` llama a `game.refresh` (idempotente)


def issue_credential(person, attempt, today: date):
    """Credencial interna verificada por el sistema, ligada a la ruta. Aprobar de nuevo renueva la misma."""
    path = LearningPath.objects.filter(slug=constants.ROUTE_SLUG).first()
    platform = Platform.objects.filter(slug="interna").first()
    title = diploma_title()
    return credential_services.issue_system_credential(
        person,
        constants.CREDENTIAL_ID,
        {
            "title": title,
            "issuer": constants.DEFAULT_ISSUER,
            "platform": platform,
            "review_comment": "Verificada por el sistema: prueba interna de conocimientos RPAS aprobada.",
            "issued_on": today,
            "expires_on": attempt.expires_on,
            "path": path,
            "visibility": Credential.Visibility.TEAM,
        },
    )


def diploma_title():
    overview = data.load_overview() or {}
    return (overview.get("diploma") or {}).get("title") or constants.DEFAULT_DIPLOMA_TITLE


def diploma_text():
    overview = data.load_overview() or {}
    return (overview.get("diploma") or {}).get("text", "")


# --- permisos y consultas --------------------------------------------------------------------------------------


def can_view(person, attempt) -> bool:
    """Cada quien ve lo suyo; quien lidera ve el de todas las personas."""
    return attempt.person_id == person.pk or person.is_lead


def attempts_of(person):
    return KnowledgeAttempt.objects.filter(person=person)


def latest_valid(person):
    """Último intento aprobado y vigente de la persona, o None."""
    return (
        attempts_of(person)
        .filter(passed=True, expires_on__gte=timezone.localdate())
        .order_by("-taken_at")
        .first()
    )


def best_attempt(person):
    return attempts_of(person).order_by("-score_percent", "-taken_at").first()


def team_status():
    """Para quien lidera: el último intento de cada persona aprobada. Sin consultas por fila."""
    latest = {}
    for attempt in KnowledgeAttempt.objects.select_related("person").order_by("taken_at"):
        latest[attempt.person_id] = attempt
    people = Person.objects.filter(status=PersonStatus.APPROVED, is_active=True)
    rows = []
    for person in people:
        attempt = latest.get(person.pk)
        rows.append({"person": person, "attempt": attempt})
    rows.sort(key=lambda r: (r["attempt"] is None, r["person"].name.lower()))
    return rows


def progress_summary(person):
    """Resumen para la portada: avance en la ruta, prueba y diploma."""
    path = LearningPath.objects.filter(slug=constants.ROUTE_SLUG, is_published=True).first()
    valid = latest_valid(person)
    best = best_attempt(person)
    return {
        "path": path,
        "path_pct": game.path_percent(person, path) if path else None,
        "valid": valid,
        "best": best,
        "attempts": attempts_of(person).count(),
    }
