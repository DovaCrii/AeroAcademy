"""Incorporación del equipo: alta masiva con CSV, lista de invitación y cambios de área o rol.

Toda la lógica vive aquí; la vista de `team` y el comando `importar_equipo` solo la llaman.
La aprobación sigue siendo de `accounts.services.grant_access`.
"""

import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts import services as accounts
from apps.accounts.models import Person, PersonStatus
from apps.catalog.models import Discipline
from apps.community import moderation
from apps.community.models import Post, Thread
from apps.credentials.models import Credential
from apps.progress.models import MilestoneCheck

from .models import TeamMember

MAX_ROWS = 500
MAX_BYTES = 200_000
DEFAULT_URL = "https://aeroacademy.tailccd107.ts.net"
EMAIL_RE = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$")

ROLE_ALIASES = {
    "": "",
    "member": "member",
    "miembro": "member",
    "lead": "lead",
    "responsable": "lead",
    "lider": "lead",
    "admin": "admin",
    "administrador": "admin",
    "administradora": "admin",
}
ROLE_LABELS = {"member": "Miembro", "lead": "Responsable", "admin": "Admin"}
HEADER_ALIASES = {
    "login": "email",
    "correo": "email",
    "email": "email",
    "e-mail": "email",
    "mail": "email",
    "nombre": "name",
    "name": "name",
    "rol": "role",
    "role": "role",
    "area": "disciplines",
    "area/disciplina": "disciplines",
    "area / disciplina": "disciplines",
    "disciplina": "disciplines",
    "disciplinas": "disciplines",
    "cargo": "job",
    "puesto": "job",
}
TEMPLATE_CSV = (
    "correo,nombre,rol,área/disciplina,cargo\n"
    "ana@empresa.cl,Ana Pérez,member,Topografía,Topógrafa\n"
    'luis@empresa.cl,Luis Soto,lead,Arquitectura | Civil-Estructural,"Coordinador BIM"\n'
)


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).strip().casefold()


# --- lectura del CSV ----------------------------------------------------------------------------------------------


@dataclass
class RowResult:
    line: int
    login: str = ""
    name: str = ""
    role: str = ""  # el pedido (vacío = no cambia)
    disciplines: list[str] = field(default_factory=list)  # slugs
    job: str = ""
    action: str = ""  # created | updated | unchanged | error
    changes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self):
        return not self.errors


@dataclass
class ImportReport:
    rows: list[RowResult] = field(default_factory=list)
    dry_run: bool = False
    fatal: str = ""

    def count(self, action):
        return sum(1 for r in self.rows if r.action == action)

    @property
    def count_created(self):
        return self.count("created")

    @property
    def count_updated(self):
        return self.count("updated")

    @property
    def errors(self):
        return [r for r in self.rows if r.errors]


def _read_rows(text: str):
    """Devuelve (filas como dict normalizado con su número de línea, error fatal)."""
    text = (text or "").lstrip("﻿")
    if len(text.encode("utf-8")) > MAX_BYTES:
        return [], "El archivo es demasiado grande (máximo 200 KB)."
    if not text.strip():
        return [], "El archivo está vacío."
    first = text.splitlines()[0]
    delimiter = ";" if first.count(";") > first.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration:
        return [], "El archivo está vacío."
    columns = [HEADER_ALIASES.get(_fold(h)) for h in header]
    if "email" not in columns:
        return [], "Falta la columna «correo» en la primera fila."
    rows = []
    try:
        for raw in reader:
            if not any(c.strip() for c in raw):
                continue
            rows.append(
                (reader.line_num, dict(zip(columns, (c.strip() for c in raw), strict=False)))
            )
    except csv.Error as exc:
        return [], f"CSV mal formado: {exc}"
    if len(rows) > MAX_ROWS:
        return [], f"Demasiadas filas ({len(rows)}); el máximo es {MAX_ROWS} por archivo."
    return rows, ""


