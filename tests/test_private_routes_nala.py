"""Las rutas privadas de JEJ (`PRIVATE_COURSES_DIR/<slug>/ruta.json`) nunca llegan a Nala: ni al índice de búsqueda ni
al contexto que viaja al modelo externo. Lo exige el checklist de autoría de docs/CURSOS.md."""

import json

import pytest
from django.core.management import call_command
from django.db import connection

from apps.assistant import search
from apps.core.private_files import private_route_slugs
from apps.dgac import constants

pytestmark = pytest.mark.django_db

SLUG = "curso-interno-demo"


def route_json():
    return {
        "slug": SLUG,
        "title": "Curso interno demo",
        "program": "Demo · Material reservado",
        "platform": "interna",
        "kind": "structured",
        "vendor": "bentley",
        "products": ["microstation"],
        "disciplines": ["transversal"],
        "world": "architecture",
        "description": "frase-reservada-para-nala",
        "levels": [
            {
                "code": "d0",
                "order": 0,
                "short": "Demo",
                "title": "Nivel reservado",
                "estimated_hours": 1,
                "audience": "audiencia-reservada",
                "goal": "meta-reservada",
                "milestones": [
                    {
                        "key": "d0-t0",
                        "order": 0,
                        "title": "misión-reservada",
                        "text": "texto-reservado",
                    }
                ],
            }
        ],
    }


@pytest.fixture
def private_course(settings, tmp_path):
    settings.PRIVATE_COURSES_DIR = tmp_path
    folder = tmp_path / SLUG
    folder.mkdir()
    (folder / "ruta.json").write_text(json.dumps(route_json()), encoding="utf-8")
    call_command("seed_catalog", verbosity=0)
    call_command("cargar_cursos_privados", verbosity=0)
    return folder


def test_private_route_slugs_include_dgac_and_every_folder_with_a_route(settings, tmp_path):
    settings.PRIVATE_COURSES_DIR = tmp_path
    (tmp_path / "con-ruta").mkdir()
    (tmp_path / "con-ruta" / "ruta.json").write_text("{}", encoding="utf-8")
    (tmp_path / "solo-fotos" / "fotos").mkdir(parents=True)
    slugs = private_route_slugs()
    assert constants.ROUTE_SLUG in slugs and "con-ruta" in slugs and "solo-fotos" not in slugs


def test_missing_private_dir_still_returns_the_dgac_slug(settings, tmp_path):
    settings.PRIVATE_COURSES_DIR = tmp_path / "no-existe"
    assert private_route_slugs() == (constants.ROUTE_SLUG,)


def test_private_course_content_is_not_in_the_nala_index(private_course):
    assert search.reindex() > 0
    with connection.cursor() as cur:
        cur.execute("SELECT kind, ref, title, body, url FROM assistant_fts")
        blob = json.dumps(cur.fetchall(), ensure_ascii=False)
    for secret in (SLUG, "frase-reservada-para-nala", "audiencia-reservada", "misión-reservada"):
        assert secret not in blob
    for hit in search.search("frase-reservada-para-nala"):
        assert SLUG not in f"{hit['title']} {hit['body']} {hit['url']}"


def test_private_course_missions_never_reach_the_model(private_course, member):
    from apps.assistant import context
    from apps.paths.models import LearningPath

    LearningPath.objects.exclude(slug=SLUG).update(is_published=False)
    from apps.core import dashboard

    mission = dashboard.suggested_mission(member)
    assert mission and mission["path"].slug == SLUG  # sí se sugiere dentro de la app
    assert context.pending_titles(member) == []  # pero no viaja al proveedor externo
