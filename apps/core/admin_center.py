"""Centro de administración (D42): un solo lugar para la situación del equipo, las cuentas y el servidor.

Solo lee y arma datos; las acciones que cambian algo llaman a los servicios de siempre (`accounts`, `team`,
`community.moderation`). Nada de secretos, rutas del servidor ni contenido de credenciales: de las credenciales solo
se cuentan cuentas. Las vistas están en `admin_views.py`.
"""

import logging
import os
import re
import secrets
import shutil
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.db.models import Case, Count, Exists, IntegerField, Max, OuterRef, Q, Value, When
from django.urls import reverse
from django.utils import timezone
from django.utils.timesince import timesince

from apps.accounts import services as accounts
from apps.accounts.models import CharacterClass, Person, PersonStatus
from apps.catalog.models import Discipline
from apps.community import moderation
from apps.community.models import ModerationLog
from apps.core.models import TaskRun
from apps.credentials import services as credential_services
from apps.credentials.models import Credential
from apps.notifications.models import Notification
from apps.paths.models import LearningPath
from apps.team import onboarding

URGENT_DAYS = 30  # el contador «urgente» del Centro; los avisos de la campana siguen a 60 (Q5)

ADMIN = "admin"
LEAD = "lead"


def access(user, request) -> str | None:
    """«admin», «lead» o None. None siempre es un 404: el Centro no existe para quien no administra ni en la puerta
    pública (doble llave: el prefijo bloqueado y esta comprobación)."""
    if getattr(request, "public_door", False) or settings.PUBLIC_DOOR:
        return None
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        return None
    if user.status != PersonStatus.APPROVED:
        return None
    if user.is_admin:
        return ADMIN
    if user.is_lead:
        return LEAD
    return None


# --- cuentas: contadores ----------------------------------------------------------------------------------------


def people_counts() -> dict:
    """Cuántas personas hay en cada estado, en UNA consulta (no crece con los datos).

    Activa = aprobada, con la cuenta encendida y que ya entró; «nunca entró» = aprobada que aún no entra.
    «Sin rol» = aprobada sin grupo asignado (cuenta como miembro); «sin disciplina» = aprobada sin disciplinas."""
    live = Q(status=PersonStatus.APPROVED, is_active=True)
    return Person.objects.aggregate(
        total=Count("pk", distinct=True),
        pending=Count("pk", filter=Q(status=PersonStatus.PENDING), distinct=True),
        active=Count("pk", filter=live & Q(last_login__isnull=False), distinct=True),
        never=Count("pk", filter=live & Q(last_login__isnull=True), distinct=True),
        suspended=Count("pk", filter=Q(status=PersonStatus.SUSPENDED), distinct=True),
        deactivated=Count(
            "pk", filter=Q(status=PersonStatus.APPROVED, is_active=False), distinct=True
        ),
        no_role=Count(
            "pk", filter=live & Q(groups__isnull=True, is_superuser=False), distinct=True
        ),
        no_discipline=Count("pk", filter=live & Q(disciplines__isnull=True), distinct=True),
    )


# --- situación --------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Card:
    """Tarjeta-contador de la situación: cuenta, qué es, adónde lleva y qué decir cuando no hay nada."""

    key: str
    value: str
    label: str
    hint: str
    url: str
    warn: bool  # hay algo pendiente: borde ámbar y texto de acción


def _credential_counts(today) -> dict:
    return Credential.objects.filter(status=Credential.Status.VERIFIED).aggregate(
        soon=Count(
            "pk",
            filter=Q(expires_on__gte=today, expires_on__lte=today + timedelta(days=URGENT_DAYS)),
        ),
        gone=Count("pk", filter=Q(expires_on__lt=today)),
    )


