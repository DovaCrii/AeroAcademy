"""Kit de figuras (P1-9): cada ruta tiene figura y vocabulario propios; fuera de arquitectura no hay «COTA», «Lámina»…"""

import html as html_lib
import json
import re
from pathlib import Path

import pytest
from django.conf import settings
from django.db import connection
from django.template.loader import get_template
from django.test.utils import CaptureQueriesContext

from apps.catalog import figure_layout, figures
from apps.paths.models import LearningPath

pytestmark = pytest.mark.django_db

KIT_FIGURES = {k for k in figures.DRAWN if k not in ("building", "building-lod", "flight-plan")}
LEGACY = (
    "building",
    "road-profile",
    "flight-plan",
)  # se dibujan con _floors, _journey y _waypoints

SEED_ROUTES = sorted((Path(settings.BASE_DIR) / "seed" / "rutas").glob("*.json"))
DGAC_ROUTE = Path(__file__).parent / "fixtures" / "dgac" / "ruta.json"


def route_files():
    return [*SEED_ROUTES, DGAC_ROUTE]


def load(file):
    return json.loads(file.read_text(encoding="utf-8"))


def test_there_are_23_routes_with_a_figure():
    assert len(route_files()) == 23
    for file in route_files():
        data = load(file)
        assert data.get("figure") in figures.FIGURES, f"{data['slug']}: falta «figure» o no existe"
        assert figures.valid_figure(data["figure"], data["kind"]), data["slug"]


def test_every_route_has_a_figure(site_world):
    for path in LearningPath.objects.all():
        key = figures.figure_key(path)
        assert key in figures.FIGURES
        assert figures.valid_figure(key, path.kind)


def test_the_route_json_decides_its_figure(site_world):
    """La figura de la semilla es la que se usa (no la de respaldo por disciplina)."""
    for file in SEED_ROUTES:
        data = load(file)
        path = LearningPath.objects.get(slug=data["slug"])
        assert figures.figure_key(path) == data["figure"], data["slug"]


def test_figure_templates_exist():
    for fig in figures.FIGURES.values():
        for kind in figures.BOTH:
            get_template(fig.template_for(kind))
    get_template("worlds/figures/_marks.html")


def test_every_figure_has_the_labels_the_templates_read():
    needed = set(figures.BASE_LABELS)
    for key, fig in figures.FIGURES.items():
        assert needed <= set(fig.labels), (key, needed - set(fig.labels))
        if fig.drawn:
            assert fig.layout in figure_layout.LAYOUTS or fig.layout in LEGACY, key


def test_forbidden_words_are_per_figure():
    assert "cota" not in figures.FORBIDDEN["building"] and "pilar" in figures.FORBIDDEN["building"]
    assert "estaca" not in figures.FORBIDDEN["road-profile"]
    assert set(figures.ARCH_WORDS) <= set(figures.FORBIDDEN["pipeline-ai"])
    assert "dibujo y modelado" in figures.FORBIDDEN["building"]


def test_labels_never_use_a_word_their_figure_forbids():
    """Los rótulos de cada figura respetan su propia lista (`FORBIDDEN`)."""
    for key, fig in figures.FIGURES.items():
        text = " ".join(
            str(v) if not isinstance(v, tuple | list) else " ".join(map(str, v))
            for v in fig.labels.values()
        ).lower()
        for word in figures.FORBIDDEN[key]:
            assert word not in text, (key, word)


def _own_texts(data):
    """Texto de la propia ruta (título, descripción, niveles, cursos…): no es vocabulario de la figura."""
    out = [data.get("title", ""), data.get("program", ""), data.get("description", "")]
    intro = data.get("intro")
    if isinstance(intro, dict):
        out += [intro.get("title", ""), intro.get("text", "")]
    for step in data.get("flow", []):
        out += [step.get("title", ""), step.get("text", "")]
    for level in data.get("levels", []):
        out += [level.get("short", ""), level.get("title", ""), level.get("goal", "")]
        out += [c.get("title", "") for c in level.get("external_courses", [])]
        out += [m.get("text", "") for m in level.get("milestones", [])]
    return sorted({t for t in out if t}, key=len, reverse=True)


def figure_region(page_html):
    """Portada y lámina de la figura (hasta la lista de niveles), con el texto propio de la ruta quitado."""
    start = page_html.index('class="lv-cover')
    end = page_html.index('id="niveles"')
    return html_lib.unescape(page_html[start:end])


