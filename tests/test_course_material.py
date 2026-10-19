"""PDF privados de un curso (`cursos:material`): carpeta `material/`, descarga como adjunto, mismo control que las fotos.

Solo usa una ruta de juguete en una carpeta temporal; nada del contenido real de JEJ.
"""

import json

import pytest
from django.core.management import call_command

from apps.catalog import guides
from apps.catalog.models import Resource
from apps.catalog.seeding import SeedError
from apps.core import private_files
from apps.paths.models import LearningPath
from apps.paths.seeding import load_route
from tests.test_cargar_cursos_privados import toy_route

pytestmark = pytest.mark.django_db

SLUG = "curso-material-prueba"
PDF = b"%PDF-1.4\n% documento de juguete\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n"
URL = f"/cursos/material/{SLUG}/ficha.pdf"


def route_with_file(file="ficha.pdf", **extra):
    data = toy_route(SLUG)
    data["levels"][0]["resources"] = [{"title": "Ficha de prueba", "file": file, **extra}]
    return data


@pytest.fixture
def course(settings, tmp_path):
    settings.PRIVATE_COURSES_DIR = tmp_path / "cursos"
    folder = settings.PRIVATE_COURSES_DIR / SLUG
    (folder / "material").mkdir(parents=True)
    (folder / "fotos").mkdir()
    (folder / "material" / "ficha.pdf").write_bytes(PDF)
    (folder / "fotos" / "foto.png").write_bytes(PNG)
    call_command("seed_catalog", verbosity=0)
    (folder / "ruta.json").write_text(json.dumps(route_with_file()), encoding="utf-8")
    call_command("cargar_cursos_privados", verbosity=0)
    return folder


def test_pdf_is_served_to_approved_people_as_attachment(course, member_client):
    resp = member_client.get(URL)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/pdf"
    assert resp["Content-Disposition"].startswith("attachment")
    assert 'filename="ficha.pdf"' in resp["Content-Disposition"]
    assert resp["X-Content-Type-Options"] == "nosniff"
    assert resp["Content-Security-Policy"] == "default-src 'none'; sandbox"
    assert resp["Cache-Control"] == "private, max-age=300"
    assert b"".join(resp.streaming_content) == PDF


def test_post_is_not_allowed(course, member_client):
    assert member_client.post(URL).status_code == 405


@pytest.mark.parametrize(
    "name",
    [
        "..%2Fruta.json",
        "%2E%2E%2Fficha.pdf",
        "a/../ficha.pdf",
        "sub/ficha.pdf",
        "..\\ficha.pdf",
        "ficha.pdf%00.txt",
        "ficha.txt",
        "ruta.json",
        ".pdf",
        "ficha..pdf",
        "no-existe.pdf",
    ],
)
def test_odd_names_and_missing_files_are_404(course, member_client, name):
    assert member_client.get(f"/cursos/material/{SLUG}/{name}").status_code == 404


def test_file_that_is_not_a_real_pdf_is_404(course, member_client):
    (course / "material" / "falso.pdf").write_bytes(b"<html>no soy pdf</html>")
    assert member_client.get(f"/cursos/material/{SLUG}/falso.pdf").status_code == 404


def test_unknown_route_is_404(course, member_client):
    assert member_client.get("/cursos/material/no-existe/ficha.pdf").status_code == 404


def test_draft_route_is_404_for_members(course, member_client):
    LearningPath.objects.filter(slug=SLUG).update(is_published=False)
    assert member_client.get(URL).status_code == 404


def test_pending_and_anonymous_people_do_not_get_it(course, make_person, client_for):
    pending = make_person("nueva@example.com", status="pending")
    assert client_for(pending.login).get(URL).status_code == 302
    assert client_for("").get(URL).status_code in (302, 401, 403, 404)


def test_folders_do_not_cross_over(course, member_client):
    (course / "fotos" / "ficha.pdf").write_bytes(PDF)
    (course / "material" / "foto.png").write_bytes(PNG)
    assert member_client.get(f"/cursos/material/{SLUG}/foto.png").status_code == 404
    assert member_client.get(f"/cursos/foto/{SLUG}/ficha.pdf").status_code == 404
    assert member_client.get(f"/cursos/foto/{SLUG}/foto.png").status_code == 200


def test_shared_module_rules(tmp_path):
    (tmp_path / "a.pdf").write_bytes(PDF)
    (tmp_path / "a.png").write_bytes(PNG)
    assert private_files.safe_document(tmp_path, "a.pdf").name == "a.pdf"
    assert private_files.safe_file(tmp_path, "a.pdf") is None
    for bad in ("a.png", "../a.pdf", "sub/a.pdf", "", None, "a.exe", "x" * 90 + ".pdf"):
        assert private_files.safe_document(tmp_path, bad) is None
    assert guides.material_path("../x", "a.pdf") is None


def test_file_in_the_seed_saves_the_internal_url(course):
    resource = Resource.objects.get(title="Ficha de prueba")
    assert resource.url == URL
    assert resource.is_internal_url


def test_invalid_file_in_the_seed_is_a_clear_error(course):
    for bad in ("../ficha.pdf", "ficha.png", "sub/ficha.pdf", "ficha"):
        with pytest.raises(SeedError) as exc:
            load_route(route_with_file(bad))
        assert "«file» inválido" in "\n".join(exc.value.errors)


def test_explicit_url_wins_over_file(course):
    load_route(route_with_file(url="https://example.com/doc"))
    assert Resource.objects.get(title="Ficha de prueba").url == "https://example.com/doc"


def test_internal_link_has_no_external_marks(course, member_client):
    html = member_client.get("/catalogo/?q=Ficha").content.decode()
    assert f'href="{URL}"' in html
    link = html[html.index(f'href="{URL}"') - 40 : html.index(f'href="{URL}"') + 200]
    assert "_blank" not in link and "↗" not in link
    detail = member_client.get(f"/rutas/{SLUG}/").content.decode()
    assert URL not in detail or "_blank" not in detail[detail.index(URL) : detail.index(URL) + 120]


def test_document_of_a_draft_route_is_not_in_catalog_nor_search_index(course, member_client):
    from apps.assistant import search

    LearningPath.objects.filter(slug=SLUG).update(is_published=False)
    assert "Ficha de prueba" not in member_client.get("/catalogo/?q=Ficha").content.decode()
    titles = [row[2] for row in search._rows()]
    assert "Ficha de prueba" not in titles
    LearningPath.objects.filter(slug=SLUG).update(is_published=True)
    assert "Ficha de prueba" in member_client.get("/catalogo/?q=Ficha").content.decode()
    # Es una ruta privada (tiene carpeta con ruta.json): publicada o no, sus recursos nunca entran al índice de Nala.
    assert "Ficha de prueba" not in [row[2] for row in search._rows()]
