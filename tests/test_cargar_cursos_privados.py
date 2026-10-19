"""Comando `cargar_cursos_privados`: rutas privadas desde PRIVATE_COURSES_DIR/<slug>/ruta.json.

Solo usa una ruta de juguete en una carpeta temporal; nada del contenido real de JEJ.
"""

import json
from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from apps.paths.models import LearningPath, Level, Milestone, QuizQuestion

pytestmark = pytest.mark.django_db

SLUG = "curso-privado-prueba"


def toy_route(slug=SLUG):
    return {
        "slug": slug,
        "title": "Curso privado de prueba",
        "program": "Curso interno de prueba",
        "platform": "interna",
        "kind": "structured",
        "vendor": "aeroacademy",
        "products": [],
        "disciplines": ["transversal"],
        "world": "civil",
        "description": "Ruta mínima de juguete para las pruebas.",
        "levels": [
            {
                "code": "p01",
                "order": 10,
                "short": "Primera clase",
                "title": "Primera clase de prueba",
                "milestones": [{"key": "p01-t0", "text": "Hacer algo de prueba"}],
                "quiz": [
                    {
                        "key": "p01-q0",
                        "question": "¿Pregunta de prueba?",
                        "options": ["Sí", "No"],
                        "answer": 0,
                        "explanation": "Porque sí.",
                    }
                ],
            }
        ],
    }


def write_route(root, folder=SLUG, route=None):
    path = root / folder
    path.mkdir(parents=True)
    (path / "ruta.json").write_text(json.dumps(route or toy_route(folder)), encoding="utf-8")
    return path


def run(*args):
    out, err = StringIO(), StringIO()
    call_command("cargar_cursos_privados", *args, stdout=out, stderr=err)
    return out.getvalue(), err.getvalue()


@pytest.fixture(autouse=True)
def private_root(settings, tmp_path):
    settings.PRIVATE_COURSES_DIR = tmp_path / "cursos"
    call_command("seed_catalog", verbosity=0)
    return settings.PRIVATE_COURSES_DIR


def test_loads_the_private_route(private_root):
    write_route(private_root)
    out, _ = run()
    assert f"Ruta {SLUG}: 1 niveles, 1 misiones, 1 preguntas." in out
    path = LearningPath.objects.get(slug=SLUG)
    assert path.platform.slug == "interna"
    assert Level.objects.filter(path=path, code="p01").exists()
    assert Milestone.objects.filter(path=path, key="p01-t0").exists()
    assert QuizQuestion.objects.filter(path=path, key="p01-q0").exists()


def test_is_idempotent_and_new_levels_are_appended(private_root):
    folder = write_route(private_root)
    run()
    run()
    assert LearningPath.objects.filter(slug=SLUG).count() == 1
    assert Milestone.objects.filter(path__slug=SLUG).count() == 1
    route = toy_route()
    route["levels"].append(
        {"code": "p02", "order": 20, "short": "Segunda", "title": "Segunda clase", "milestones": []}
    )
    (folder / "ruta.json").write_text(json.dumps(route), encoding="utf-8")
    run()
    assert list(
        Level.objects.filter(path__slug=SLUG).order_by("order").values_list("code", flat=True)
    ) == [
        "p01",
        "p02",
    ]
    assert Milestone.objects.filter(path__slug=SLUG).count() == 1


def test_dry_run_does_not_save(private_root):
    write_route(private_root)
    out, _ = run("--dry-run")
    assert "[dry-run]" in out
    assert not LearningPath.objects.filter(slug=SLUG).exists()


def test_slug_must_match_the_folder_name(private_root):
    write_route(private_root, folder="otra-carpeta", route=toy_route("otro-slug"))
    with pytest.raises(CommandError):
        run()
    assert not LearningPath.objects.filter(slug="otro-slug").exists()


def test_invalid_route_reports_errors_and_keeps_loading_the_rest(private_root):
    bad = toy_route("ruta-mala")
    bad["vendor"] = "no-existe"
    write_route(private_root, folder="ruta-mala", route=bad)
    write_route(private_root)
    with pytest.raises(CommandError):
        run()
    assert LearningPath.objects.filter(slug=SLUG).exists()
    assert not LearningPath.objects.filter(slug="ruta-mala").exists()


def test_folder_with_only_photos_is_ignored(private_root):
    (private_root / "solo-fotos" / "fotos").mkdir(parents=True)
    (private_root / "solo-fotos" / "fotos" / "a.png").write_bytes(b"x")
    out, err = run()
    assert err == ""
    assert not LearningPath.objects.filter(slug="solo-fotos").exists()
    assert "No hay rutas privadas" in out


def test_missing_folder_is_not_an_error(settings, tmp_path):
    settings.PRIVATE_COURSES_DIR = tmp_path / "no-existe"
    out, _ = run()
    assert "No existe la carpeta" in out


def test_private_route_is_hidden_from_pending_people_and_shown_to_members(
    private_root, client_for, make_person
):
    write_route(private_root)
    run()
    pending = make_person("nueva@example.com", status="pending")
    c = client_for(pending.login)
    assert c.get(f"/rutas/{SLUG}/").status_code == 302
    assert c.get("/rutas/").status_code == 302
    assert c.get("/catalogo/").status_code == 302

    member = make_person("socia@example.com")
    m = client_for(member.login)
    assert "Curso privado de prueba" in m.get("/rutas/").content.decode()
    assert "Curso privado de prueba" in m.get("/catalogo/").content.decode()
