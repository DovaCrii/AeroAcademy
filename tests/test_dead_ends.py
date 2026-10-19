"""Callejones sin salida: cada estado vacío ofrece el siguiente paso (pedido del dueño, 2026-10-19)."""

import re

import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db


def test_empty_inbox_points_to_the_paths(member_client):
    html = member_client.get("/avisos/").content.decode()
    assert "No tienes avisos" in html and 'href="/rutas/"' in html


def test_empty_knowledge_offers_to_write_or_clear_filters(member_client):
    plain = member_client.get("/conocimiento/").content.decode()
    assert "Escribe el primero" in plain and 'href="/conocimiento/nuevo/"' in plain
    filtered = member_client.get("/conocimiento/?q=zzz").content.decode()
    assert "Quitar filtros" in filtered and "escribir uno" in filtered


def test_catalog_tiles_without_resources_are_links_not_dead_tiles(member_client):
    call_command("seed_catalog", verbosity=0)
    html = member_client.get("/catalogo/?vendor=autodesk").content.decode()
    empty = re.findall(r'<a class="vs-item[^"]*is-empty"[^>]*>', html)
    assert empty and all('href="/foro/nuevo/"' in tag for tag in empty)
    assert '<span class="vs-item' not in html  # ya no hay fichas sin enlace


def test_own_profile_empty_states_say_what_to_do(member_client):
    html = member_client.get("/perfil/").content.decode()
    assert 'href="/certificados/nueva/"' in html and "Registra un certificado" in html
