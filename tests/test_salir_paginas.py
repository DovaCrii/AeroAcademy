"""Páginas públicas sin callejones (D41): «Volver al inicio», «Salir» con sesión y el aviso del enlace del equipo."""

import pytest
from django.core.cache import cache
from django.test import Client

from apps.accounts import services, team_link
from apps.accounts.models import Person

pytestmark = pytest.mark.django_db
GOOD = "Clave-de-prueba-6128!"  # valor de prueba generado para esta suite
BACK = "← Volver al inicio"


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def link_path(admin_person):
    _, token = team_link.create_link(admin_person, days=14)
    return f"/inscripcion/{token}/"


def anon():
    return Client(REMOTE_ADDR="127.0.0.1")


def form(email="nuevo@empresa.cl"):
    return {"email": email, "display_name": "Nuevo Nombre", "password1": GOOD, "password2": GOOD}


@pytest.mark.parametrize("door", ["tailnet", "public"])
def test_every_public_page_has_back_to_start(settings, link_path, door):
    settings.PUBLIC_DOOR = door == "public"
    for path in ("/entrar/", link_path, "/inscripcion/token-malo/", "/registro/token-malo/"):
        html = anon().get(path).content.decode()
        assert BACK in html and 'href="/bienvenida/"' in html, path
        assert "Salir</button>" not in html, path  # sin sesión no hay «Salir»


def test_result_page_has_back_and_single_answer(link_path):
    first = anon().post(link_path, form())
    assert "Recibimos tu inscripción" in first.content.decode()
    assert BACK in first.content.decode()
    # A12: la misma respuesta (texto y código) para un correo nuevo y para uno ya existente
    again = anon().post(link_path, form())
    assert again.status_code == first.status_code
    assert again.content.decode().count("Recibimos tu inscripción") == 1


def test_team_signup_with_session_shows_notice_and_exit_button(client_for, member, link_path):
    html = client_for(member.login).get(link_path).content.decode()
    assert f"Ya iniciaste sesión como <b>{member.login}</b>" in html
    assert "Salir y continuar" in html
    assert 'name="email"' not in html  # no muestra el formulario
    assert f'name="next" value="{link_path}"' in html


def test_team_signup_post_with_session_does_not_enroll(client_for, member, link_path):
    before = Person.objects.count()
    response = client_for(member.login).post(link_path, form())
    assert "Salir y continuar" in response.content.decode()
    assert Person.objects.count() == before


def test_exit_and_continue_returns_to_the_same_link(client_for, member, link_path):
    client = client_for(member.login)
    client.get("/")
    response = client.post("/salir/", {"next": link_path})
    assert response.status_code == 302 and response.url == link_path
    page = client.get(link_path)  # el encabezado ya no inicia sesión solo
    assert 'name="email"' in page.content.decode()


@pytest.mark.parametrize(
    "bad", ["//evil.com", "/\\evil.com", "https://evil.com", "javascript:alert(1)"]
)
def test_logout_next_ignores_malicious_values(client_for, member, bad):
    response = client_for(member.login).post("/salir/", {"next": bad})
    assert response.status_code == 302 and response.url == "/bienvenida/"


def test_session_email_is_escaped_in_the_notice(link_path):
    evil = "<script>alert(1)</script>@example.com"
    person = Person.objects.create_user("x@example.com")
    Person.objects.filter(pk=person.pk).update(login=evil, status="approved")
    client = anon()
    client.force_login(Person.objects.get(pk=person.pk), backend=services.PASSWORD_BACKEND)
    html = client.get(link_path).content.decode()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_waiting_and_suspended_have_back_and_exit(client_for, make_person):
    pending = make_person("pend@example.com", status="pending")
    html = client_for(pending.login).get("/espera/").content.decode()
    assert BACK in html and "Salir</button>" in html
    susp = make_person("susp@example.com", status="suspended")
    assert "Salir</button>" in client_for(susp.login).get("/").content.decode()