def _discipline_map():
    out = {}
    for d in Discipline.objects.all():
        out[_fold(d.slug)] = d.slug
        out[_fold(d.name)] = d.slug
    return out


def _role_of(person: Person) -> str:
    if person.is_superuser:
        return "admin"
    return "lead" if any(g.name == "lead" for g in person.groups.all()) else "member"


def _parse(line, data, disc_map) -> RowResult:
    r = RowResult(line=line)
    r.login = accounts.normalize_login(data.get("email", ""))
    if not r.login:
        r.errors.append("Falta el correo.")
    elif not EMAIL_RE.match(r.login) or len(r.login) > 254:
        r.errors.append(f"Correo no válido: «{r.login}».")
    r.name = data.get("name", "")[:150]
    r.job = data.get("job", "")[:120]
    raw_role = _fold(data.get("role", ""))
    if raw_role not in ROLE_ALIASES:
        r.errors.append(f"Rol desconocido: «{data.get('role', '')}» (usa member, lead o admin).")
    else:
        r.role = ROLE_ALIASES[raw_role]
    for part in re.split(r"[|;+]", data.get("disciplines", "")):
        if not part.strip():
            continue
        slug = disc_map.get(_fold(part))
        if slug is None:
            known = ", ".join(sorted({s for s in disc_map.values()}))
            r.errors.append(f"Disciplina desconocida: «{part.strip()}» (disponibles: {known}).")
        elif slug not in r.disciplines:
            r.disciplines.append(slug)
    return r


# --- alta masiva ------------------------------------------------------------------------------------------------------


def import_team(text: str, by: Person | None = None, dry_run: bool = False) -> ImportReport:
    """Pre-aprueba a las personas del CSV. Idempotente: repetirlo actualiza, nunca duplica.
    Con `dry_run` calcula y valida todo igual, pero no escribe nada."""
    report = ImportReport(dry_run=dry_run)
    rows, fatal = _read_rows(text)
    if fatal:
        report.fatal = fatal
        return report
    disc_map = _discipline_map()
    parsed = [_parse(line, data, disc_map) for line, data in rows]
    existing = {
        p.login: p
        for p in Person.objects.filter(
            login__in=[r.login for r in parsed if r.login]
        ).prefetch_related("groups", "disciplines")
    }
    seen = {}
    for r in parsed:
        if r.login and r.login in seen:
            r.errors.append(
                f"Correo repetido en el archivo (ya estaba en la línea {seen[r.login]})."
            )
        elif r.login:
            seen[r.login] = r.line
        person = existing.get(r.login)
        if person is not None and not r.errors:
            _check_existing(r, person, by)
        elif person is None and r.role in ("lead", "admin") and by is not None and not by.is_admin:
            r.errors.append("Solo un admin puede dar el rol lead o admin.")
        if r.errors:
            r.action = "error"
        else:
            _plan_and_apply(r, person, by, dry_run)
        report.rows.append(r)
    return report


def _check_existing(r: RowResult, person: Person, by):
    if person.status == PersonStatus.SUSPENDED:
        r.errors.append("Está suspendida: reactívala desde el admin, no por importación.")
        return
    current = _role_of(person)
    wanted = r.role or current
    if by is not None and not by.is_admin and (current != "member" or wanted != "member"):
        r.errors.append("Solo un admin puede tocar a un lead o admin, o dar ese rol.")


