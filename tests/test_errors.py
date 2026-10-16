"""Página 404 útil (P0-1): sin filtrar qué existe y con un registro que no guarda datos personales."""

import logging
import re

import pytest

pytestmark = pytest.mark.django_db


def test_404_page_is_helpful_and_does_not_leak(member_client, member):
    response = member_client.get("/rutas/no-existe/")
    assert response.status_code == 404
    html = response.content.decode()
    assert "Esta página no existe o ya no está disponible" in html
    for needle in ('href="/"', 'href="/rutas/"', 'href="/catalogo/"', "data-back"):
        assert needle in html, needle
    assert 'action="/ayuda/"' in html and 'name="q"' in html  # buscador
    assert "Not Found" not in html


def test_404_is_the_same_for_hidden_and_missing(member_client, admin_person):
    """Un recurso oculto o restringido responde igual que uno que no existe."""
    from django.core.management import call_command

    from apps.paths.models import LearningPath

    call_command("seed_catalog", verbosity=0)
    LearningPath.objects.filter(slug="bim-101").update(is_published=False)
    hidden = member_client.get("/rutas/bim-101/")
    missing = member_client.get("/rutas/otro-que-no-existe/")
    assert hidden.status_code == missing.status_code == 404
    token = re.compile(r'value="[A-Za-z0-9]{40,}"')  # el token CSRF cambia en cada respuesta
    assert token.sub("", hidden.content.decode()) == token.sub("", missing.content.decode())
    assert "BIM 101" not in hidden.content.decode()


def test_403_page_is_friendly(member_client):
    response = member_client.get("/equipo/personas/agregar/")
    assert response.status_code == 403
    assert "No tienes acceso a esta página" in response.content.decode()


def test_404_is_logged_without_query(member_client, member, caplog):
    caplog.set_level(logging.INFO, logger="apps.core")
    member_client.get(
        "/rutas/no-existe/?q=secreto&email=ana@example.com",
        HTTP_REFERER="http://testserver/catalogo/?x=privado",
    )
    messages = [r.getMessage() for r in caplog.records if r.name == "apps.core"]
    assert messages == ["404 /rutas/no-existe/ ref=/catalogo/"]
    text = "\n".join(messages)
    assert "secreto" not in text and "example.com" not in text and "privado" not in text


def test_404_log_ignores_external_referer_and_anonymous(client, member_client, caplog):
    caplog.set_level(logging.INFO, logger="apps.core")
    member_client.get("/rutas/no-existe/", HTTP_REFERER="https://evil.example.org/x?y=1")
    assert [r.getMessage() for r in caplog.records if r.name == "apps.core"] == [
        "404 /rutas/no-existe/ ref=-"
    ]
    caplog.clear()
    from django.test import Client

    anonymous = Client(REMOTE_ADDR="127.0.0.1")
    anonymous.get("/bienvenida/no-existe/")  # público y anónimo: no se registra
    assert not [r for r in caplog.records if r.name == "apps.core"]
