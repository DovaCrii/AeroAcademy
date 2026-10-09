"""Mosaicos de software, guías rápidas por nivel, portada con datos de la ruta y filas del catálogo."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.conf import settings
from django.core.management import call_command
from django.templatetags.static import static

from apps.catalog import guides, software
from apps.catalog.models import Platform, Product, Resource
from apps.paths.models import LearningPath

pytestmark = pytest.mark.django_db

SEED = Path(settings.BASE_DIR) / "seed" / "rutas"


@pytest.fixture
def seeded():
    call_command("seed_catalog", verbosity=0)


def fake(title, kind="module", tags=()):
    """Recurso sin base de datos: sin products ni platform precargados, solo título."""
    return SimpleNamespace(title=title, kind=kind, tags=list(tags))


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Learn Civil 3D in 90 minutes", ["civil3d"]),
        ("Revit as a Forma Connected Client", ["revit", "forma"]),
        ("Iterative design and analysis with Forma and Revit", ["forma", "revit"]),
        ("Learn Forma Data Management and Build in 90 minutes", ["acc"]),
        ("Dynamo in Forma", ["dynamo", "forma"]),
        ("Reduce errors by using Point Clouds in Civil 3D", ["civil3d"]),
        ("Bentley Accredited Road Modeler: OpenRoads Modeling Core Skills", ["openroads"]),
        ("Bentley Accredited BIM Modeler: Basic Architectural Modeling with OpenBuildings", ["openbuildings"]),
        ("Catálogo MicroStation en Bentley Learn", ["microstation"]),
        ("Introduction to BIM for civil design and engineering", ["civil3d"]),
        ("Algo sin software", []),
    ],
)  # fmt: skip
def test_title_keywords_map_to_tiles(title, expected):
    assert [t.slug for t in software.tiles_from_title(title)] == expected


def test_every_tile_has_an_svg_file():
    root = Path(settings.BASE_DIR) / "apps" / "core" / "static"
    assert len(software.TILES) == 14
    for tile in software.TILES.values():
        assert (root / tile.static_path).is_file(), tile.slug
        assert static(tile.static_path)


def test_products_beat_title_then_platform(seeded):
    resource = Resource.objects.select_related("platform__vendor").get(title="Dynamo in Forma")
    # sin productos: gana el título
    resource = (
        Resource.objects.select_related("platform__vendor")
        .prefetch_related("products")
        .get(pk=resource.pk)
    )
    assert software.software_for_resource(resource)[0].slug == "dynamo"
    resource.products.set(Product.objects.filter(slug="revit"))
    resource = Resource.objects.prefetch_related("products").get(pk=resource.pk)
    assert [t.slug for t in software.software_for_resource(resource)] == ["revit"]


def test_platform_and_vendor_are_the_last_resort(seeded):
    geocom = Platform.objects.get(slug="geocom-cursos")
    r = Resource.objects.create(platform=geocom, title="Curso de nivelación")
    r = (
        Resource.objects.select_related("platform__vendor")
        .prefetch_related("products")
        .get(pk=r.pk)
    )
    assert [t.slug for t in software.software_for_resource(r)] == ["tbc"]
    bentley = (
        Resource.objects.select_related("platform__vendor")
        .prefetch_related("products")
        .get(title="QuickStarts en Bentley Learn")
    )
    assert [t.slug for t in software.software_for_resource(bentley)] == ["microstation"]


def test_mapping_does_no_queries(seeded, django_assert_num_queries):
    r = Resource.objects.select_related("platform__vendor").prefetch_related("products").first()
    with django_assert_num_queries(0):
        software.software_for_resource(r)
    bare = Resource.objects.get(pk=r.pk)
    with django_assert_num_queries(0):  # sin precarga no consulta: solo usa el título
        software.software_for_resource(bare)


def test_level_mapping():
    assert (
        software.level_for_resource(fake("Learn Civil 3D in 90 minutes", "course"))[0]
        == "fundamental"
    )
    assert (
        software.level_for_resource(fake("Define geometry for Civil 3D", "module"))[0]
        == "intermedio"
    )
    assert (
        software.level_for_resource(fake("Civil 3D Certification Prep", "course"))[0] == "avanzado"
    )
    assert software.level_for_resource(fake("Algo", "exam"))[0] == "avanzado"
    assert (
        software.level_for_resource(fake("Algo", "module", ["Prepara certificación"]))[0]
        == "avanzado"
    )
    assert software.type_label(SimpleNamespace(kind="learning_plan")) == "Plan de aprendizaje"


def test_group_by_software_keeps_order_and_limits(seeded):
    resources = list(
        Resource.objects.select_related("platform__vendor").prefetch_related("products")
    )
    rows = software.group_by_software(resources, per_row=3)
    slugs = [r["tile"].slug for r in rows]
    assert slugs == sorted(slugs, key=software.ROW_ORDER.index)
    assert "revit" in slugs and "civil3d" in slugs
    for row in rows:
        assert len(row["items"]) <= 3
        assert row["more"] == max(0, row["total"] - 3)


def test_discipline_key_by_route(seeded):
    assert software.discipline_key(LearningPath.objects.get(slug="civil-3d")) == software.CIV
    assert software.discipline_key(LearningPath.objects.get(slug="forma-revit")) == software.ARQ
    assert software.discipline_key(LearningPath.objects.get(slug="bentley-learn")) == software.CIV


# ---- guías --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("slug", ["forma-revit", "civil-3d"])
def test_every_level_has_a_guide_with_an_existing_essential_course(slug):
    data = json.loads((SEED / f"{slug}.json").read_text(encoding="utf-8"))
    for level in data["levels"]:
        guide = level.get("guide")
        assert guide, (slug, level["code"])
        assert guide["do"] and guide["commands"] and guide["mistakes"]
        titles = {r["title"] for r in level["resources"]}
        assert guide["essential"] in titles
        assert guide["software"] in software.TILES
        assert any("*" in step for step in guide["do"])  # comandos con el estilo *Comando*


def test_guide_lookup_and_unknown_cases():
    assert guides.guide_for("civil-3d", "n2")["title"].startswith("Guía rápida")
    assert guides.guide_for("civil-3d", "zz") is None
    assert guides.guide_for("no-existe", "n0") is None


def test_guide_renders_in_route_panel(seeded, member_client, member):
    html = member_client.get("/rutas/civil-3d/?nivel=n2").content.decode()
    assert 'class="gd gd-civ"' in html
    assert "Guía rápida · Alineamientos" in html
    assert '<em class="term">Alignment Creation Tools</em>' in html
    assert "Curso esencial".upper() in html.upper()
    assert "define-geometry-for-civil-3d" in html  # enlace al curso esencial
    revit = member_client.get("/rutas/forma-revit/?nivel=n1").content.decode()
    assert 'class="gd gd-arq"' in revit
    assert "Guía rápida · Fundamentos de Revit" in revit


def test_guide_text_is_escaped():
    guide = {"title": "x", "do": ["<script>alert(1)</script> *Cmd*"], "essential": ""}
    from django.template.loader import render_to_string

    html = render_to_string(
        "catalog/partials/guide.html", {"guide": guide, "flavour": "civ", "code": "n0"}
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


# ---- portada con datos de la ruta --------------------------------------------------------------------------


def test_civil_cover_uses_route_data_not_cc410(seeded, member_client):
    html = member_client.get("/rutas/civil-3d/").content.decode()
    assert "CC 410" not in html
    assert "Infraestructura vial" in html  # programa de la ruta
    assert "Topografía y diseño vial" in html
    assert "fl-civ" in html and 'data-scene="terrain"' in html
    assert "ESCALA 1:1000" in html
    assert "Del km 0 a la certificación".lower() in html.lower()  # intro de la ruta
    assert "lv-profile" in html
    assert 'alt="Civil 3D"' in html  # mosaico de la portada


def test_architecture_cover_keeps_its_data(seeded, member_client):
    html = member_client.get("/rutas/forma-revit/").content.decode()
    assert "Levantamiento digital · CC 410" in html
    assert "fl-arq" in html and 'data-scene="building"' in html
    assert "lv-profile" not in html


def test_program_text_comes_from_the_path(seeded, member_client):
    LearningPath.objects.filter(slug="civil-3d").update(program="Obras lineales · Mi programa")
    html = member_client.get("/rutas/civil-3d/").content.decode()
    assert "Obras lineales" in html and "Mi programa" in html


# ---- catálogo -----------------------------------------------------------------------------------------------


def test_catalog_shows_rows_per_software_then_grid_when_filtered(seeded, member_client):
    html = member_client.get("/catalogo/").content.decode()
    assert 'class="cat-row d-arq"' in html and 'id="sw-civil3d"' in html
    assert "data-rail" in html and "cat-lvl lvl-" in html
    assert "// 02" in html
    grid = member_client.get("/catalogo/?software=civil3d").content.decode()
    assert "cat-grid" in grid and 'class="cat-row' not in grid
    assert "Civil 3D" in grid
    assert "cat-grid" in member_client.get("/catalogo/?q=revit").content.decode()
    assert "cat-grid" in member_client.get("/catalogo/?todo=1").content.decode()


def test_catalog_unknown_software_is_ignored(seeded, member_client):
    assert member_client.get("/catalogo/?software=<script>").status_code == 200


def test_catalog_queries_do_not_grow(seeded, member_client):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    member_client.get("/catalogo/")  # calienta cachés
    with CaptureQueriesContext(connection) as before:
        assert member_client.get("/catalogo/").status_code == 200
    extra = Platform.objects.get(slug="autodesk-learning")
    for i in range(20):
        Resource.objects.create(platform=extra, title=f"Revit curso {i}")
    with CaptureQueriesContext(connection) as after:
        assert member_client.get("/catalogo/").status_code == 200
    assert len(after) == len(before)
