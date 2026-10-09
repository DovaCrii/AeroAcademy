"""Identidad, roles y aprobación. La lógica vive aquí; las vistas y el admin solo la llaman."""

import hashlib
import secrets
from email.header import decode_header as _decode_header
from email.header import make_header
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.models import Group
from django.core import signing
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from apps.notifications import services as notifications

from .models import Person, PersonStatus

ROLES = ("member", "lead", "admin")


def normalize_login(raw: str) -> str:
    return (raw or "").strip().lower()


def decode_header_value(value: str) -> str:
    """Tailscale puede mandar el nombre en RFC 2047 o en UTF-8 leído como latin-1."""
    value = (value or "").strip()
    if not value:
        return ""
    if "=?" in value:
        try:
            return str(make_header(_decode_header(value))).strip()
        except Exception:
            pass
    try:
        return value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


def clean_avatar_url(url: str) -> str:
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme in {"http", "https"} and parsed.netloc and len(url) <= 500:
        return url
    return ""


def is_bootstrap_admin(login: str) -> bool:
    return normalize_login(login) in {normalize_login(x) for x in settings.BOOTSTRAP_ADMINS}


def set_role(person: Person, role: str) -> Person:
    if role not in ROLES:
        raise ValueError(f"Rol desconocido: {role}")
    groups = {name: Group.objects.get_or_create(name=name)[0] for name in ROLES}
    person.groups.set([groups[role]])
    person.is_superuser = person.is_staff = role == "admin"
    person.save(update_fields=["is_superuser", "is_staff", "updated_at"])
    person.__dict__.pop("role", None)
    return person


def approve(person: Person, by: Person | None = None) -> Person:
    person.status = PersonStatus.APPROVED
    person.approved_by = by
    person.approved_at = timezone.now()
    person.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    notifications.notify(
        person,
        "welcome",
        "¡Te damos la bienvenida al gremio!",
        "Completa tu hoja de personaje para ganar tu primera insignia.",
        url="/perfil/editar/",
        key="welcome",
    )
    return person


def suspend(person: Person) -> Person:
    person.status = PersonStatus.SUSPENDED
    person.save(update_fields=["status", "updated_at"])
    return person


def ensure_bootstrap(person: Person) -> bool:
    """Quien figura en BOOTSTRAP_ADMINS queda admin y aprobada. Devuelve si cambió algo."""
    if not is_bootstrap_admin(person.login):
        return False
    changed = False
    if person.role != "admin":
        set_role(person, "admin")
        changed = True
    if person.status != PersonStatus.APPROVED:
        approve(person)
        changed = True
    return changed


def init_new_person(person: Person) -> Person:
    """Primera vez que Tailscale presenta a esta persona: rol member y estado pendiente."""
    person.set_unusable_password()
    person.save(update_fields=["password", "updated_at"])
    set_role(person, "member")
    ensure_bootstrap(person)
    if person.status == PersonStatus.PENDING:
        notifications.notify_leads(
            "person_pending",
            f"{person.name} pidió acceso",
            person.login,
            url="/moderacion/",
            key=f"pending:{person.pk}",
        )
    return person


def grant_access(login: str, role: str = "member") -> tuple[Person, bool]:
    """Aprueba a una persona con un rol desde la consola de la VM (`manage.py aprobar`). Si aún no entra nunca,
    queda creada y aprobada: al llegar por Tailscale con ese login entra directo. Devuelve (persona, creada)."""
    login = normalize_login(login)
    if "@" not in login or len(login) > 254:
        raise ValueError(f"«{login}» no parece un login de Tailscale (correo).")
    if role not in ROLES:
        raise ValueError(f"Rol desconocido: {role}. Usa {', '.join(ROLES)}.")
    person = Person.objects.filter(login=login).first()
    created = person is None
    if (
        created
    ):  # sin init_new_person: no hace falta avisar a los responsables de una solicitud ya resuelta
        person = set_role(Person.objects.create_user(login=login), "member")
    if person.status != PersonStatus.APPROVED:
        approve(person)
    if is_bootstrap_admin(login):
        ensure_bootstrap(
            person
        )  # BOOTSTRAP_ADMINS siempre queda admin, pida lo que pida el comando
    elif person.role != role:
        set_role(person, role)
    return person, created