def _plan_and_apply(r: RowResult, person: Person | None, by, dry_run: bool):
    wanted_role = r.role or (_role_of(person) if person else "member")
    if person is None:
        r.action = "created"
        r.changes = ["alta", f"rol {wanted_role}"]
        if r.disciplines:
            r.changes.append("disciplinas")
    else:
        if person.status != PersonStatus.APPROVED:
            r.changes.append("aprobada")
        if wanted_role != _role_of(person):
            r.changes.append(f"rol {wanted_role}")
        if r.name and r.name != person.display_name:
            r.changes.append("nombre")
        if r.job and r.job != person.role_title:
            r.changes.append("cargo")
        if r.disciplines and set(r.disciplines) != {d.slug for d in person.disciplines.all()}:
            r.changes.append("disciplinas")
        r.action = "updated" if r.changes else "unchanged"
    if dry_run or r.action == "unchanged":
        return
    with transaction.atomic():
        person, _created = accounts.grant_access(r.login, wanted_role)
        fields = []
        if r.name and r.name != person.display_name:
            person.display_name = r.name
            fields.append("display_name")
        if r.job and r.job != person.role_title:
            person.role_title = r.job
            fields.append("role_title")
        if fields:
            person.save(update_fields=[*fields, "updated_at"])
        if r.disciplines:
            person.disciplines.set(Discipline.objects.filter(slug__in=r.disciplines))
        TeamMember.objects.get_or_create(person=person)
        if by is not None:
            moderation.log(by, "import_person", person, f"{r.action}: {', '.join(r.changes)}")


# --- lista de incorporación --------------------------------------------------------------------------------------------

STEP_LABELS = ["hoja", "misión", "certificado", "foro"]


def _first_steps_done(ids):
    """{person_id: cantidad de primeros pasos hechos (0-4)}, en cuatro consultas para todas las personas."""
    sheet = set(
        Person.objects.filter(pk__in=ids)
        .filter(~Q(headline="") | ~Q(character_class=""))
        .values_list("pk", flat=True)
    )
    mission = set(MilestoneCheck.objects.filter(person__in=ids).values_list("person_id", flat=True))
    cert = set(Credential.objects.filter(owner__in=ids).values_list("owner_id", flat=True))
    forum = set(Thread.objects.filter(author__in=ids).values_list("author_id", flat=True)) | set(
        Post.objects.filter(author__in=ids).values_list("author_id", flat=True)
    )
    return {pk: sum(pk in s for s in (sheet, mission, cert, forum)) for pk in ids}


def roster(with_steps=True):
    """Todas las personas no suspendidas con su estado de incorporación (consultas constantes)."""
    people = list(
        Person.objects.exclude(status=PersonStatus.SUSPENDED)
        .select_related("team_member")
        .prefetch_related("disciplines", "groups")
        .order_by("display_name", "login")
    )
    steps = (
        _first_steps_done([p.pk for p in people])
        if with_steps
        else dict.fromkeys([p.pk for p in people], 0)
    )
    rows = []
    for p in people:
        tm = getattr(p, "team_member", None)
        rows.append(
            {
                "person": p,
                "role": _role_of(p),
                "role_label": ROLE_LABELS[_role_of(p)],
                "disciplines": sorted(p.disciplines.all(), key=lambda d: (d.order, d.name)),
                "invited": bool(tm and tm.tailscale_invited),
                "approved": p.status == PersonStatus.APPROVED,
                "entered": p.last_login is not None,
                "steps": steps[p.pk],
                "steps_done": steps[p.pk] == len(STEP_LABELS),
                "invitation": invitation_text(p),
            }
        )
    return rows


def groups_by_area(rows):
    """Agrupa por la primera disciplina de cada persona (la de menor orden); sin disciplina, al final."""
    order, groups = [], {}
    for row in rows:
        d = row["disciplines"][0] if row["disciplines"] else None
        key = d.slug if d else ""
        if key not in groups:
            groups[key] = {"discipline": d, "name": d.name if d else "Sin área", "rows": []}
            order.append(key)
        groups[key]["rows"].append(row)
    ordered = sorted(
        groups.values(),
        key=lambda g: (g["discipline"] is None, g["discipline"].order if g["discipline"] else 0),
    )
    return ordered


