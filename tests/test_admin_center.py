"""Centro de administración (D42), P0-1: acceso, situación, enlaces y privacidad de la pantalla."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.core.cache import cache
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts import team_link
from apps.accounts.models import Person
from apps.community.models import Report
from apps.core import admin_center
from apps.credentials.models import Credential
from tests.conftest import own_queries, tailscale_client

pytestmark = pytest.mark.django_db
GOOD = "Clave-de-prueba-9271!"  # valor de prueba generado para esta suite
URL = "/administracion/"


@pytest.fixture(autouse=True)
def _clean_cache(monkeypatch):
    cache.clear()
    monkeypatch.setattr(
        admin_center, "public_door_up", lambda: False
    )  # sin sonda de red en estas pruebas
    yield
    cache.clear()


def password_client(person, raw=GOOD):
    person.set_password(raw)
    person.save(update_fields=["password"])
    client = Client(REMOTE_ADDR="127.0.0.1")
    assert client.post("/entrar/", {"email": person.login, "password": raw}).status_code == 302
    return client


def body(response):
    """Solo el contenido de la página (la campana y Nala salen en todas)."""
    return response.content.decode().split("<main")[1]


def grow(n, make_person, owner):
    """`n` personas pendientes, `n` reportes y `n` credenciales (por revisar y por vencer)."""
    today = timezone.localdate()
    for i in range(n):
        make_person(f"nueva{i}-{Person.objects.count()}@example.com", status="pending")
        Report.objects.create(reporter=owner, target_type="post", target_id=i + 1, reason="r")
        Credential.objects.create(
            owner=owner, title=f"C{i}", status="pending", file=f"x/{i}.pdf", file_kind="pdf"
        )
        Credential.objects.create(
            owner=owner,
            title=f"V{i}",
            status="verified",
            expires_on=today + timedelta(days=5),
            file=f"x/v{i}.pdf",
            file_kind="pdf",
        )


# --- acceso ------------------------------------------------------------------------------------------------------


def test_admin_and_lead_enter_member_gets_404(admin_person, lead, member):
    assert tailscale_client(admin_person.login).get(URL).status_code == 200
    assert tailscale_client(lead.login).get(URL).status_code == 200
    response = tailscale_client(member.login).get(URL)
    assert response.status_code == 404
    assert "Centro de administración" not in response.content.decode().split("<main")[1]


def test_anonymous_pending_and_suspended_never_see_the_center(make_person):
    anon = Client(REMOTE_ADDR="127.0.0.1")
    response = anon.get(URL)
    assert response.status_code == 302 and "/bienvenida/" in response["Location"]
    pending = make_person("espera@example.com", status="pending")
    response = tailscale_client(pending.login).get(URL)
    assert response.status_code == 302 and "/espera/" in response["Location"]
    suspended = make_person("fuera@example.com", status="suspended", role="admin")
    response = tailscale_client(suspended.login).get(URL)
    assert response.status_code == 403
    assert "Centro de administración" not in body(response)


def test_the_public_door_hides_the_center_even_from_an_admin(admin_person, settings):
    assert "/administracion/" in settings.PUBLIC_BLOCKED_PREFIXES
    client = password_client(admin_person)
    assert client.get(URL).status_code == 200
    settings.PUBLIC_DOOR = True
    settings.PUBLIC_REQUIRE_SECOND_FACTOR = False
    for path in (URL, URL + "cuentas/", URL + "bitacora/", URL + "cuentas/1/suspender/"):
        assert client.get(path).status_code == 404, path
    assert client.post(URL + "cuentas/1/suspender/").status_code == 404
    assert client.post(URL + "enlace-equipo/").status_code == 404


def test_access_is_a_second_lock_on_the_public_door(admin_person, settings):
    """Aunque el prefijo dejara de estar bloqueado, la propia comprobación dice que no."""
    assert admin_center.access(admin_person, SimpleNamespace(public_door=False)) == "admin"
    assert admin_center.access(admin_person, SimpleNamespace(public_door=True)) is None
    settings.PUBLIC_DOOR = True
    assert admin_center.access(admin_person, SimpleNamespace()) is None


def test_lead_sees_only_his_queues(lead, admin_person, make_person):
    make_person("espera@example.com", status="pending")
    admin_html = body(tailscale_client(admin_person.login).get(URL))
    lead_html = body(tailscale_client(lead.login).get(URL))
    assert "Enlace del equipo" in admin_html and "Cuentas</h2>" in admin_html
    assert "esperando aprobación" in admin_html and "Administración técnica avanzada" in admin_html
    for hidden in (
        "Enlace del equipo",
        "Cuentas</h2>",
        "esperando aprobación",
        "Administración técnica avanzada",
        "vencen en 30 días",
        "Agregar personas",
    ):
        assert hidden not in lead_html
    assert "reporte" in lead_html and "certificado" in lead_html
    assert "Moderación" in lead_html and "Vencimientos del equipo" in lead_html


# --- situación -----------------------------------------------------------------------------------------------------


def test_the_cards_count_and_link_to_where_it_is_solved(admin_person, member, make_person):
    today = timezone.localdate()
    make_person("espera@example.com", status="pending")
    make_person("espera2@example.com", status="pending")
    Report.objects.create(reporter=member, target_type="post", target_id=1, reason="x")
    Credential.objects.create(owner=member, title="A", status="pending", file="a.pdf")
    Credential.objects.create(
        owner=member,
        title="B",
        status="verified",
        expires_on=today + timedelta(days=20),
        file="b.pdf",
    )
    Credential.objects.create(  # a 45 días: avisa la campana (60) pero no entra al contador urgente (30)
        owner=member,
        title="C",
        status="verified",
        expires_on=today + timedelta(days=45),
        file="c.pdf",
    )
    Credential.objects.create(
        owner=member,
        title="D",
        status="verified",
        expires_on=today - timedelta(days=2),
        file="d.pdf",
    )
    cards = {c.key: c for c in admin_center.situation("admin", link=None)}
    assert cards["pending"].value == "2" and cards["pending"].warn
    assert cards["pending"].url == "/administracion/cuentas/?estado=pendiente"
    assert cards["reports"].value == "1" and cards["reports"].url == "/moderacion/#m-reports"
    assert cards["review"].value == "1" and cards["review"].url == "/certificados/revisar/"
    assert cards["expiring"].value == "1" and "1 ya vencida" in cards["expiring"].hint
    assert cards["expiring"].url == "/certificados/vencimientos/?equipo=1"
    html = body(tailscale_client(admin_person.login).get(URL))
    assert 'href="/certificados/revisar/"' in html and 'href="/moderacion/#m-reports"' in html


def test_zero_counters_say_nothing_pending(admin_person):
    html = body(tailscale_client(admin_person.login).get(URL))
    assert html.count("Nada pendiente") >= 4
    cards = admin_center.situation("admin", link=None)
    assert not any(c.warn for c in cards if c.key != "team_link")


def test_team_link_card_shows_days_and_uses_never_the_token(admin_person):
    url = team_link.generate(admin_person, 14)
    token = url.rsplit("/inscripcion/", 1)[1].strip("/")
    html = body(tailscale_client(admin_person.login).get(URL))
    assert "inscripciones hasta ahora" in html or "inscripción hasta ahora" in html
    assert token not in html and "/inscripcion/" not in html


# --- consultas acotadas ----------------------------------------------------------------------------------------


# La cabecera de toda página (sesión, persona, anillo de XP, campana) cuesta unas 10 consultas que no son del Centro.


def measure(client, url=URL):
    """(consultas totales, consultas propias del Centro: sin las de la cabecera de toda página)."""
    with CaptureQueriesContext(connection) as ctx:
        assert client.get(url).status_code == 200
    own = own_queries(ctx.captured_queries)
    return len(ctx), len(own)


def test_the_center_queries_do_not_grow_with_the_data(admin_person, member, make_person):
    client = tailscale_client(admin_person.login)
    client.get(URL)  # abre la sesión
    grow(1, make_person, member)
    small = measure(client)
    grow(40, make_person, member)
    large = measure(client)
    assert small == large  # no crece con los datos
    assert large[1] <= 12  # y el Centro mismo cabe en el presupuesto (la cabecera pone el resto)


def test_the_lead_view_is_also_constant(lead, member, make_person):
    client = tailscale_client(lead.login)
    client.get(URL)
    grow(1, make_person, member)
    small = measure(client)
    grow(40, make_person, member)
    assert measure(client) == small


# --- privacidad y escape ------------------------------------------------------------------------------------------


def test_the_center_shows_no_emails_secrets_or_server_paths(admin_person, member, make_person):
    pending = make_person("secreta.persona@example.com", status="pending")
    team_link.generate(admin_person, 7)
    main = body(tailscale_client(admin_person.login).get(URL))
    assert pending.login not in main and member.login not in main
    assert admin_person.login not in main
    for needle in ("/var/", "/opt/", "private", "nvapi", "SECRET", "secret_hash"):
        assert needle not in main, needle


def test_user_text_is_escaped(admin_person, make_person):
    evil = make_person("mala@example.com", status="pending")
    evil.display_name = "<script>alert(1)</script>"
    evil.save(update_fields=["display_name"])
    html = body(tailscale_client(admin_person.login).get(URL))
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_the_center_is_not_indexed_for_nala():
    """Nala indexa contenido de la academia (rutas, foro, conocimiento), nunca pantallas de administración."""
    from pathlib import Path

    source = (
        Path(__file__).resolve().parent.parent / "apps" / "assistant" / "search.py"
    ).read_text(encoding="utf-8")
    assert "administracion" not in source and "admin_center" not in source


def test_other_screens_link_to_the_center(admin_person):
    client = tailscale_client(admin_person.login)
    for path in ("/moderacion/", "/equipo/personas/"):
        html = client.get(path).content.decode()
        assert 'href="/administracion/"' in html, path


def test_the_center_is_never_cached_and_has_no_script(admin_person):
    response = tailscale_client(admin_person.login).get(URL)
    assert "no-store" in response["Cache-Control"] or "private" in response["Cache-Control"]
    assert "<script" not in body(response).split("</main>")[0]


def test_the_static_code_cannot_leak_a_403():
    """Ninguna vista del Centro responde 403: lo que no corresponde es 404 (regla de AGENTS.md)."""
    from pathlib import Path

    views = (Path(__file__).resolve().parent.parent / "apps" / "core" / "admin_views.py").read_text(
        encoding="utf-8"
    )
    assert "PermissionDenied" not in views
