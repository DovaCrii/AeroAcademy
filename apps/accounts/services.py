"""Identidad, roles y aprobación. La lógica vive aquí; las vistas y el admin solo la llaman."""

from email.header import decode_header as _decode_header
from email.header import make_header
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.models import Group
from django.utils import timezone

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
    return person


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
