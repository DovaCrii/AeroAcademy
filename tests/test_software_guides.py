"""Mosaicos de software, guías rápidas por nivel, portada con datos de la ruta y filas del catálogo."""

import json
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree

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
        ("Using ProjectWise Explorer", ["projectwise"]),
        ("OpenFlows WaterGEMS basics", ["openflows"]),
        ("STAAD structural analysis", ["staad"]),
        ("iTwin Capture Modeler for reality meshes", ["itwin-capture"]),
        ("Getting started with iTwin", ["itwin"]),
        ("SYNCHRO 4D scheduling", ["synchro"]),
        ("LumenRT renders", ["lumenrt"]),
        ("OpenPlant piping", ["openplant"]),
        ("InfraWorks conceptual design", ["infraworks"]),
        ("Operaciones con drones RPAS", ["dgac"]),
        ("AutoCAD Plant 3D piping", ["plant-3d"]),
        ("AutoCAD basics", ["autocad"]),
        ("Algo sin software", []),
    ],
)  # fmt: skip
def test_title_keywords_map_to_tiles(title, expected):
    assert [t.slug for t in software.tiles_from_title(title)] == expected


def test_every_tile_has_an_svg_file():
    root = Path(settings.BASE_DIR) / "apps" / "core" / "static"
    assert len(software.TILES) == 37
    for tile in software.TILES.values():
        assert (root / tile.static_path).is_file(), tile.slug
        assert static(tile.static_path)
        ElementTree.parse(root / tile.static_path)  # SVG bien formado (sin atributos duplicados)


def test_tiles_have_a_family_and_every_tile_has_a_row():
    by_family = {}
    for t in software.TILES.values():
        by_family.setdefault(t.family, set()).add(t.slug)
    assert by_family[software.AUTODESK] == {
        "revit", "civil3d", "autocad", "forma", "acc", "navisworks", "recap", "dynamo", "infraworks", "plant-3d",
    }  # fmt: skip
    assert by_family[software.BENTLEY] == {
        "microstation", "openroads", "openbridge", "openbuildings", "openplant", "openflows", "staad",
        "itwin", "lumenrt", "projectwise", "itwin-capture", "synchro", "descartes",
    }  # fmt: skip
    assert by_family[software.INTERNAL] == {"tbc", "gis", "dgac"}
    assert by_family[software.IA] == {
        "ia", "terminal", "git", "claude-code", "mcp", "agentes", "python", "qgis", "gee", "powerbi", "sql",
    }  # fmt: skip
    assert set(software.ROW_ORDER) == set(software.TILES)


OFFICIAL_AUTODESK = {"autocad", "revit", "forma", "navisworks", "infraworks"}


PICTO_AUTODESK = {"civil3d", "plant-3d", "recap", "dynamo", "acc"}


def test_autodesk_tiles_have_letter_and_code_and_bentley_are_pictograms():
    root = Path(settings.BASE_DIR) / "apps" / "core" / "static"
    for t in software.TILES.values():
        svg = (root / t.static_path).read_text(encoding="utf-8")
        if t.slug in OFFICIAL_AUTODESK:  # logo oficial de Autodesk sobre baldosa blanca
            assert (root / "core/img/software/oficial" / f"autodesk-{t.slug}.svg").is_file()
            assert 'fill="#fff"' in svg and "<text" not in svg
        elif t.slug in PICTO_AUTODESK:  # pictograma simplificado sobre baldosa blanca, sin texto
            assert 'fill="#fff"' in svg and "<text" not in svg
        elif t.family == software.AUTODESK:
            assert (
                f">{t.code}</text>" in svg and svg.count("<text") == 3
            )  # letra (con sombra) + código
        elif t.family in (software.BENTLEY, software.IA):
            assert "<text" not in svg  # pictograma blanco, sin texto


def test_vendor_sections_split_rows_by_family(seeded):
    resources = list(
        Resource.objects.select_related("platform__vendor").prefetch_related("products")
    )
    sections = software.vendor_sections(software.group_by_software(resources))
    keys = [s["key"] for s in sections]
    assert keys == sorted(
        keys, key=software.FAMILIES.index
    )  # Bentley · Autodesk · IA · Topografía (D43)
    assert "autodesk" in keys and "bentley" in keys
    bentley = next(s for s in sections if s["key"] == "bentley")
    assert all(r["tile"].family == "bentley" for r in bentley["rows"])
    assert (
        "shelves" not in bentley and len(bentley["starters"]) == 8
    )  # sin vitrinas repetidas; área oficial: 8
    autodesk = next(s for s in sections if s["key"] == "autodesk")
    assert len(autodesk["pack"]) == 10 and len(autodesk["products"]) == 8


