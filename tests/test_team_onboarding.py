import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accounts.models import Person, PersonStatus
from apps.catalog.models import Discipline
from apps.community.models import ModerationLog
from apps.team import onboarding
from apps.team.models import TeamMember

CSV = (
    "correo,nombre,rol,área/disciplina,cargo\n"
    "Ana@Empresa.cl,Ana Pérez,member,Topografía,Topógrafa\n"
    "luis@empresa.cl,Luis Soto,lead,Arquitectura | Civil-Estructural,Coordinador BIM\n"
)


@pytest.fixture
def disciplines(db):
    for i, (slug, name, world) in enumerate(
        [
            ("arquitectura", "Arquitectura", "architecture"),
            ("civil-estructural", "Civil-Estructural", "civil"),
            ("topografia", "Topografía", "survey"),
            ("captura-rpa", "Captura / RPA", "aero"),
        ]
    ):
        Discipline.objects.create(slug=slug, name=name, default_world=world, order=i)


def test_import_creates_preapproved_people(disciplines, admin_person):
    report = onboarding.import_team(CSV, by=admin_person)
    assert [r.action for r in report.rows] == ["created", "created"]
    ana = Person.objects.get(login="ana@empresa.cl")
    assert ana.status == PersonStatus.APPROVED
    assert ana.display_name == "Ana Pérez" and ana.role_title == "Topógrafa"
    assert ana.role == "member"
    assert [d.slug for d in ana.disciplines.all()] == ["topografia"]
    luis = Person.objects.get(login="luis@empresa.cl")
    assert luis.role == "lead"
    assert {d.slug for d in luis.disciplines.all()} == {"arquitectura", "civil-estructural"}
    assert ModerationLog.objects.filter(action="import_person").count() == 2


def test_import_is_idempotent_and_updates(disciplines, admin_person):
    onboarding.import_team(CSV, by=admin_person)
    again = onboarding.import_team(CSV, by=admin_person)
    assert [r.action for r in again.rows] == ["unchanged", "unchanged"]
    assert Person.objects.filter(login__endswith="@empresa.cl").count() == 2
    changed = CSV.replace("Topógrafa", "Jefa de Topografía")
    report = onboarding.import_team(changed, by=admin_person)
    assert [r.action for r in report.rows] == ["updated", "unchanged"]
    assert Person.objects.get(login="ana@empresa.cl").role_title == "Jefa de Topografía"
    assert Person.objects.filter(login__endswith="@empresa.cl").count() == 2


def test_import_approves_an_existing_pending_person(disciplines, admin_person, make_person):
    pend = make_person("ana@empresa.cl", status="pending")
    onboarding.import_team(CSV, by=admin_person)
    pend.refresh_from_db()
    assert pend.status == PersonStatus.APPROVED
    assert Person.objects.filter(login="ana@empresa.cl").count() == 1


def test_dry_run_changes_nothing(disciplines, admin_person):
    before = (Person.objects.count(), ModerationLog.objects.count(), TeamMember.objects.count())
    report = onboarding.import_team(CSV, by=admin_person, dry_run=True)
    assert [r.action for r in report.rows] == ["created", "created"]
    assert (
        Person.objects.count(),
        ModerationLog.objects.count(),
        TeamMember.objects.count(),
    ) == before


def test_invalid_rows_are_reported_and_valid_ones_apply(disciplines, admin_person):
    text = (
        "correo,nombre,rol,área/disciplina,cargo\n"
        "no-es-correo,X,member,,\n"
        "bien@empresa.cl,Bien,member,Topografía,\n"
        "rol@empresa.cl,Rol,jefazo,,\n"
        "disc@empresa.cl,Disc,member,Astrología,\n"
        "BIEN@empresa.cl,Otra,member,,\n"
    )
    report = onboarding.import_team(text, by=admin_person)
    actions = [r.action for r in report.rows]
    assert actions == ["error", "created", "error", "error", "error"]
    assert "Correo no válido" in report.rows[0].errors[0]
    assert "Rol desconocido" in report.rows[2].errors[0]
    assert "Disciplina desconocida" in report.rows[3].errors[0]
    assert "repetido" in report.rows[4].errors[0]
    assert Person.objects.filter(login="bien@empresa.cl").exists()
    assert not Person.objects.filter(login="rol@empresa.cl").exists()


def test_missing_email_column_and_semicolon_delimiter(disciplines, admin_person):
    assert onboarding.import_team("nombre,rol\nA,member\n", by=admin_person).fatal
    ok = onboarding.import_team("correo;nombre;rol\nz@empresa.cl;Zoe;member\n", by=admin_person)
    assert ok.rows[0].action == "created"