def _plural(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


def _team_link_card(link) -> Card:
    url = reverse("core:admin_center") + "#enlace"
    if link is None:
        return Card(
            "team_link",
            "—",
            "enlace del equipo",
            "No hay un enlace vigente. Genera uno cuando quieras inscribir a más gente.",
            url,
            False,
        )
    days = max((link.expires_at - timezone.now()).days, 0)
    return Card(
        "team_link",
        str(days),
        f"{_plural(days, 'día', 'días')} de vigencia del enlace del equipo",
        f"{link.uses} {_plural(link.uses, 'inscripción', 'inscripciones')} hasta ahora.",
        url,
        days <= 2,
    )


def situation(
    level: str, *, counts: dict | None = None, link=None, server: dict | None = None
) -> list[Card]:
    """Las tarjetas de «Situación», cada una enlaza a donde se resuelve. El responsable ve solo sus colas
    (reportes y certificados por revisar, Q1); el admin, además, cuentas, vencimientos y el enlace del equipo.
    `counts` (de `people_counts`), `link` (de `team_link.active_link`) y `server` (de `server_status`) los trae
    la vista, que los usa también en sus bloques: así no se repite ninguna consulta."""
    today = timezone.localdate()
    cards: list[Card] = []
    is_admin = level == ADMIN
    if is_admin:
        counts = counts if counts is not None else people_counts()
        n = counts["pending"]
        cards.append(
            Card(
                "pending",
                str(n),
                _plural(n, "persona esperando aprobación", "personas esperando aprobación"),
                "Aprueba o rechaza desde Cuentas." if n else "Nada pendiente.",
                reverse("core:admin_accounts") + "?estado=pendiente",
                n > 0,
            )
        )
    n = moderation.open_reports().count()
    cards.append(
        Card(
            "reports",
            str(n),
            _plural(n, "reporte del foro sin resolver", "reportes del foro sin resolver"),
            "Revísalos en Moderación." if n else "Nada pendiente.",
            reverse("community:moderation") + "#m-reports",
            n > 0,
        )
    )
    n = credential_services.review_queue().count()
    cards.append(
        Card(
            "review",
            str(n),
            _plural(n, "certificado por revisar", "certificados por revisar"),
            "Verifícalos o recházalos." if n else "Nada pendiente.",
            reverse("credentials:review_queue"),
            n > 0,
        )
    )
    if is_admin:
        creds = _credential_counts(today)
        n = creds["soon"]
        gone = creds["gone"]
        hint = "Avísales a tiempo." if n else "Nada pendiente."
        if gone:
            hint += f" {gone} ya {_plural(gone, 'vencida', 'vencidas')}."
        cards.append(
            Card(
                "expiring",
                str(n),
                _plural(
                    n,
                    f"credencial vence en {URGENT_DAYS} días",
                    f"credenciales vencen en {URGENT_DAYS} días",
                ),
                hint,
                reverse("credentials:expirations") + "?equipo=1",
                n > 0 or gone > 0,
            )
        )
    if is_admin and server is not None:
        cards.append(server_card(server))
    if is_admin:
        cards.append(_team_link_card(link))
    return cards


# --- enlaces agrupados --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Link:
    icon: str  # nombre de un garabato de img/doodles
    title: str
    text: str
    url: str
    level: str  # quién lo ve: «lead» (responsable y admin) o «admin»


def _links() -> list[tuple[str, str, list[Link]]]:
    """(id, título, filas). Solo destinos que existen: cada fila lleva a una pantalla de 1 clic."""
    return [
        (
            "cuentas",
            "Cuentas y accesos",
            [
                Link(
                    "equipo",
                    "Todas las cuentas",
                    "Quién está pendiente, activa, suspendida o sin rol, y cómo entra cada persona.",
                    reverse("core:admin_accounts"),
                    ADMIN,
                ),
                Link(
                    "equipo",
                    "Agregar personas",
                    "Pega correos o un CSV para dejarlas pre-aprobadas.",
                    reverse("team:people_add"),
                    ADMIN,
                ),
                Link(
                    "equipo",
                    "Plantel e invitaciones por área",
                    "Disciplinas, cargo y texto de invitación de cada persona.",
                    reverse("team:people"),
                    ADMIN,
                ),
                Link(
                    "equipo",
                    "Mi segundo factor (2FA)",
                    "Activa el código de un solo uso para entrar por internet.",
                    reverse("accounts:two_factor"),
                    LEAD,
                ),
            ],
        ),
        (
            "contenido",
            "Contenido",
            [
                Link(
                    "rutas",
                    "Rutas",
                    "Las rutas de aprendizaje de la academia.",
                    reverse("paths:index"),
                    LEAD,
                ),
                Link(
                    "catalogo",
                    "Catálogo",
                    "Cursos y recursos por empresa de software.",
                    reverse("catalog:resources"),
                    LEAD,
                ),
            ],
        ),
        (
            "comunidad",
            "Comunidad",
            [
                Link(
                    "foro",
                    "Moderación",
                    "Reportes del foro, personas por aprobar y bitácora.",
                    reverse("community:moderation"),
                    LEAD,
                ),
                Link(
                    "foro",
                    "Anuncios",
                    "Publica un aviso para todo el equipo.",
                    reverse("community:moderation") + "#m-ann",
                    LEAD,
                ),
            ],
        ),
        (
            "credenciales",
            "Credenciales",
            [
                Link(
                    "certificados",
                    "Por revisar",
                    "La cola de certificados que esperan una verificación.",
                    reverse("credentials:review_queue"),
                    LEAD,
                ),
                Link(
                    "certificados",
                    "Vencimientos del equipo",
                    "Qué credenciales vencen pronto y quién las tiene.",
                    reverse("credentials:expirations") + "?equipo=1",
                    LEAD,
                ),
                Link(
                    "documentos",
                    "Exportar evidencia",
                    "Descarga la evidencia de certificados del equipo.",
                    reverse("credentials:export"),
                    LEAD,
                ),
            ],
        ),
        (
            "sistema",
            "Sistema",
            [
                Link(
                    "documentos",
                    "Bitácora",
                    "Quién hizo qué en moderación y cuentas, solo para leer.",
                    reverse("core:admin_log"),
                    LEAD,
                ),
            ],
        ),
    ]


def link_sections(level: str) -> list[dict]:
    """Las secciones de enlaces que corresponden a `level` (las vacías no salen)."""
    out = []
    for key, title, links in _links():
        rows = [link for link in links if level == ADMIN or link.level == LEAD]
        if rows:
            out.append({"key": key, "title": title, "links": rows})
    return out


# --- cuentas: listado, frases y acciones -------------------------------------------------------------------------

STATES = {
    "pendiente": "Pendientes",
    "activa": "Activas",
    "nunca": "Nunca entraron",
    "suspendida": "Suspendidas",
    "desactivada": "Desactivadas",
    "sin-rol": "Sin rol",
    "sin-disciplina": "Sin disciplina",
}
# Qué contador de `people_counts` acompaña a cada filtro.
STATE_COUNT = {
    "pendiente": "pending",
    "activa": "active",
    "nunca": "never",
    "suspendida": "suspended",
    "desactivada": "deactivated",
    "sin-rol": "no_role",
    "sin-disciplina": "no_discipline",
}
PAGE_SIZE = 50
QUERY_MAX = 100
ROLE_LABELS = {"member": "Miembro", "lead": "Responsable", "admin": "Admin"}


def _ago(moment, now) -> str:
    """«hace 3 días», «hace un momento»: una sola unidad, en español simple."""
    if moment is None:
        return ""
    if now - moment < timedelta(minutes=1):
        return "hace un momento"
    return "hace " + timesince(moment, now, depth=1).replace("\xa0", " ")


def account_sentence(person, now, *, no_role=False, via="") -> str:
    """El estado de una cuenta en una o dos frases. Se calcula aquí y no en la plantilla."""
    if person.status == PersonStatus.PENDING:
        text = (
            f"Pidió acceso {_ago(person.created_at, now)}. "
            "Todavía no puede entrar: apruébala o recházala."
        )
    elif person.status == PersonStatus.SUSPENDED:
        text = "Sin acceso. Sus datos y certificados se conservan."
    elif not person.is_active:
        text = "Cuenta desactivada en la administración técnica."
    elif person.last_login is None:
        if person.has_usable_password():
            text = "Aprobada y con contraseña, pero aún no entra."
        else:
            text = (
                "Aprobada, aún no entra. Necesita Tailscale o un enlace personal "
                "para crear su contraseña."
            )
    else:
        text = f"Entró {_ago(person.last_login, now)}" + (f" {via}." if via else ".")
    if no_role and person.status == PersonStatus.APPROVED:
        text += " Sin rol asignado: cuenta como miembro."
    return text


def _fixed_admins() -> set[str]:
    return {accounts.normalize_login(x) for x in settings.BOOTSTRAP_ADMINS}


def access_via(person) -> str:
    """«por Tailscale», «con contraseña», «desde internet (puerta pública)» o vacío si aún no hay dato.
    Sin consulta: el registro de entradas viene con `select_related`."""
    trace = getattr(person, "login_trace", None)
    return trace.via_text() if trace is not None else ""


def _state_key(person) -> str:
    if person.status == PersonStatus.PENDING:
        return "pendiente"
    if person.status == PersonStatus.SUSPENDED:
        return "suspendida"
    if not person.is_active:
        return "desactivada"
    return "nunca" if person.last_login is None else "activa"


def _row(person, viewer, now, fixed) -> dict:
    approved = person.status == PersonStatus.APPROVED
    live = approved and person.is_active
    # `has_group`, `in_lead_group` y `has_discipline` se anotan en la consulta (sin consultas por persona).
    if person.is_superuser:
        role = "admin"
    else:
        role = "lead" if person.in_lead_group else "member"
    no_role = live and not person.has_group and not person.is_superuser
    is_self = person.pk == viewer.pk
    is_fixed = person.login in fixed
    tm = getattr(person, "team_member", None)
    totp = getattr(person, "totp", None)
    chips = []
    if is_fixed:
        chips.append(("Admin fija", "plain"))
    if approved:
        chips.append(
            ("Contraseña: sí", "ok")
            if person.has_usable_password()
            else ("Contraseña: no", "plain")
        )
        trace = getattr(person, "login_trace", None)
        if trace is not None:
            for moment, label in (
                (trace.last_tailscale_at, "Entra por Tailscale"),
                (trace.last_password_at, "Entra con contraseña"),
                (trace.last_public_at, "Entra desde internet"),
            ):
                if moment:
                    chips.append((f"{label} ({timezone.localtime(moment):%d/%m})", "ok"))
        if tm is not None and tm.tailscale_invited:
            chips.append(("Tailscale: invitada", "ok"))
        if totp is not None and totp.confirmed_at and role != "member":
            chips.append(("2FA activo", "ok"))
        if live and not person.has_discipline:
            chips.append(("Sin disciplina", "pend"))
    if no_role:
        chips.append(("Sin rol", "pend"))
    return {
        "person": person,
        "key": _state_key(person),
        "role": role,
        "role_label": ROLE_LABELS[role],
        "sentence": account_sentence(person, now, no_role=no_role, via=access_via(person)),
        "chips": chips,
        "is_self": is_self,
        "fixed": is_fixed,
        "can_approve": person.status == PersonStatus.PENDING,
        "can_suspend": approved and not is_self and not is_fixed,
        "can_reactivate": person.status == PersonStatus.SUSPENDED,
        "can_role": approved and not is_self and not is_fixed,
        "can_link": accounts.can_receive_link(person),
    }


def _filtered(state: str, q: str):
    live = Q(status=PersonStatus.APPROVED, is_active=True)
    through = Person.groups.through
    has_group = Exists(through.objects.filter(person_id=OuterRef("pk")))
    in_lead = Exists(through.objects.filter(person_id=OuterRef("pk"), group__name="lead"))
    has_discipline = Exists(Person.disciplines.through.objects.filter(person_id=OuterRef("pk")))
    qs = (
        Person.objects.select_related("team_member", "totp", "login_trace")
        .annotate(has_group=has_group, in_lead_group=in_lead, has_discipline=has_discipline)
        .annotate(
            order_state=Case(
                When(status=PersonStatus.PENDING, then=Value(0)),
                When(status=PersonStatus.SUSPENDED, then=Value(2)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by("order_state", "display_name", "login")
    )
    if state == "pendiente":
        qs = qs.filter(status=PersonStatus.PENDING)
    elif state == "activa":
        qs = qs.filter(live, last_login__isnull=False)
    elif state == "nunca":
        qs = qs.filter(live, last_login__isnull=True)
    elif state == "suspendida":
        qs = qs.filter(status=PersonStatus.SUSPENDED)
    elif state == "desactivada":
        qs = qs.filter(status=PersonStatus.APPROVED, is_active=False)
    elif state == "sin-rol":
        qs = qs.filter(live, has_group=False, is_superuser=False)
    elif state == "sin-disciplina":
        qs = qs.filter(live, has_discipline=False)
    if q:
        qs = qs.filter(Q(login__icontains=q) | Q(display_name__icontains=q))
    return qs


def accounts_page(viewer, *, state: str = "", q: str = "", page=1) -> dict:
    """La página de cuentas: contadores, filas con su frase y acciones. Consultas constantes (no crecen con las
    personas): contadores, total y la página, nada más."""
    state = state if state in STATES else ""
    q = (q or "").strip()[:QUERY_MAX]
    current = Paginator(_filtered(state, q), PAGE_SIZE).get_page(page)
    now = timezone.now()
    fixed = _fixed_admins()
    counts = people_counts()
    return {
        "rows": [_row(p, viewer, now, fixed) for p in current.object_list],
        "page": current,
        "counts": counts,
        "state": state,
        "q": q,
        "filters": [
            {"key": key, "label": label, "n": counts[STATE_COUNT[key]]}
            for key, label in STATES.items()
            if key != "desactivada" or counts["deactivated"]
        ],
    }


def pending_people(limit: int = 5) -> list:
    """Las primeras personas por aprobar, con «pidió acceso hace…» (sin correos: en el Centro solo van los nombres)."""
    now = timezone.now()
    people = (
        Person.objects.filter(status=PersonStatus.PENDING)
        .only("id", "login", "display_name", "created_at")
        .order_by("created_at")[:limit]
    )
    return [{"person": p, "ago": _ago(p.created_at, now)} for p in people]


# Acciones: las reglas de siempre (servicios de `accounts` y `team`) y constancia en la bitácora de moderación.


def _require_admin(by):
    if not by.is_admin:
        raise PermissionError("Solo un admin puede hacer esto.")


def approve_pending(person, by, *, role="member", discipline_slugs=(), character_class=""):
    """Aprueba a alguien que está pendiente (como miembro o responsable) y deja constancia."""
    _require_admin(by)
    if person.status != PersonStatus.PENDING:
        raise ValueError("Esa persona ya no está pendiente.")
    role = role if role in ("member", "lead") else "member"
    with transaction.atomic():
        accounts.approve(person, by)
        accounts.set_role(person, role)
        person.disciplines.set(Discipline.objects.filter(slug__in=list(discipline_slugs)))
        if character_class in CharacterClass.values:
            person.character_class = character_class
            person.save(update_fields=["character_class", "updated_at"])
        moderation.log(by, "approve_person", person, person.name, role)
    return person


def reject_pending(person, by):
    _require_admin(by)
    if person.status != PersonStatus.PENDING:
        raise ValueError("Esa persona ya no está pendiente.")
    with transaction.atomic():
        accounts.suspend(person)
        moderation.log(by, "reject_person", person, person.name)
    return person


def suspend_account(person, by) -> bool:
    """Suspende a una persona aprobada. False si ya estaba suspendida (no repite el registro)."""
    _require_admin(by)
    if person.pk == by.pk:
        raise PermissionError("No puedes suspender tu propia cuenta.")
    if accounts.is_bootstrap_admin(person.login):
        raise PermissionError("Esa persona es admin fija (BOOTSTRAP_ADMINS): no se suspende.")
    if person.status == PersonStatus.SUSPENDED:
        return False
    if person.status != PersonStatus.APPROVED:
        raise ValueError("Solo se suspende a una persona aprobada (si está pendiente, recházala).")
    with transaction.atomic():
        accounts.suspend(person)
        moderation.log(by, "suspend_person", person, person.name)
    return True


def reactivate_account(person, by) -> bool:
    """Devuelve el acceso a una persona suspendida. False si no estaba suspendida."""
    _require_admin(by)
    if person.status != PersonStatus.SUSPENDED:
        return False
    with transaction.atomic():
        accounts.approve(person, by)
        moderation.log(by, "reactivate_person", person, person.name)
    return True


def change_role(person, by, role) -> bool:
    """Cambia el rol (o fija el de una cuenta «sin rol»). False si no había nada que cambiar."""
    _require_admin(by)
    if role not in accounts.ROLES:
        raise ValueError("Rol desconocido.")
    if person.pk == by.pk:
        raise PermissionError("No puedes cambiar tu propio rol.")
    if accounts.is_bootstrap_admin(person.login):
        raise PermissionError("Esa persona es admin fija (BOOTSTRAP_ADMINS).")
    if person.status != PersonStatus.APPROVED:
        raise ValueError("Solo se cambia el rol de una persona aprobada.")
    groups = set(person.groups.values_list("name", flat=True))
    current = "admin" if person.is_superuser else ("lead" if "lead" in groups else "member")
    if role == current and groups:
        return False
    with transaction.atomic():
        accounts.set_role(person, role)
        moderation.log(by, "update_person", person, f"rol {role}")
    return True


# --- bitácora (solo lectura) ----------------------------------------------------------------------------------

LOG_PAGE_SIZE = 50
# Lista blanca de acciones que se pueden filtrar, con su nombre en español. Una acción que no esté aquí (p. ej. una
# nueva de otro módulo) se ve igual en la lista, pero no se ofrece como filtro.
LOG_ACTIONS = {
    "approve_person": "Persona aprobada",
    "reject_person": "Acceso rechazado",
    "suspend_person": "Persona suspendida",
    "reactivate_person": "Persona reactivada",
    "update_person": "Cambio de rol, área o cargo",
    "import_person": "Alta por importación",
    "invite_mark": "Marcada como invitada",
    "invite_unmark": "Marca de invitación quitada",
    "signup_link": "Enlace personal generado",
    "team_link": "Enlace del equipo generado",
    "team_link_revoke": "Enlace del equipo revocado",
    "hide": "Contenido ocultado",
    "unhide": "Contenido mostrado de nuevo",
    "dismiss_report": "Reporte descartado",
    "pin": "Hilo fijado",
    "unpin": "Hilo desfijado",
    "move": "Hilo movido",
    "rename": "Hilo renombrado",
}


def log_page(*, action: str = "", page=1) -> dict:
    """Una página (50) de la bitácora de moderación, de la más nueva a la más antigua. Consultas constantes."""
    action = action if action in LOG_ACTIONS else ""
    qs = ModerationLog.objects.select_related("actor").order_by("-created_at", "-id")
    if action:
        qs = qs.filter(action=action)
    current = Paginator(qs, LOG_PAGE_SIZE).get_page(page)
    rows = [
        {
            "entry": e,
            "label": LOG_ACTIONS.get(e.action, e.action),
            "actor": e.actor.name if e.actor_id else "Alguien que ya no está",
        }
        for e in current.object_list
    ]
    return {
        "rows": rows,
        "page": current,
        "action": action,
        "actions": list(LOG_ACTIONS.items()),
    }


# --- servidor: salud, respaldos, versión y puerta pública ----------------------------------------------------------
# Todo es lectura acotada y a prueba de fallas: una comprobación que lanza una excepción dice «No se pudo comprobar»
# (nunca un 500) y nada de lo que se muestra es una ruta del servidor, un secreto ni un dato de las credenciales.

logger = logging.getLogger("apps.core")

BACKUP_STALE_HOURS = 36
DISK_LOW_PERCENT = 10
SCAN_LIMIT = 2000  # entradas que se miran de la carpeta de respaldos, como máximo
PUBLIC_PROBE_SECONDS = 0.5
PUBLIC_PROBE_CACHE_SECONDS = 60
PUBLIC_PROBE_KEY = "admin-center:public-door"
CANT_CHECK = "No se pudo comprobar."

_DB_NAME = re.compile(r"^db-\d{4}-\d{2}-\d{2}\.sqlite3$")
_MEDIA_NAME = re.compile(r"^media-\d{4}-\d{2}-\d{2}\.tar\.gz$")
_PRE_NAME = re.compile(r"^pre-actualizar-[0-9TZ]{8,20}\.sqlite3$")
_COMMIT = re.compile(r"^[0-9a-f]{4,40}$")
_TAG = re.compile(r"^[\w.+/-]{1,40}$")
SYMBOLS = {"ok": "✓", "warn": "!", "none": "·"}


@dataclass(frozen=True)
class Check:
    """Una fila del servidor. Siempre texto + símbolo (✓ en orden, ! aviso, · sin dato): nunca solo color."""

    label: str
    state: str  # ok | warn | none
    text: str
    note: str = ""
    counts: bool = True  # si un aviso suma a «avisos del servidor» (el respaldo ya se cuenta en su propia fila)

    @property
    def symbol(self) -> str:
        return SYMBOLS[self.state]

    @property
    def word(self) -> str:
        """El estado en palabras, para quien lee con lector de pantalla."""
        return {"ok": "En orden", "warn": "Aviso", "none": "Sin dato"}[self.state]


def _safe(label: str, fn) -> list[Check]:
    """Corre una comprobación; si falla, una fila «No se pudo comprobar» (se anota solo el tipo de error)."""
    try:
        return fn()
    except Exception as exc:  # una comprobación de salud nunca puede tumbar el Centro
        logger.warning("Centro: no se pudo comprobar «%s» (%s)", label, type(exc).__name__)
        return [Check(label, "none", CANT_CHECK)]


def _human_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.0f} {unit}"
        size /= 1024
    return f"{n} B"


def _when(moment, now) -> str:
    """«hoy 03:30», «ayer 03:30» o «18/10 03:30», en hora local."""
    local, today = timezone.localtime(moment), timezone.localdate(now)
    day = local.date()
    stamp = local.strftime("%H:%M")
    if day == today:
        return f"hoy {stamp}"
    if day == today - timedelta(days=1):
        return f"ayer {stamp}"
    return f"{local:%d/%m} {stamp}"


def _database_checks() -> list[Check]:
    with connection.cursor() as cur:
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.execute("PRAGMA journal_mode")
        mode = (cur.fetchone() or [""])[0]
    size = ""
    try:
        size = f", {_human_size(os.path.getsize(connection.settings_dict['NAME']))}"
    except (OSError, TypeError):
        pass  # base en memoria (pruebas) o ilegible: sin tamaño
    if mode == "wal":
        return [Check("Base de datos", "ok", f"Responde (modo WAL{size}).")]
    if mode == "memory":
        return [Check("Base de datos", "ok", "Responde.")]
    return [
        Check(
            "Base de datos",
            "warn",
            "Responde, pero no está en modo WAL.",
            "El modo WAL permite leer mientras se escribe.",
        )
    ]


def _storage_checks() -> list[Check]:
    root = Path(settings.MEDIA_ROOT)
    probe = root
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    usage = shutil.disk_usage(probe)
    free = int(usage.free / usage.total * 100 + 0.5) if usage.total else 0
    writable = root.is_dir() and os.access(root, os.W_OK)
    if not writable:
        return [Check("Archivos privados", "warn", "No se puede escribir en su carpeta.")]
    if free < DISK_LOW_PERCENT:
        return [
            Check(
                "Archivos privados",
                "warn",
                f"Se puede escribir, pero el disco tiene solo {free} % libre.",
            )
        ]
    return [Check("Archivos privados", "ok", f"Se puede escribir · disco con {free} % libre.")]


def _cache_checks() -> list[Check]:
    probe = secrets.token_hex(4)
    cache.set("admin-center:probe", probe, 10)
    if cache.get("admin-center:probe") == probe:
        return [Check("Límite de intentos", "ok", "La memoria que protege la entrada funciona.")]
    return [
        Check(
            "Límite de intentos",
            "warn",
            "La memoria que protege la entrada no guarda datos.",
            "Sin ella, el límite de intentos de /entrar/ no se acuerda de nadie.",
        )
    ]


def _nala_checks() -> list[Check]:
    from apps.assistant import client

    if client.is_configured():
        return [Check("Nala", "ok", "Configurada.")]
    return [Check("Nala", "none", "Dormida (sin clave): los atajos funcionan igual.")]


def _scan(folder: Path):
    """Entradas de archivo de `folder` (acotado a SCAN_LIMIT)."""
    out = []
    with os.scandir(folder) as it:
        for i, entry in enumerate(it):
            if i >= SCAN_LIMIT:
                break
            if entry.is_file(follow_symlinks=False):
                out.append(entry)
    return out


def latest_backups(now=None) -> dict:
    """Lo más reciente de la carpeta de respaldos: solo nombre, fecha y tamaño (nunca la ruta).

    {"found": bool, "db": {...}|None, "media": {...}|None, "pre": {...}|None, "kept": int}"""
    now = now or timezone.now()
    empty = {"found": False, "db": None, "media": None, "pre": None, "kept": 0}
    folder = Path(settings.BACKUP_DIR)
    if not folder.is_dir():
        return empty
    kinds = {"db": [], "media": [], "pre": []}
    for entry in _scan(folder):
        for kind, pattern in (("db", _DB_NAME), ("media", _MEDIA_NAME), ("pre", _PRE_NAME)):
            if pattern.match(entry.name):
                stat = entry.stat()
                kinds[kind].append((entry.name, stat.st_size, stat.st_mtime))

    def newest(items):
        if not items:
            return None
        name, size, mtime = max(items, key=lambda i: (i[2], i[0]))
        moment = datetime.fromtimestamp(mtime, tz=UTC)
        return {
            "name": name,
            "size": _human_size(size),
            "when": _when(moment, now),
            "age_hours": (now - moment).total_seconds() / 3600,
        }

    return {
        "found": any(kinds.values()),
        "db": newest(kinds["db"]),
        "media": newest(kinds["media"]),
        "pre": newest(kinds["pre"]),
        "kept": len(kinds["db"]),
    }


def _backup_checks(data=None, failures=None) -> list[Check]:
    data = data if data is not None else latest_backups()
    failures = failures or {}
    now = timezone.now()
    failed_at = failures.get(UNIT_BACKUP)
    if not data["found"] or data["db"] is None:
        text = "No hay respaldos a la vista."
        if failed_at:
            text += f" El último intento falló el {_when(failed_at, now)}."
        return [Check("Último respaldo", "warn", text, "El respaldo diario corre a las 03:30.")]
    db, media = data["db"], data["media"]
    stale = db["age_hours"] > BACKUP_STALE_HOURS
    newer_failure = failed_at is not None and failed_at > now - timedelta(hours=db["age_hours"])
    tail = "."
    if stale:
        tail = " · hace más de un día y medio."
    if newer_failure:
        tail += f" El último intento falló el {_when(failed_at, now)}."
    checks = [
        Check(
            "Último respaldo",
            "warn" if stale or newer_failure else "ok",
            f"Base de datos: {db['name']} · {db['when']} · {db['size']}" + tail,
            f"{data['kept']} respaldo{'s' if data['kept'] != 1 else ''} diario{'s' if data['kept'] != 1 else ''} guardado{'s' if data['kept'] != 1 else ''}."
            + (f" Último previo a actualizar: {data['pre']['when']}." if data["pre"] else ""),
        )
    ]
    if media:
        checks.append(
            Check(
                "", "ok", f"Archivos privados: {media['name']} · {media['when']} · {media['size']}."
            )
        )
    return checks


def _read_info(path: Path) -> dict[str, str]:
    """Lee un archivo `clave=valor` pequeño (≤ 2 KB). Líneas raras se ignoran."""
    if not path.is_file() or path.stat().st_size > 2048:
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip():
            out[key.strip()] = value.strip()
    return out


def _stamp(value: str):
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def deployed_version() -> dict | None:
    """La versión instalada: del archivo que escribe el instalador y, si falta, de la info de la última actualización.
    {"commit", "tag", "at"} (con None donde no hay dato) o None si no se puede saber. Sin rutas."""
    for path, commit_key, date_key in (
        (Path(settings.VERSION_FILE), "commit", "deployed_at"),
        (Path(settings.PREV_INFO_FILE), "commit_after", "taken_at"),
    ):
        try:
            info = _read_info(path)
        except OSError:
            continue
        commit = info.get(commit_key, "").lower()
        if _COMMIT.match(commit):
            tag = info.get("tag", "")
            return {
                "commit": commit[:8],
                "tag": tag if _TAG.match(tag) else "",
                "at": _stamp(info.get(date_key, "")),
            }
    return None


def _version_checks() -> list[Check]:
    version = deployed_version()
    if version is None:
        return [
            Check(
                "Versión instalada",
                "none",
                "Sin dato: la app no puede saber qué versión está instalada.",
            )
        ]
    text = version["commit"]
    if version["tag"]:
        text += f" ({version['tag']})"
    if version["at"]:
        text += f" · instalada el {timezone.localtime(version['at']):%d/%m/%Y}"
    return [Check("Versión instalada", "ok", text + ".")]


def public_door_up() -> bool:
    """¿Responde el servicio de la puerta pública (127.0.0.1:PUERTO/healthz)? Espera 0,5 s y se acuerda 60 s.
    No sabe si el Funnel está publicado en Tailscale: solo si el servicio está en marcha."""
    cached = cache.get(PUBLIC_PROBE_KEY)
    if cached is not None:
        return cached == "up"
    host = next((h for h in settings.ALLOWED_HOSTS if h and not h.startswith(".")), "localhost")
    request = urllib.request.Request(
        f"http://127.0.0.1:{int(settings.PUBLIC_DOOR_PORT)}/healthz", headers={"Host": host}
    )
    try:
        with urllib.request.urlopen(request, timeout=PUBLIC_PROBE_SECONDS) as response:  # noqa: S310 (solo http local)
            up = response.status == 200
    except Exception:  # noqa: BLE001 - cualquier fallo de red es «no responde»
        up = False
    cache.set(PUBLIC_PROBE_KEY, "up" if up else "down", PUBLIC_PROBE_CACHE_SECONDS)
    return up


def _public_door_checks() -> list[Check]:
    if public_door_up():
        return [
            Check(
                "Puerta pública",
                "ok",
                "El servicio está en marcha.",
                "Si el Funnel de Tailscale está publicado no se ve desde aquí: se revisa en la VM.",
            )
        ]
    return [
        Check(
            "Puerta pública",
            "none",
            "El servicio no responde.",
            "Es lo normal si la puerta pública está apagada. El Funnel se revisa en la VM.",
        )
    ]


def private_courses() -> dict:
    """Cursos privados: carpetas con `ruta.json` frente a rutas ya cargadas. Solo cuentas (sin rutas ni nombres)."""
    root = Path(settings.PRIVATE_COURSES_DIR)
    if not root.is_dir():
        return {"installed": False, "folders": 0, "loaded": 0}
    slugs = []
    with os.scandir(root) as it:
        for i, entry in enumerate(it):
            if i >= 200:
                break
            if entry.is_dir(follow_symlinks=False) and (Path(entry.path) / "ruta.json").is_file():
                slugs.append(entry.name)
    loaded = LearningPath.objects.filter(slug__in=slugs).count() if slugs else 0
    return {"installed": True, "folders": len(slugs), "loaded": loaded}


def _courses_checks() -> list[Check]:
    data = private_courses()
    if not data["installed"]:
        return [Check("Cursos privados", "none", "Carpeta no instalada (es opcional).")]
    if data["folders"] == data["loaded"]:
        return [Check("Cursos privados", "ok", f"{data['loaded']} de {data['folders']} cargados.")]
    return [
        Check(
            "Cursos privados",
            "warn",
            f"{data['loaded']} de {data['folders']} cargados.",
            "Se cargan con el comando cargar_cursos_privados.",
        )
    ]


# --- tareas programadas ---------------------------------------------------------------------------------------

UNIT_BACKUP = "centro-backup.service"


@dataclass(frozen=True)
class Expected:
    """Una tarea que el Centro conoce: cómo se llama, cuándo corre y cuánto puede atrasarse (None = a mano)."""

    key: str  # nombre en TaskRun (el comando), o «backup» (su rastro son los archivos)
    label: str
    when: str
    tolerance_hours: int | None
    unit: str = ""  # unidad de systemd: de ahí salen los avisos `task_failed`


# Tabla fija; los horarios son los de deploy/*.timer.
EXPECTED = (
    Expected("backup", "Respaldo diario", "todos los días a las 03:30", 36, UNIT_BACKUP),
    Expected(
        "check_expirations",
        "Revisión de vencimientos",
        "todos los días a las 07:00",
        26,
        "centro-expiry.service",
    ),
    Expected(
        "teo_seguimiento",
        "Seguimiento de Nala",
        "los lunes a las 09:00",
        8 * 24,
        "centro-teo.service",
    ),
    Expected("revisar_enlaces", "Revisión de enlaces", "a mano", None),
    Expected("reindex_assistant", "Índice de búsqueda de Nala", "a mano", None),
    Expected("cargar_cursos_privados", "Carga de cursos privados", "a mano", None),
    Expected("seed_catalog", "Carga del catálogo", "a mano, en cada instalación", None),
)


def task_failures() -> dict[str, datetime]:
    """{unidad de systemd: aviso de fallo más reciente}, de las notificaciones `task_failed` que dejó `avisar_fallo`
    (clave `fallo:<unidad>:<fecha>`, una por responsable). Una sola consulta, acotada."""
    rows = (
        Notification.objects.filter(kind="task_failed", key__startswith="fallo:")
        .values("key")
        .annotate(last=Max("created_at"))
        .order_by("-last")[:100]
    )
    out: dict[str, datetime] = {}
    for row in rows:
        parts = row["key"].split(":")
        if len(parts) >= 3 and parts[1] not in out:
            out[parts[1]] = row["last"]
    return out


def _task_check(task: Expected, runs: dict, failures: dict, backups: dict, now) -> Check:
    label = f"{task.label} ({task.when})"
    failed_at = failures.get(task.unit) if task.unit else None
    if task.key == "backup":  # su rastro son los archivos; el aviso va en su propia fila
        db = backups["db"] if backups else None
        if db is None:
            return Check(label, "none", "Sin registro todavía.", counts=False)
        moment = now - timedelta(hours=db["age_hours"])
        late = db["age_hours"] > (task.tolerance_hours or 0)
        text = f"{'Atrasada' if late else 'Corrió'}: último {_when(moment, now)}."
        return Check(label, "warn" if late else "ok", text, counts=False)
    run = runs.get(task.key)
    if run is not None and run.ok is False:
        failed_at = max(filter(None, [failed_at, run.finished_at]), default=None)
    if run is None:
        if failed_at:
            return Check(label, "warn", f"Falló el {_when(failed_at, now)}.")
        return Check(label, "none", "Sin registro todavía.")
    last_ok = run.finished_at if run.ok else None
    if failed_at and (last_ok is None or failed_at > last_ok):
        return Check(
            label,
            "warn",
            f"Falló el {_when(failed_at, now)}."
            + (f" {run.summary}" if run.summary and run.ok is False else ""),
        )
    if run.ok is None:
        started = run.started_at
        if started and now - started > timedelta(hours=2):
            return Check(label, "warn", f"Empezó el {_when(started, now)} y no terminó.")
        return Check(label, "none", "En curso.")
    late = task.tolerance_hours is not None and now - run.finished_at > timedelta(
        hours=task.tolerance_hours
    )
    text = f"{'Atrasada: última' if late else 'Corrió'} {_when(run.finished_at, now)}."
    if run.summary:
        text += f" {run.summary}."
    return Check(label, "warn" if late else "ok", text)


def _task_checks(backups: dict, failures: dict) -> list[Check]:
    now = timezone.now()
    runs = {r.name: r for r in TaskRun.objects.all()}  # una sola consulta
    return [_task_check(task, runs, failures, backups, now) for task in EXPECTED]


def server_status() -> dict:
    """Todo el bloque «Servidor»: grupos de filas y cuántos avisos (!) hay en total."""
    scratch: dict = {}

    def shared(name, fn):
        """Lee una vez lo que usan varias filas; si falla, esa fila dirá «No se pudo comprobar»."""
        if name not in scratch:
            scratch[name] = fn()
        return scratch[name]

    def failures():
        return shared("failures", task_failures)

    def backups():
        return shared("backups", latest_backups)

    groups = [
        (
            "Salud",
            [
                _safe("Base de datos", _database_checks),
                _safe("Archivos privados", _storage_checks),
                _safe("Límite de intentos", _cache_checks),
                _safe("Nala", _nala_checks),
            ],
        ),
        (
            "Respaldo",
            [
                _safe(
                    "Último respaldo",
                    lambda: _backup_checks(backups(), _failures_or_empty(failures)),
                )
            ],
        ),
        ("Tareas", [_safe("Tareas programadas", lambda: _task_checks(backups(), failures()))]),
        ("Versión", [_safe("Versión instalada", _version_checks)]),
        ("Puerta pública", [_safe("Puerta pública", _public_door_checks)]),
        ("Cursos privados", [_safe("Cursos privados", _courses_checks)]),
    ]
    flat = [
        {"label": label, "checks": [c for part in parts for c in part]} for label, parts in groups
    ]
    warnings = sum(1 for g in flat for c in g["checks"] if c.state == "warn" and c.counts)
    return {"groups": flat, "warnings": warnings}


def _failures_or_empty(getter) -> dict:
    """Los avisos de fallo son un extra de la fila del respaldo: si no se pueden leer, la fila sigue."""
    try:
        return getter()
    except Exception:  # noqa: BLE001
        return {}


def server_card(status: dict) -> Card:
    n = status["warnings"]
    url = reverse("core:admin_center") + "#servidor"
    if n == 0:
        return Card(
            "server",
            "✓",
            "servidor: todo en orden",
            "Salud, respaldo y versión al día.",
            url,
            False,
        )
    return Card(
        "server",
        str(n),
        _plural(n, "aviso del servidor", "avisos del servidor"),
        "Mira el detalle en Servidor.",
        url,
        True,
    )


def personal_link(person, by) -> str:
    """Enlace personal de registro o restablecimiento: se devuelve para mostrarlo una vez, nunca se guarda."""
    return onboarding.create_signup_link(person, by)