@transaction.atomic
def set_invited(person: Person, by: Person, invited: bool) -> TeamMember:
    """Marca (o desmarca) a mano que la persona ya fue invitada a Tailscale. Idempotente."""
    _require_lead(by)
    tm, _ = TeamMember.objects.get_or_create(person=person)
    if tm.tailscale_invited != invited:
        tm.tailscale_invited = invited
        tm.invited_at = timezone.now() if invited else None
        tm.invited_by = by if invited else None
        tm.save()
        moderation.log(by, "invite_mark" if invited else "invite_unmark", person, person.name)
    return tm


def _require_lead(by):
    if not by.is_lead:
        raise PermissionError("Solo un responsable puede gestionar al equipo.")


@transaction.atomic
def update_person(person: Person, by: Person, *, role="", discipline_slugs=None, job=None):
    """Cambia rol, disciplinas o cargo desde la interfaz. Un lead solo toca a miembros y no da roles altos."""
    _require_lead(by)
    current = _role_of(person)
    if not by.is_admin and current != "member":
        raise PermissionError("Solo un admin puede cambiar a un lead o admin.")
    changes = []
    if role and role != current:
        if role not in accounts.ROLES:
            raise ValueError("Rol desconocido.")
        if not by.is_admin:
            raise PermissionError("Solo un admin puede dar el rol lead o admin.")
        if person.pk == by.pk:
            raise PermissionError("No puedes cambiar tu propio rol.")
        if accounts.is_bootstrap_admin(person.login):
            raise PermissionError("Esa persona es admin fija (BOOTSTRAP_ADMINS).")
        accounts.set_role(person, role)
        changes.append(f"rol {role}")
    if job is not None and job.strip()[:120] != person.role_title:
        person.role_title = job.strip()[:120]
        person.save(update_fields=["role_title", "updated_at"])
        changes.append("cargo")
    if discipline_slugs is not None:
        wanted = set(
            Discipline.objects.filter(slug__in=discipline_slugs).values_list("slug", flat=True)
        )
        if wanted != {d.slug for d in person.disciplines.all()}:
            person.disciplines.set(Discipline.objects.filter(slug__in=wanted))
            changes.append("disciplinas")
    if changes:
        moderation.log(by, "update_person", person, ", ".join(changes))
    return changes


# --- texto de invitación -----------------------------------------------------------------------------------------------


def academy_url() -> str:
    return getattr(settings, "ACADEMY_URL", DEFAULT_URL).rstrip("/")


def invitation_text(person: Person | None = None) -> str:
    """Mensaje listo para copiar. No lleva claves ni tokens: solo la dirección y los pasos."""
    url = academy_url()
    hello = f"Hola {person.name}," if person is not None else "Hola,"
    who = (
        f" (con el correo {person.login})"
        if person is not None
        else " (con el correo que te indicaron)"
    )
    return (
        f"{hello}\n\n"
        "Te sumamos a AeroAcademy, la academia interna del equipo. Para entrar:\n\n"
        "1. Revisa tu correo: te llegó una invitación a nuestra red de Tailscale. Acéptala.\n"
        "2. Instala Tailscale desde https://tailscale.com/download e inicia sesión"
        f"{who}.\n"
        f"3. Con Tailscale conectado, abre {url} en el navegador. Quedas dentro sin contraseña.\n"
        "4. Para tenerla como app: en Chrome o Edge, menú (⋮) → Instalar AeroAcademy; en el celular, "
        "«Agregar a pantalla de inicio».\n"
        "5. En la portada sigue los «Primeros pasos»: completa tu hoja de personaje y preséntate en el foro.\n\n"
        "Si algo no abre, revisa que Tailscale esté conectado y escríbenos."
    )


def board_areas():
    """Personas aprobadas agrupadas por área para el tablero: solo dos consultas, sin correos ni estados."""
    people = Person.objects.filter(status=PersonStatus.APPROVED, is_active=True).prefetch_related(
        "disciplines"
    )
    rows = [
        {"person": p, "disciplines": sorted(p.disciplines.all(), key=lambda d: (d.order, d.name))}
        for p in people.order_by("display_name", "login")
    ]
    return groups_by_area(rows)
