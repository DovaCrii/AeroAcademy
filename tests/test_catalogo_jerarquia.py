"""Jerarquía del catálogo (docs/MEJORAS_CATALOGO.md): área de cada recurso, mapa, vista por proveedor y consultas."""

import re

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.catalog import services, software
from apps.catalog.models import Platform, Resource
from apps.paths.models import LearningPath, LevelResource

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded():
    call_command("seed_catalog", verbosity=0)


def page(client, url):
    r = client.get(url)
    assert r.status_code == 200, url
    return r.content.decode()


def count_of(html):
    return int(re.search(r'<p class="cat-count" role="status"><b>(\d+)</b>', html).group(1))


def area_data():
    paths = list(
        LearningPath.objects.filter(is_published=True)
        .select_related("vendor")
        .prefetch_related("products")
    )
    every = list(services.resource_queryset())
    areas = software.areas_of(
        every, paths, services.published_path_links(), set(services.general_ids())
    )
    return every, areas


# ---- P0-1 · servicio ----------------------------------------------------------------------------------------


def test_every_resource_has_an_area(seeded):
    every, areas = area_data()
    assert len(every) > 300
    assert set(areas) == {r.pk for r in every}
    assert set(areas.values()) <= set(software.AREA_ORDER)


def test_catalog_map_totals_match_queryset(seeded):
    every, areas = area_data()
    area_map = software.catalog_map(every, areas)
    assert [a["key"] for a in area_map] == [
        "autodesk", "bentley", "ia", "internal", "general",
    ]  # fmt: skip
    assert sum(a["total"] for a in area_map) == services.resource_queryset().count()
    by_key = {a["key"]: a for a in area_map}
    assert by_key["ia"]["total"] >= 139  # antes invisible: sus recursos no traen producto
    assert by_key["bentley"]["total"] == 51 and len(by_key["bentley"]["products"]) == 10
    assert by_key["autodesk"]["anchor"] == "vendor-autodesk"
    assert by_key["general"]["anchor"] == "conocimiento-general" and by_key["general"]["total"] > 0
    assert all(p["total"] for a in area_map for p in a["products"])  # sin productos vacíos


def test_resources_without_product_go_to_a_more_row(seeded):
    every, areas = area_data()
    rows = software.group_by_software(every, areas=areas)
    by_key = {r["key"]: r for r in rows}
    assert by_key["more-autodesk"]["total"] == 13 and by_key["more-autodesk"]["tile"] is None
    assert by_key["more-ia"]["total"] >= 139
    assert by_key["more-autodesk"]["name"] == "Más de Autodesk"
    keys = [r["key"] for r in rows if r["family"] == software.AUTODESK]
    assert keys[-1] == "more-autodesk"  # al final de su área
    # sin `areas` el comportamiento anterior: los recursos sin mosaico quedan fuera
    assert all(r["tile"] for r in software.group_by_software(every))


def test_starters_one_per_product_round_robin(seeded):
    every, areas = area_data()
    rows = software.group_by_software(every, areas=areas)
    sections = software.vendor_sections(rows)
    bentley = next(s for s in sections if s["key"] == "bentley")
    assert len(bentley["starters"]) == 4
    first = [r["items"][0] for r in bentley["rows"][:4]]
    assert bentley["starters"] == first  # uno por producto, no 4 de MicroStation
    assert len({software.software_for_resource(r, 1)[0].slug for r in bentley["starters"]}) == 4
    ia = next(s for s in sections if s["key"] == "ia")
    assert len(ia["starters"]) == 4  # una sola fila: las rondas siguientes la completan
    assert [s["key"] for s in sections] == ["autodesk", "bentley", "ia", "internal"]
    assert not hasattr(software, "FEATURED") and "shelves" not in bentley