@pytest.mark.parametrize(
    "file", route_files(), ids=lambda f: f.parent.name if f.name == "ruta.json" else f.stem
)
def test_route_page_labels_belong_to_its_figure(site_world, member_client, file):
    data = load(file)
    response = member_client.get(f"/rutas/{data['slug']}/")
    assert response.status_code == 200
    assert response.context["fig"]["key"] == data["figure"]
    region = figure_region(response.content.decode())
    if data["figure"] in KIT_FIGURES and not (
        data["figure"] == "road-profile" and data["kind"] != "structured"
    ):
        # Cada figura del kit enlaza a cada nivel con los ganchos estables (?nivel=<code>#panel, data-fid).
        for level in data["levels"]:
            if data["kind"] == "structured" or level.get("external_courses"):
                assert f"?nivel={level['code']}#panel" in region, (data["slug"], level["code"])
        if data["figure"] != "road-profile":  # el perfil de Civil 3D conserva los ganchos floor-*
            assert 'data-fid="st-' in region and "data-enhance" in region
    for text in _own_texts(data):
        region = region.replace(text, " ").replace(html_lib.escape(text), " ")
    region = re.sub(r"<[^>]+>", " ", region).lower()  # solo el texto visible
    for word in figures.FORBIDDEN[data["figure"]]:
        assert not re.search(r"(?<!\w)" + re.escape(word), region), (
            data["slug"],
            data["figure"],
            word,
        )


def test_non_architecture_covers_do_not_show_architecture_words(site_world, member_client):
    """Las capturas del dueño: IA y Datos sin COTA ni «Dibujo y modelado»; iTwin sin estacas ni pilares."""
    page = member_client.get("/rutas/ia-101/").content.decode()
    for word in ("COTA", "+3,50", "Dibujo y modelado", "X-101", "Lámina"):
        assert word not in figure_region(page), word
    page = member_client.get("/rutas/bentley-itwin/").content.decode()
    region = figure_region(page).lower()
    for word in ("planta y perfil", "estaca", "pilar"):
        assert word not in region, word


def test_building_keeps_its_architecture_vocabulary(site_world, member_client):
    region = figure_region(member_client.get("/rutas/forma-revit/").content.decode())
    assert "COTA ±0,00" in region and "+3,50" in region and "Lámina" in region


def test_bim_101_uses_lod_instead_of_cotas(site_world, member_client):
    region = figure_region(member_client.get("/rutas/bim-101/").content.decode())
    assert "LOD 100" in region and "COTA" not in region and "+3,50" not in region


def test_figure_adds_no_queries_per_level(site_world, member_client, member):
    """Los puntos de la figura salen del contexto ya calculado: marcar misiones no suma consultas."""
    url = "/rutas/ia-101/"
    member_client.get(url)  # caliente
    with CaptureQueriesContext(connection) as before:
        member_client.get(url)
    from apps.paths.models import Milestone
    from apps.progress import services

    for m in Milestone.objects.filter(path__slug="ia-101", retired=False)[:6]:
        services.set_milestone(member, m, True)
    with CaptureQueriesContext(connection) as after:
        member_client.get(url)
    assert len(after) <= len(before) + 1


def test_the_figure_text_is_escaped(site_world, member_client):
    """El nombre de un nivel con HTML no llega crudo a la figura."""
    from apps.paths.models import Level

    level = Level.objects.filter(path__slug="ia-101").first()
    level.short = "<script>x</script>"
    level.save()
    page = member_client.get("/rutas/ia-101/").content.decode()
    assert "<script>x</script>" not in page


def test_seed_rejects_unknown_or_unfit_figures():
    from apps.paths.seeding import validate_route

    base = load(SEED_ROUTES[0])
    bad = {**base, "figure": "no-existe"}
    assert any("figura desconocida" in e for e in validate_route(bad))
    structured = next(load(f) for f in SEED_ROUTES if load(f)["kind"] == "structured")
    wrong = {**structured, "figure": "flight-plan"}
    assert not any("no sirve" in e for e in validate_route(wrong))  # estructurada: sirve
    external = next(load(f) for f in SEED_ROUTES if load(f)["kind"] == "external_track")
    unfit = {**external, "figure": "building"}
    assert any("no sirve" in e for e in validate_route(unfit))