def test_transversal_discipline_and_new_products_map():
    assert software.TILES["autocad"].discipline == software.TRA
    assert software.TILES["microstation"].discipline == software.TRA
    assert software.PRODUCT_TILE["plant-3d"] == "plant-3d"
    assert software.DISCIPLINE_BY_SLUG["transversal"] == software.TRA
    assert software.DISCIPLINE_BY_SLUG["ia-datos"] == software.IAD


def test_vendor_key_and_path_tiles_fall_back_to_title():
    assert software.vendor_key(SimpleNamespace(vendor=SimpleNamespace(slug="bentley"))) == "bentley"
    assert software.vendor_key(SimpleNamespace(vendor=None)) == "internal"
    rpas = SimpleNamespace(title="Diploma interno RPAS", products=SimpleNamespace(all=list))
    assert [t.slug for t in software.software_for_path(rpas)] == ["dgac"]


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


@pytest.mark.parametrize(
    "slug", ["forma-revit", "civil-3d", "forma-coordinacion", "autocad", "plant-3d"]
)
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
    html = member_client.get("/rutas/civil-3d/?nivel=n2&paso=guia").content.decode()
    assert 'class="gd gd-civ"' in html
    assert "Guía rápida · Alineamientos" in html
    assert '<em class="term">Alignment Creation Tools</em>' in html
    assert "Curso esencial".upper() in html.upper()
    assert "define-geometry-for-civil-3d" in html  # enlace al curso esencial
    revit = member_client.get("/rutas/forma-revit/?nivel=n1&paso=guia").content.decode()
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
    assert "lv-tiles vf-autodesk" in html


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


def test_catalog_shows_map_and_short_areas_then_rows_per_vendor_then_grid(seeded, member_client):
    html = member_client.get("/catalogo/").content.decode()
    assert 'class="vs vs-autodesk vs-short"' in html and 'class="vs vs-bentley vs-short"' in html
    assert 'class="cat-row' not in html and "Destacados" not in html  # el detalle vive en ?vendor=
    assert "// 02" in html and "Para empezar" in html
    rows = member_client.get("/catalogo/?vendor=autodesk").content.decode()
    assert 'class="cat-row d-arq"' in rows and 'id="sw-civil3d"' in rows
    assert "data-rail" in rows and "vs-pack" in rows and "lvl-dot lvl-" in rows
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


def test_every_route_has_its_own_unique_icon_file(site_world):
    """Todas las rutas visibles: las de seed/rutas, la de DGAC (fixture) y cualquier otra que haya en la BD."""
    from apps.dgac.constants import ROUTE_SLUG

    root = Path(settings.BASE_DIR) / "apps" / "core" / "static"
    slugs = {json.loads(f.read_text(encoding="utf-8"))["slug"] for f in SEED.glob("*.json")}
    slugs |= {ROUTE_SLUG} | set(LearningPath.objects.values_list("slug", flat=True))
    assert ROUTE_SLUG in LearningPath.objects.values_list("slug", flat=True)
    assert len(slugs) == 23
    assert slugs <= set(software.ROUTE_ICON), slugs - set(software.ROUTE_ICON)
    stems = [software.route_icon(s) for s in slugs]
    assert len(set(stems)) == len(stems)  # ninguna ruta repite icono
    contents = set()
    for stem in stems:
        f = root / "core" / "img" / "software" / f"{stem}.svg"
        ElementTree.parse(f)
        contents.add(f.read_bytes())
    assert len(contents) == len(stems)  # ni siquiera con otro nombre
    assert software.route_icon("no-existe") == ""


def test_official_route_logos_keep_their_source_and_are_on_a_white_tile():
    root = Path(settings.BASE_DIR) / "apps" / "core" / "static" / "core" / "img" / "software"
    official = {
        "python-datos-101": "python",
        "herramientas-ia": "git", "claude-code-mcp": "claude", "geospatial-data-science": "qgis",
        "data-science-aplicada": "kaggle", "datos-reportes": "powerbi",
    }  # fmt: skip
    for slug, name in official.items():
        raw = (root / "oficial" / f"{name}.svg").read_text(encoding="utf-8")
        d = ElementTree.fromstring(raw).find(".//{*}path").get("d")
        tile = (root / f"ruta-{slug}.svg").read_text(encoding="utf-8")
        assert d in tile and 'fill="#fff"' in tile  # forma del logo intacta sobre baldosa blanca