def test_vendor_param_filters_rows(seeded, member_client):
    html = page(member_client, "/catalogo/?vendor=bentley")
    assert 'id="sw-microstation"' in html and 'id="sw-revit"' not in html
    assert 'class="vs vs-bentley"' in html and 'class="vs vs-autodesk"' not in html
    assert 'id="sw-more-autodesk"' not in html
    ia = page(member_client, "/catalogo/?vendor=ia")
    assert 'id="sw-more-ia"' in ia
    assert "Más de IA y Datos" in ia


def test_vendor_param_ignores_garbage(seeded, member_client):
    for value in ("<script>", "nada", "BENTLEY", ""):
        html = page(member_client, f"/catalogo/?vendor={value}")
        assert "<script>alert" not in html
        assert (
            'id="mapa"' in html and 'id="sw-revit"' not in html
        )  # sin proveedor válido: la portada
    escaped = page(member_client, "/catalogo/?vendor=<script>alert(1)</script>")
    assert "<script>alert(1)</script>" not in escaped


@pytest.mark.parametrize(
    "query",
    [
        "q=revit",
        "software=civil3d",
        "ruta=bentley-learn",
        "kind=exam",
        "cert=1",
        "free=1",
        "general=1",
        "esencial=1",
        "discipline=topografia",
        "platform=bentley-learn",
        "todo=1",
        "todo=1&page=2",
    ],
)
def test_legacy_params_unchanged(seeded, member_client, query):
    """Cada parámetro de antes sigue dando el mismo conjunto de resultados que su consulta."""
    params = dict(p.split("=") for p in query.split("&"))
    kwargs = {
        "q": params.get("q", ""),
        "path": params.get("ruta", ""),
        "kind": params.get("kind", ""),
        "cert": params.get("cert") == "1",
        "free": params.get("free") == "1",
        "general": params.get("general") == "1",
        "essential": params.get("esencial") == "1",
        "discipline": params.get("discipline", ""),
        "platform": params.get("platform", ""),
    }
    if "software" in params:
        every = list(services.resource_queryset())
        kwargs["ids"] = software.resource_ids_for_software(every, params["software"])
    expected = services.resource_queryset(**kwargs).count()
    assert count_of(page(member_client, f"/catalogo/?{query}")) == expected


def test_software_page_has_48_and_vendor_crumbs(seeded, member_client):
    html = page(member_client, "/catalogo/?software=microstation")
    cards = html.split("<main")[1].count('<article class="cat-card')
    assert cards == 27  # el producto más grande cabe entero (antes 24 + otra página)
    assert 'class="pager"' not in html
    crumbs = html.split('aria-label="Migas de pan"')[1].split("</nav>")[0]
    assert "Catálogo" in crumbs and "Bentley Systems" in crumbs and "MicroStation" in crumbs
    assert 'href="?vendor=bentley"' in crumbs


def test_catalog_queries_bounded(seeded, member_client):
    urls = ["/catalogo/", "/catalogo/?vendor=bentley", "/catalogo/?software=microstation"]

    def counts():
        out = []
        for url in urls:
            with CaptureQueriesContext(connection) as ctx:
                assert member_client.get(url).status_code == 200
            out.append(len(ctx))
        return out

    counts()  # calienta cachés
    before = counts()
    assert before[0] <= 45  # el techo de antes de la reforma
    extra_platform = Platform.objects.get(slug="autodesk-learning")
    path = LearningPath.objects.get(slug="ia-101")
    level = path.levels.first()
    for i in range(30):
        r = Resource.objects.create(platform=extra_platform, title=f"Revit curso {i}")
        LevelResource.objects.create(level=level, resource=r)
    for slug in ("copia-a", "copia-b"):
        clone = LearningPath.objects.create(slug=slug, title=slug, vendor=path.vendor)
        lvl = clone.levels.create(code="n0", order=0, short="N0", title="N0")
        LevelResource.objects.create(level=lvl, resource=Resource.objects.order_by("pk").first())
    assert counts() == before


# ---- P0-2 · portada: cabecera con búsqueda, mapa y áreas cortas -------------------------------------------------


def main_of(html):
    return html.split("<main")[1]


