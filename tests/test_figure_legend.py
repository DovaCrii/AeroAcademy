"""Leyenda de las figuras: en celular (≤ 560 px) los rótulos del SVG se ocultan y cada estación sale en una lista."""

import html as html_lib
import re
from pathlib import Path

import pytest
from django.conf import settings
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.catalog import figures

from .test_figures import DGAC_ROUTE, SEED_ROUTES, load

pytestmark = pytest.mark.django_db

ROUTES = [*SEED_ROUTES, DGAC_ROUTE]
STATIC = Path(settings.BASE_DIR) / "apps/core/static/worlds"


def _id(f):
    return f.parent.name if f.name == "ruta.json" else f.stem


def _legend(page):
    """Texto HTML de la leyenda (una sola `<ol class="fg-legend">`)."""
    assert page.count('class="fg-legend"') == 1
    start = page.index('<ol class="fg-legend"')
    return page[start : page.index("</ol>", start)]


def _rows(legend):
    return re.findall(r"<li>.*?</li>", legend, re.S)


def _expected(ctx):
    """(nombre, código del enlace o None) de cada estación, según los datos con los que se dibuja la figura."""
    if (
        ctx.get("journey")
        and ctx["fig"]["key"] == "road-profile"
        and ctx["path"].kind == "external_track"
    ):
        j = ctx["journey"]
        return [(s["title"], None) for s in j["stakes"]] + [(p["title"], None) for p in j["piers"]]
    key = ctx["fig"]["key"]
    if key in ("building", "building-lod"):
        return [(f["short"], f["code"]) for f in ctx["building"]["floors"]]
    if key == "flight-plan":
        return [(p["short"], p["code"]) for p in ctx["flight"]["points"]]
    return [(s["short"], s["code"]) for s in ctx["fg"]["items"]]


@pytest.mark.parametrize("file", ROUTES, ids=_id)
def test_each_route_page_has_one_legend_with_every_station(site_world, member_client, file):
    data = load(file)
    response = member_client.get(f"/rutas/{data['slug']}/")
    assert response.status_code == 200
    page = response.content.decode()
    ctx = response.context
    if data["figure"] == "road-profile" and data["kind"] == "structured":
        # El perfil estructurado ya es una lista HTML de enlaces con el nombre completo: no se duplica.
        assert 'class="fg-legend"' not in page and 'class="pf-st"' in page
        return
    legend = _legend(page)
    assert 'aria-label="Estaciones de la figura"' in legend
    expected = _expected(ctx)
    assert expected, data["slug"]
    rows = _rows(legend)
    assert len(rows) == len(expected), data["slug"]
    text = html_lib.unescape(legend)
    for name, _code in expected:
        assert name in text, (data["slug"], name)  # nombre completo, sin recortar
    links = re.findall(r'href="([^"]+)"', legend)
    slug = data["slug"]
    wanted = [f"/rutas/{slug}/?nivel={code}#panel" for _n, code in expected if code]
    assert links == wanted, slug
    assert len(links) == len([c for _n, c in expected if c])


def test_every_drawn_figure_is_covered_by_a_seed_route(site_world, member_client):
    """Cada clave de `figures.DRAWN` tiene al menos una ruta que la usa en estas pruebas."""
    used = {load(f)["figure"] for f in ROUTES}
    assert set(figures.DRAWN) - {"stack"} <= used, (
        set(figures.DRAWN) - used
    )  # `stack`: ver la prueba siguiente


@pytest.mark.parametrize("slug", ["ia-101", "bentley-learn"])
def test_the_generic_stack_figure_has_its_legend(site_world, member_client, monkeypatch, slug):
    monkeypatch.setattr(figures.guides, "figure_name", lambda _slug: "stack")
    response = member_client.get(f"/rutas/{slug}/")
    assert response.context["fig"]["key"] == "stack"
    legend = _legend(response.content.decode())
    assert len(_rows(legend)) == len(response.context["fg"]["items"])
    assert f"/rutas/{slug}/?nivel=" in legend


def test_the_state_is_said_in_words(site_world, member_client):
    page = member_client.get("/rutas/ia-101/").content.decode()
    assert re.search(r"fg-lg-state\">(hecho|en curso · \d+ %|por hacer)<", _legend(page))
    page = member_client.get("/rutas/bentley-learn/").content.decode()
    states = set(re.findall(r'fg-lg-state">([^<]+)<', _legend(page)))
    assert states <= {
        "verificado",
        "en revisión",
        "rechazado",
        "por hacer",
        "pilar en pie",
        "por levantar",
    }


def test_legend_text_is_escaped(site_world, member_client):
    from apps.paths.models import Level

    level = Level.objects.filter(path__slug="ia-101").first()
    level.short = "<script>x</script>"
    level.save()
    page = member_client.get("/rutas/ia-101/").content.decode()
    assert "<script>x</script>" not in _legend(page)


def test_legend_adds_no_queries_per_level(site_world, member_client, member):
    """La leyenda sale del contexto ya calculado: marcar misiones no suma consultas."""
    from apps.paths.models import Milestone
    from apps.progress import services

    url = "/rutas/ia-101/"
    member_client.get(url)
    with CaptureQueriesContext(connection) as before:
        member_client.get(url)
    for m in Milestone.objects.filter(path__slug="ia-101", retired=False)[:6]:
        services.set_milestone(member, m, True)
    with CaptureQueriesContext(connection) as after:
        member_client.get(url)
    assert len(after) <= len(before) + 1


def test_css_hides_svg_text_on_phones_and_shows_the_legend():
    css = (STATIC / "figures.css").read_text(encoding="utf-8")
    assert re.search(r"\.fg-legend\{display:none", css)
    phone = css[css.index("@media (max-width:560px)", css.index(".fg-legend")) :]
    assert ".fg-legend{display:block}" in phone and ".fg text" in phone and ".cv-svg text" in phone
    assert "min-height:44px" in css
    civil = (STATIC / "civil.css").read_text(encoding="utf-8")
    assert ".cv-svg text{display:none}" not in civil