def sync_identity(person: Person, *, display_name: str = "", avatar_url: str = "") -> Person:
    """Actualiza nombre y foto desde los encabezados de Tailscale y reaplica BOOTSTRAP_ADMINS."""
    changed = []
    name = (display_name or "").strip()[:150]
    if name and name != person.display_name:
        person.display_name = name
        changed.append("display_name")
    if avatar_url:
        url = clean_avatar_url(avatar_url)
        if url != person.avatar_url:
            person.avatar_url = url
            changed.append("avatar_url")
    if changed:
        person.save(update_fields=[*changed, "updated_at"])
    ensure_bootstrap(person)
    return person


# --- invitación + contraseña (D34) ----------------------------------------------------------------------------
# El admin genera un enlace de registro firmado (7 días, un solo uso) para una persona ya aprobada. La persona
# elige su contraseña y queda dentro aunque su login de Tailscale no coincida o llegue desde un equipo compartido.

DEFAULT_ACADEMY_URL = "https://aeroacademy.tailccd107.ts.net"
SIGNUP_SALT = "accounts.signup.v1"
SIGNUP_MAX_AGE = 7 * 24 * 3600
PASSWORD_BACKEND = "django.contrib.auth.backends.ModelBackend"

LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW_SECONDS = 15 * 60


def academy_url() -> str:
    return getattr(settings, "ACADEMY_URL", DEFAULT_ACADEMY_URL).rstrip("/")


def _fingerprint(person: Person) -> str:
    """Huella del hash de la contraseña vigente: si la contraseña cambia por otro camino, el enlace deja de valer."""
    return salted_hmac(SIGNUP_SALT, f"{person.pk}:{person.password}").hexdigest()[:16]


def can_receive_link(person: Person) -> bool:
    return person.is_active and person.status == PersonStatus.APPROVED


def issue_signup_token(person: Person) -> str:
    """Genera un enlace nuevo (invalida los anteriores). Solo para personas aprobadas y activas."""
    if not can_receive_link(person):
        raise ValueError("Solo se puede invitar a una persona aprobada (apruébala primero).")
    person.invite_nonce = secrets.token_hex(8)
    person.save(update_fields=["invite_nonce", "updated_at"])
    payload = f"{person.pk}.{person.invite_nonce}.{_fingerprint(person)}"
    return signing.TimestampSigner(salt=SIGNUP_SALT).sign(payload)


def signup_url(person: Person) -> str:
    """Genera un enlace nuevo y lo devuelve completo (con la dirección de la academia en la tailnet)."""
    return academy_url() + reverse("accounts:signup", args=[issue_signup_token(person)])


def resolve_signup_token(token: str) -> Person | None:
    """La persona dueña del enlace, o None si es inválido, venció, ya se usó o fue reemplazado. Un solo resultado
    para todos los fallos: no revela nada sobre correos ni personas."""
    try:
        payload = signing.TimestampSigner(salt=SIGNUP_SALT).unsign(
            token or "", max_age=SIGNUP_MAX_AGE
        )
        pk, nonce, fingerprint = payload.split(".")
        person = Person.objects.filter(pk=int(pk)).first()
    except (signing.BadSignature, ValueError):
        return None
    if person is None or not can_receive_link(person) or not person.invite_nonce:
        return None
    if not (
        constant_time_compare(nonce, person.invite_nonce)
        and constant_time_compare(fingerprint, _fingerprint(person))
    ):
        return None
    return person


def complete_signup(
    person: Person, *, display_name: str, password: str, character_class: str = ""
) -> Person:
    """Fija la contraseña y consume el enlace (borra el nonce). Se llama dentro de una transacción."""
    person.set_password(password)
    person.display_name = display_name.strip()[:150]
    if character_class:
        person.character_class = character_class
    person.invite_nonce = ""
    person.save(
        update_fields=["password", "display_name", "character_class", "invite_nonce", "updated_at"]
    )
    return person


# --- límite de intentos de entrada ----------------------------------------------------------------------------


def _attempt_key(ip: str, email: str) -> str:
    digest = hashlib.sha256(f"{ip}|{normalize_login(email)}".encode()).hexdigest()[:32]
    return f"login-fail:{digest}"


def login_blocked(ip: str, email: str) -> bool:
    return cache.get(_attempt_key(ip, email), 0) >= LOGIN_MAX_FAILURES


def register_login_failure(ip: str, email: str) -> None:
    key = _attempt_key(ip, email)
    if cache.add(key, 1, LOGIN_WINDOW_SECONDS):
        return
    try:
        cache.incr(key)
    except ValueError:  # venció entre add e incr
        cache.add(key, 1, LOGIN_WINDOW_SECONDS)


def clear_login_failures(ip: str, email: str) -> None:
    cache.delete(_attempt_key(ip, email))