def test_lead_cannot_import_people_at_all(disciplines, lead, make_person):
    """D34: agregar personas es solo del admin."""
    report = onboarding.import_team(CSV, by=lead)
    assert report.fatal and not report.rows
    assert not Person.objects.filter(login__endswith="@empresa.cl").exists()


def test_suspended_person_is_not_reactivated_by_import(disciplines, admin_person, make_person):
    sus = make_person("ana@empresa.cl", status="suspended")
    report = onboarding.import_team(CSV, by=admin_person)
    assert report.rows[0].action == "error"
    sus.refresh_from_db()
    assert sus.status == PersonStatus.SUSPENDED


def test_management_command(disciplines, tmp_path, capsys):
    f = tmp_path / "equipo.csv"
    f.write_text(CSV, encoding="utf-8")
    call_command("importar_equipo", str(f), "--dry-run")
    assert Person.objects.count() == 0
    call_command("importar_equipo", str(f))
    assert Person.objects.filter(login__endswith="@empresa.cl").count() == 2
    call_command("importar_equipo", str(f))
    assert Person.objects.filter(login__endswith="@empresa.cl").count() == 2
    bad = tmp_path / "mal.csv"
    bad.write_text("correo,rol\nx@empresa.cl,zzz\n", encoding="utf-8")
    with pytest.raises(CommandError):
        call_command("importar_equipo", str(bad))
    with pytest.raises(CommandError):
        call_command("importar_equipo", str(tmp_path / "no-existe.csv"))


# --- vistas ------------------------------------------------------------------------------------------------------


def test_members_cannot_access_management(member_client, member):
    for url in ("/equipo/personas/", "/equipo/personas/agregar/"):
        assert member_client.get(url).status_code == 403
    assert (
        member_client.post(
            "/equipo/personas/agregar/", {"csv": CSV, "action": "import"}
        ).status_code
        == 403
    )
    assert (
        member_client.post(f"/equipo/personas/{member.pk}/", {"role": "admin"}).status_code == 403
    )
    assert (
        member_client.post(f"/equipo/personas/{member.pk}/invitada/", {"invited": "1"}).status_code
        == 403
    )
    assert not Person.objects.filter(login__endswith="@empresa.cl").exists()
    assert not TeamMember.objects.exists()


def test_member_sees_areas_but_no_management_links(
    disciplines, member, member_client, admin_person
):
    onboarding.import_team(CSV, by=admin_person)
    html = member_client.get("/equipo/").content.decode()
    assert "Personas por área" in html and "Topógrafa" in html
    assert "Gestionar personas" not in html
    assert "ana@empresa.cl" not in html  # el correo no se muestra a los miembros


def test_admin_imports_from_ui_with_dry_run_then_real(disciplines, admin_person, client_for):
    c = client_for(admin_person.login)
    r = c.post("/equipo/personas/agregar/", {"csv": CSV, "action": "dry"})
    assert r.status_code == 200 and "No se escribió nada" in r.content.decode()
    assert not Person.objects.filter(login="ana@empresa.cl").exists()
    c.post("/equipo/personas/agregar/", {"csv": CSV, "action": "import"})
    assert Person.objects.filter(login="ana@empresa.cl").exists()
    assert Person.objects.filter(login="luis@empresa.cl").exists()  # el admin sí da lead


def test_csrf_is_enforced_on_changes(disciplines, admin_person, member):
    from django.test import Client

    c = Client(
        enforce_csrf_checks=True,
        REMOTE_ADDR="127.0.0.1",
        HTTP_TAILSCALE_USER_LOGIN=admin_person.login,
    )
    assert c.post(f"/equipo/personas/{member.pk}/", {"role": "lead"}).status_code == 403
    member.refresh_from_db()
    assert member.role == "member"


def test_lead_updates_discipline_and_job_with_audit(disciplines, lead, member, client_for):
    c = client_for(lead.login)
    c.post(f"/equipo/personas/{member.pk}/", {"job": "Topógrafa", "disciplines": ["topografia"]})
    member.refresh_from_db()
    assert member.role_title == "Topógrafa"
    assert [d.slug for d in member.disciplines.all()] == ["topografia"]
    assert ModerationLog.objects.filter(action="update_person", object_id=member.pk).count() == 1
    c.post(f"/equipo/personas/{member.pk}/", {"role": "lead"})  # un lead no sube roles
    member.refresh_from_db()
    assert member.role == "member"


