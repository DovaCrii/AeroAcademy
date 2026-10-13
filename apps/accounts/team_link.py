"""Enlace de inscripción del equipo (D35): un enlace para todos, generado y revocado por el admin.

El enlace firmado lleva el id del registro y un secreto al azar; en la base solo queda el hash del secreto. Vence
(7/14/30 días), se revoca y generar uno nuevo revoca el anterior. Inscribirse nunca da más que un acceso `member`:
las cuentas de responsables y admin no se reclaman con este enlace.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.core import signing
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import F
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from apps.community import moderation
from apps.notifications import services as notifications

from . import services
from .models import Person, PersonStatus, TeamSignupLink

SALT = "accounts.team_signup.v1"
VALID_DAYS = (7, 14, 30)
DEFAULT_DAYS = 14
SIGNATURE_MAX_AGE = (max(VALID_DAYS) + 1) * 24 * 3600  # el vencimiento real es el del registro

MAX_SUBMISSIONS = 10
SUBMISSION_WINDOW_SECONDS = 15 * 60


def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def active_link() -> TeamSignupLink | None:
    return TeamSignupLink.objects.filter(
        revoked_at__isnull=True, expires_at__gt=timezone.now()
    ).first()


def revoke_active() -> int:
    return TeamSignupLink.objects.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())


@transaction.atomic
def create_link(by: Person | None, days: int = DEFAULT_DAYS) -> tuple[TeamSignupLink, str]:
    """Genera un enlace nuevo y revoca el anterior. Devuelve (registro, token): el token no se guarda en ninguna parte."""
    if days not in VALID_DAYS:
        raise ValueError(f"La vigencia debe ser de {', '.join(map(str, VALID_DAYS))} días.")
    revoke_active()
    secret = secrets.token_urlsafe(24)
    record = TeamSignupLink.objects.create(
        secret_hash=_hash(secret),
        created_by=by,
        expires_at=timezone.now() + timedelta(days=days),
    )
    token = signing.TimestampSigner(salt=SALT).sign(f"{record.pk}.{secret}")
    return record, token


def link_url(token: str) -> str:
    return services.academy_url() + reverse("accounts:team_signup", args=[token])


@transaction.atomic
def generate(by: Person, days: int = DEFAULT_DAYS) -> str:
    """Enlace completo para mostrar una vez, con constancia en la bitácora de moderación (nunca el enlace)."""
    record, token = create_link(by, days)
    moderation.log(by, "team_link", by, f"Enlace del equipo #{record.pk} por {days} días")
    return link_url(token)


@transaction.atomic
def revoke(by: Person) -> bool:
    link = active_link()
    if link is None:
        return False
    link.revoked_at = timezone.now()
    link.save(update_fields=["revoked_at", "updated_at"])
    moderation.log(by, "team_link_revoke", by, f"Enlace del equipo #{link.pk} revocado")
    return True


def resolve(token: str) -> TeamSignupLink | None:
    """El registro vigente del token, o None (inválido, manipulado, vencido o revocado: un solo resultado)."""
    try:
        payload = signing.TimestampSigner(salt=SALT).unsign(token or "", max_age=SIGNATURE_MAX_AGE)
        pk, secret = payload.split(".", 1)
        record = TeamSignupLink.objects.filter(pk=int(pk)).first()
    except (signing.BadSignature, ValueError):
        return None
    if record is None or record.revoked_at is not None or record.expires_at <= timezone.now():
        return None
    if not constant_time_compare(_hash(secret), record.secret_hash):
        return None
    return record


# --- límite de envíos por IP y enlace ---------------------------------------------------------------------


def _key(ip: str, link: TeamSignupLink) -> str:
    return "team-signup:" + hashlib.sha256(f"{ip}|{link.pk}".encode()).hexdigest()[:32]


def blocked(ip: str, link: TeamSignupLink) -> bool:
    return cache.get(_key(ip, link), 0) >= MAX_SUBMISSIONS


def register_submission(ip: str, link: TeamSignupLink) -> None:
    key = _key(ip, link)
    if cache.add(key, 1, SUBMISSION_WINDOW_SECONDS):
        return
    try:
        cache.incr(key)
    except ValueError:  # venció entre add e incr
        cache.add(key, 1, SUBMISSION_WINDOW_SECONDS)


# --- inscripción ---------------------------------------------------------------------------------------------

LOGGED_IN = "logged_in"  # tenía el correo aprobado y sin contraseña: quedó dentro
PENDING = "pending"  # cuenta creada o completada, a la espera de un admin
HAS_ACCOUNT = "has_account"  # el correo ya tiene contraseña
PERSONAL_LINK = "personal_link"  # responsable o admin: usa su enlace personal
REFUSED = "refused"  # suspendida o inactiva (sin detalles)


@dataclass
class Enrollment:
    kind: str
    person: Person | None = None


def _is_privileged(person: Person | None, login: str) -> bool:
    if services.is_bootstrap_admin(login):
        return True
    return person is not None and (
        person.role != "member" or person.is_staff or person.is_superuser
    )


@transaction.atomic
def enroll(
    link: TeamSignupLink,
    *,
    login: str,
    display_name: str,
    password: str,
    character_class: str = "",
) -> Enrollment:
    """Aplica las reglas del enlace del equipo. El correo ya viene normalizado y la contraseña validada."""
    person = Person.objects.filter(login=login).first()

    if person is not None:
        if person.status == PersonStatus.SUSPENDED or not person.is_active:
            return Enrollment(REFUSED)
        if person.has_usable_password():
            return Enrollment(HAS_ACCOUNT)
    if _is_privileged(person, login):
        return Enrollment(PERSONAL_LINK)

    if person is None:
        try:
            with transaction.atomic():
                person = Person.objects.create_user(login=login, password=password)
        except IntegrityError:  # otra inscripción creó el mismo correo entre tanto
            return Enrollment(HAS_ACCOUNT)
        services.set_role(person, "member")
        created = True
    else:
        person.set_password(password)
        created = False

    person.display_name = display_name.strip()[:150]
    if character_class:
        person.character_class = character_class
    person.invite_nonce = ""
    person.save(
        update_fields=["password", "display_name", "character_class", "invite_nonce", "updated_at"]
    )
    TeamSignupLink.objects.filter(pk=link.pk).update(uses=F("uses") + 1)

    if person.status == PersonStatus.APPROVED:
        return Enrollment(LOGGED_IN, person)
    if created:
        notifications.notify_leads(
            "person_pending",
            f"{person.name} pidió acceso",
            person.login,
            url="/moderacion/",
            key=f"pending:{person.pk}",
        )
    return Enrollment(PENDING, person)