def test_catalog_has_map_with_all_areas(seeded, member_client):
    html = page(member_client, "/catalogo/")
    nav = html.split('aria-label="Mapa del catálogo"')[1].split("</nav>")[0]
    keys = (
        "vendor-autodesk",
        "vendor-bentley",
        "vendor-ia",
        "vendor-internal",
        "conocimiento-general",
    )
    for key in keys:
        assert f'href="#{key}"' in nav, key
        assert f'id="{key}"' in html, key  # la ancla existe en la página
    labels = ("Autodesk", "Bentley Systems", "IA y Datos", "Topografía, GIS y captura")
    for label in (*labels, "Conocimiento general"):
        assert label in nav
    totals = [int(n) for n in re.findall(r"<small>(\d+) recurso", nav)]
    assert sum(totals) == services.resource_queryset().count() and len(totals) == 5
    assert 'href="#mapa"' in html  # «Volver al mapa»


def test_area_links_to_vendor_view(seeded, member_client):
    html = page(member_client, "/catalogo/")
    for key in ("autodesk", "bentley", "ia", "internal"):
        assert f'href="?vendor={key}"' in html, key
    assert 'href="?software=microstation"' in html  # chip de producto
    assert 'href="?vendor=general"' in html
    assert 'class="cat-row' not in html and "vs-pack" not in html  # el detalle vive en ?vendor=
    area = html.split('id="vendor-bentley"')[1].split("</section>")[0]
    assert "Para empezar" in area and area.count("<article") == 4


def test_vendor_view_has_breadcrumb(seeded, member_client):
    html = page(member_client, "/catalogo/?vendor=bentley")
    crumbs = html.split('aria-label="Migas de pan"')[1].split("</nav>")[0]
    assert "Catálogo" in crumbs and 'aria-current="page">Bentley Systems' in crumbs
    assert 'class="vs-pack"' in html and 'href="#sw-microstation"' in html  # índice de anclas
    assert "Quitar el filtro Bentley Systems" in html  # chip activo
    assert 'aria-label="Migas de pan"' not in page(member_client, "/catalogo/")


def test_search_form_is_first_form(seeded, member_client):
    main = main_of(page(member_client, "/catalogo/"))
    assert main.index('role="search"') < main.index('aria-label="Mapa del catálogo"')
    assert main.count('role="search"') == 1
    assert "Buscar y filtrar" not in main


def test_catalog_card_count_bounded(seeded, member_client):
    html = page(member_client, "/catalogo/")
    assert html.count('<article class="cat-card') <= 24
    assert html.count("<img") <= 60 and len(html.encode()) <= 80 * 1024
    assert html.count("cat-count") == 0  # «N resultados» solo con filtros
    assert "cat-count" in page(member_client, "/catalogo/?kind=exam")


def test_old_anchors_and_links_keep_working(seeded, member_client):
    html = page(member_client, "/catalogo/")
    for key in ("autodesk", "bentley", "ia", "internal"):
        assert f'id="vendor-{key}"' in html
    rows = page(member_client, "/catalogo/?vendor=autodesk")
    assert 'id="vendor-autodesk"' in rows and 'id="sw-revit"' in rows
    assert 'id="sw-more-autodesk"' in rows
    assert page(member_client, "/catalogo/?q=revit&software=revit")  # combinaciones de antes


# ---- P1-1 · tarjeta compacta y chips con información -------------------------------------------------------------


def first_compact(html):
    return html.split('<article class="cat-card cat-compact')[1].split("</article>")[0]


def test_compact_card_order(seeded, member_client):
    card = first_compact(page(member_client, "/catalogo/?vendor=bentley"))
    assert card.index("<h3") < card.index('class="cat-meta"') < card.index('class="chips"')
    assert "cat-thumb" not in card and "cat-desc" not in card  # sin banda ni descripción
    assert card.count('class="chip') <= 3