def test_admin_changes_role_but_not_own_or_bootstrap(
    disciplines, admin_person, member, client_for, settings
):
    c = client_for(admin_person.login)
    c.post(f"/equipo/personas/{member.pk}/", {"role": "lead"})
    member.refresh_from_db()
    assert member.role == "lead"
    c.post(f"/equipo/personas/{admin_person.pk}/", {"role": "member"})
    admin_person.refresh_from_db()
    assert admin_person.role == "admin"
    settings.BOOTSTRAP_ADMINS = ["ana@lev.cl"]
    c.post(f"/equipo/personas/{member.pk}/", {"role": "member"})  # member = ana, pero ahora lead
    member.refresh_from_db()
    assert member.role == "lead"


def test_invited_mark_is_manual_and_idempotent(lead, member, client_for):
    c = client_for(lead.login)
    c.post(f"/equipo/personas/{member.pk}/invitada/", {"invited": "1"})
    c.post(f"/equipo/personas/{member.pk}/invitada/", {"invited": "1"})
    tm = TeamMember.objects.get(person=member)
    assert tm.tailscale_invited and tm.invited_by == lead and tm.invited_at
    assert ModerationLog.objects.filter(action="invite_mark").count() == 1
    row = next(r for r in onboarding.roster() if r["person"].pk == member.pk)
    assert row["invited"] and row["approved"] and not row["entered"] and row["steps"] == 0
    c.post(f"/equipo/personas/{member.pk}/invitada/", {"invited": "0"})
    assert not TeamMember.objects.get(person=member).tailscale_invited


def test_roster_flags_entered_and_first_steps(member, lead):
    from django.utils import timezone

    member.last_login = timezone.now()
    member.headline = "Topógrafa"
    member.save(update_fields=["last_login", "headline"])
    row = next(r for r in onboarding.roster() if r["person"].pk == member.pk)
    assert row["entered"] and row["steps"] == 1 and not row["steps_done"]


def test_invitation_text_has_url_and_steps_but_no_secrets(member, settings):
    settings.SECRET_KEY = "super-secreto-de-prueba-123"
    settings.NIM_API_KEY = "nvapi-clave-de-prueba"
    text = onboarding.invitation_text(member)
    assert "https://aeroacademy.tailccd107.ts.net" in text
    assert "tailscale.com/download" in text and member.login in text
    for secret in ("super-secreto-de-prueba-123", "nvapi-clave-de-prueba", "token", "contraseña:"):
        assert secret not in text.lower().replace("sin contraseña", "")
    assert "password" not in text.lower()


def test_people_page_escapes_text_and_queries_are_bounded(
    disciplines, lead, make_person, client_for
):
    c = client_for(lead.login)
    for i in range(3):
        make_person(f"p{i}@lev.cl")
    c.get("/equipo/personas/")
    with CaptureQueriesContext(connection) as few:
        c.get("/equipo/personas/")
    xss = make_person("x@lev.cl")
    xss.display_name = "<script>alert(1)</script>"
    xss.role_title = "<b>x</b>"
    xss.save()
    for i in range(10):
        make_person(f"q{i}@lev.cl")
    with CaptureQueriesContext(connection) as many:
        html = c.get("/equipo/personas/").content.decode()
    assert len(many) <= len(few) + 1
    assert "<script>alert(1)" not in html
    assert "&lt;script&gt;" in html


def test_simple_mode_accepts_only_emails_one_per_line_or_separated(db):
    """Pedido del dueño: «tengo los mails; ellos se crean sus cuentas y se van editando»."""
    from apps.accounts.models import Person, PersonStatus
    from apps.team import onboarding

    text = "uno.persona@empresa.cl\ndos.persona@empresa.cl, tres.persona@empresa.cl\n\n"
    report = onboarding.import_team(text, dry_run=True)
    assert (
        not report.fatal
        and len(report.rows) == 3
        and not Person.objects.filter(login__endswith="@empresa.cl").exists()
    )
    report = onboarding.import_team(text)
    people = Person.objects.filter(login__endswith="@empresa.cl")
    assert people.count() == 3 and all(
        p.status == PersonStatus.APPROVED and p.role == "member" for p in people
    )
    assert onboarding.import_team(text).count_created == 0  # repetir no duplica


def test_simple_mode_reports_bad_emails(db):
    from apps.team import onboarding

    report = onboarding.import_team("bien@empresa.cl\nmal@\n")
    assert len(report.errors) == 1