def test_no_free_chip_and_paid_chip(seeded, member_client):
    paid = Resource.objects.filter(is_free=False)
    assert paid.exists()  # hay recursos de pago en el semillero
    word = paid.first().title.split()[0]
    for url in (
        "/catalogo/",
        "/catalogo/?vendor=bentley",
        "/catalogo/?todo=1",
        f"/catalogo/?q={word}",
    ):
        html = main_of(page(member_client, url))
        assert '<span class="chip">Gratuito</span>' not in html, url
        assert '<span class="chip off">Oficial</span>' not in html, url
    everything = ""
    for n in range(1, 17):
        everything += main_of(page(member_client, f"/catalogo/?todo=1&page={n}"))
    assert everything.count('<span class="chip paid">De pago</span>') >= paid.count()
    legend = page(member_client, "/catalogo/").split('class="cat-legend"')[1]
    assert "De pago" in legend and "Oficial" not in legend and "Gratuito</span>" not in legend


def test_xp_chip_still_shown(seeded, member_client):
    html = page(member_client, "/catalogo/?vendor=bentley")
    assert re.search(r'class="chip xp"[^>]*>\+\d+ XP', html)  # D33: el XP sigue visible
    full = page(member_client, "/catalogo/?cert=1")
    assert re.search(r'class="chip xp"[^>]*>\+\d+ XP', full) and 'class="chip cert"' in full


def test_card_fields_are_escaped(seeded, member_client):
    bad = "<script>alert(1)</script>"
    level = LearningPath.objects.get(slug="ia-101").levels.first()
    r = Resource.objects.create(
        platform=Platform.objects.get(slug="anthropic-academy"),
        title=bad,
        description=bad,
        duration_text=bad,
        tags=["Esencial"],
        is_official=True,
        is_free=False,
    )
    LevelResource.objects.create(level=level, resource=r)
    for url in ("/catalogo/", "/catalogo/?vendor=ia", "/catalogo/?q=alert", f"/catalogo/?q={bad}"):
        html = page(member_client, url)
        assert bad not in html, url
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page(member_client, "/catalogo/?vendor=ia")


# ---- P1-2 · filtro «Proveedor» ---------------------------------------------------------------------------------


def test_vendor_filter_lists_areas_with_totals(seeded, member_client):
    html = page(member_client, "/catalogo/")
    select = html.split('<select name="vendor">')[1].split("</select>")[0]
    assert '<option value="">Todos</option>' in select
    for key in ("autodesk", "bentley", "ia", "internal", "general"):
        assert f'<option value="{key}">' in select
    assert "Bentley Systems (51)" in select
    assert html.index('name="vendor"') < html.index('name="discipline"')  # primero de la fila


def test_vendor_combines_with_other_filters(seeded, member_client):
    every, areas = area_data()
    kind = sorted({r.kind for r in every if areas[r.pk] == "bentley"})[0]
    expected = len([r for r in every if areas[r.pk] == "bentley" and r.kind == kind])
    html = page(member_client, f"/catalogo/?vendor=bentley&kind={kind}")
    assert count_of(html) == expected and expected > 0
    assert 'id="sw-microstation"' not in html  # con otro filtro es la rejilla, no las filas
    q = page(member_client, "/catalogo/?vendor=bentley&q=microstation")
    assert 0 < count_of(q) < 51
    selected = html.split('<select name="vendor">')[1].split("</select>")[0]
    assert '<option value="bentley" selected>' in selected


def test_vendor_chip_removes_param(seeded, member_client):
    html = page(member_client, "/catalogo/?vendor=bentley&kind=exam&page=1")
    chips = html.split('class="cat-chips"')[1].split("</ul>")[0]
    links = re.findall(r'href="([^"]*)" title="Quitar este filtro"', chips)
    assert len(links) == 2
    assert "vendor=" not in links[0] and "kind=exam" in links[0]  # el chip de proveedor va primero
    assert "kind=" not in links[1] and "vendor=bentley" in links[1]
    assert "Bentley Systems" in chips
