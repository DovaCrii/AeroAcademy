"""Rutas por área, catálogo sin saturación y foro del equipo (P1-6, P1-7, P1-3)."""

import re

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.catalog.models import Discipline, Platform, Vendor
from apps.community import forum, opinions
from apps.community.models import Category, Thread
from apps.paths import services as path_services
from apps.paths.models import LearningPath

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded(db):
    call_command("seed_catalog", verbosity=0)


def page(client, url):
    r = client.get(url)
    assert r.status_code == 200, url
    return r.content.decode()


# --- /rutas/ por área de aprendizaje --------------------------------------------------------------------------------


def test_every_visible_route_reachable_from_rutas_index(site_world, client_for):
    """Sin filtros, cada ruta que la persona puede ver tiene su enlace en /rutas/ (el lead ve también los borradores)."""
    LearningPath.objects.filter(slug="bim-101").update(is_published=False)
    for key, sees_drafts in (("member", False), ("admin", True)):
        person = site_world[key]
        html = page(client_for(person.login), "/rutas/")
        visible = path_services.visible_paths(person)
        assert visible.count() >= 20
        assert ("/rutas/bim-101/" in html) is sees_drafts
        for slug in visible.values_list("slug", flat=True):
            assert f'href="/rutas/{slug}/"' in html, (key, slug)


def test_every_discipline_with_routes_has_section(site_world, client_for):
    html = page(client_for(site_world["member"].login), "/rutas/")
    for d in Discipline.objects.filter(paths__is_published=True).distinct():
        assert f'id="area-{d.slug}"' in html or d.slug not in {
            a["slug"]
            for a in path_services.group_by_area(
                path_services.visible_paths(site_world["member"]).prefetch_related(
                    "disciplines", "products"
                )
            )
        }, d.slug
    areas = re.findall(r'<section class="area-sec" id="area-([a-z-]+)"', html)
    assert areas[:2] == ["arquitectura", "civil-estructural"]  # orden por área de aprendizaje
    assert "captura-rpa" in areas and "ia-datos" in areas and "transversal" in areas
    assert areas.index("ia-datos") < areas.index("transversal")


def test_dgac_route_is_in_capture_area(site_world, client_for):
    html = page(client_for(site_world["member"].login), "/rutas/")
    capture = html.split('id="area-captura-rpa"')[1].split("</section>")[0]
    assert 'data-slug="dgac-rpas"' in capture


def test_each_route_card_appears_once_in_its_area(site_world, client_for):
    html = page(client_for(site_world["member"].login), "/rutas/")
    areas = re.split(r'<section class="area-sec" id="area-', html)[1:]
    seen = [slug for a in areas for slug in re.findall(r'data-slug="([a-z0-9-]+)"', a)]
    assert len(seen) == len(set(seen)) == path_services.visible_paths(site_world["member"]).count()


def test_start_here_and_my_routes(seeded, member, member_client):
    html = page(member_client, "/rutas/")
    start = html.split('id="empieza-aqui"')[1].split("</section>")[0]
    slugs = re.findall(r'data-slug="([a-z0-9-]+)"', start)
    assert slugs and all(s.endswith("-101") for s in slugs)
    assert 'id="mis-rutas"' not in html  # sin avance no hay «Mis rutas»

    from apps.paths.models import Milestone
    from apps.progress import services as progress

    path = LearningPath.objects.get(slug="topografia-101")
    progress.set_milestone(member, Milestone.objects.filter(path=path, retired=False).first(), True)
    html = page(member_client, "/rutas/")
    mine = html.split('id="mis-rutas"')[1].split("</section>")[0]
    assert 'data-slug="topografia-101"' in mine and "Continuar" in mine
    assert (
        'data-slug="topografia-101"'
        not in html.split('id="empieza-aqui"')[1].split("</section>")[0]
    )


def test_metro_map_link_is_prominent(seeded, member_client):
    html = page(member_client, "/rutas/")
    head = html.split('id="empieza-aqui"')[0]
    assert 'class="map-link"' in head and 'href="/rutas/mapa/"' in head


def test_vendor_is_secondary_filter(seeded, member_client):
    html = page(member_client, "/rutas/")
    assert '<nav class="tabs"' not in html  # ya no hay pestañas por empresa
    filters = html.split('<details class="more-filters"')[1].split("</details>")[0]
    assert 'name="vendor"' in filters and 'name="product"' in filters and 'name="skill"' in filters
    only = page(member_client, "/rutas/?vendor=bentley")
    assert "Ruta Bentley" in only and "Ruta Revit" not in only
    assert "Limpiar" in only and "open" in only.split('<details class="more-filters"')[1][:10]


def test_rutas_index_queries_constant(seeded, member):
    from tests.conftest import tailscale_client

    client = tailscale_client(member.login)
    page(client, "/rutas/")  # calienta cachés

    def count():
        with CaptureQueriesContext(connection) as ctx:
            assert client.get("/rutas/").status_code == 200
        return len(ctx)

    before = count()
    vendor = Vendor.objects.first()
    platform = Platform.objects.first()
    disc = Discipline.objects.get(slug="topografia")
    for i in range(6):
        extra = LearningPath.objects.create(
            slug=f"extra-{i}-101",
            title=f"Extra {i}",
            platform=platform,
            vendor=vendor,
            kind=LearningPath.Kind.STRUCTURED,
            is_published=True,
        )
        extra.disciplines.add(disc)
    assert count() == before


# --- catálogo sin saturación ----------------------------------------------------------------------------------------


def test_catalog_filters_compact(seeded, member_client):
    html = page(member_client, "/catalogo/")
    bar = html.split('<form class="cat-search"')[1].split("</form>")[0]
    main = bar.split('<div class="cat-main-filters">')[1].split("<details")[0]
    assert (
        main.count("<select") == 3 and main.count('type="checkbox"') == 1
    )  # Proveedor, Disciplina, Tipo y Solo esenciales
    assert (
        'name="vendor"' in main
        and 'name="discipline"' in main
        and 'name="kind"' in main
        and 'name="esencial"' in main
    )
    more = bar.split("<details")[1]
    for name in ("ruta", "platform", "cert", "general", "free"):  # lo demás sigue alcanzable
        assert f'name="{name}"' in more, name
    assert 'class="cat-pill' not in html and 'class="cat-tab' not in html
    assert "<optgroup" in more  # la ruta es un select agrupado por disciplina


def test_active_filter_chips_remove_param(seeded, member_client):
    html = page(member_client, "/catalogo/?q=revit&kind=course&esencial=1&cert=1&page=1")
    chips = html.split('class="cat-chips"')[1].split("</ul>")[0]
    links = re.findall(r'href="([^"]*)" title="Quitar este filtro"', chips)
    assert len(links) == 4
    for href, key in zip(links, ("q", "kind", "cert", "esencial"), strict=True):
        assert f"{key}=" not in href and "page=" not in href
        others = {"q", "kind", "esencial", "cert"} - {key}
        assert all(f"{o}=" in href for o in others)
    assert 'href="/catalogo/">Limpiar todo' in chips
    assert page(member_client, "/catalogo/") and "cat-chips" not in page(
        member_client, "/catalogo/"
    )


def test_result_count_is_shown(seeded, member_client):
    html = page(member_client, "/catalogo/?kind=exam")
    assert re.search(r'<p class="cat-count" role="status"><b>\d+</b> resultado', html)


def test_legacy_params_still_work(seeded, member_client):
    from apps.catalog.services import resource_queryset

    ruta = page(member_client, "/catalogo/?ruta=bentley-learn")
    assert '<option value="bentley-learn" selected>' in ruta
    expected = len(resource_queryset(path="bentley-learn"))
    assert f"<b>{expected}</b> resultado" in ruta
    exams = resource_queryset(kind="exam").count()
    assert f"<b>{exams}</b> resultado" in page(member_client, "/catalogo/?kind=exam")
    certs = resource_queryset(cert=True).count()
    assert f"<b>{certs}</b> resultado" in page(member_client, "/catalogo/?cert=1")
    free = resource_queryset(free=True).count()
    assert f"<b>{free}</b> resultado" in page(member_client, "/catalogo/?free=1")
    assert page(member_client, "/catalogo/?software=civil3d")
    assert page(member_client, "/catalogo/?general=1")


def test_discipline_filter(seeded, member_client):
    from apps.catalog.services import resource_queryset

    slug = "topografia"
    n = resource_queryset(discipline=slug).count()
    assert 0 < n < resource_queryset().count()  # filtra por la disciplina de las rutas que lo usan
    titles = {p.title for p in LearningPath.objects.filter(disciplines__slug=slug)}
    assert titles and not resource_queryset(discipline="no-existe").exists()
    html = page(member_client, f"/catalogo/?discipline={slug}")
    assert f"<b>{n}</b> resultado" in html and f'<option value="{slug}" selected>' in html
    assert page(member_client, "/catalogo/?discipline=<script>")  # valor inventado: se ignora


def test_catalog_chip_escapes_search_text(seeded, member_client):
    html = page(member_client, "/catalogo/?q=<script>alert(1)</script>")
    assert "<script>alert(1)</script>" not in html


def test_catalog_queries_constant(seeded, member_client):
    from apps.catalog.models import Platform as P
    from apps.catalog.models import Resource

    page(member_client, "/catalogo/?q=revit")  # calienta cachés

    def count(url):
        with CaptureQueriesContext(connection) as ctx:
            assert member_client.get(url).status_code == 200
        return len(ctx)

    url = "/catalogo/?kind=course&esencial=1&q=revit"
    before_all, before_f = count("/catalogo/"), count(url)
    platform = P.objects.first()
    for i in range(10):
        Resource.objects.create(
            title=f"Revit curso extra {i}",
            platform=platform,
            kind="course",
            url="https://x.example/",
        )
    assert count("/catalogo/") == before_all and count(url) == before_f


# --- foro del equipo ------------------------------------------------------------------------------------------------


TEAM = ["general", "ideas", "ideas-mejoras", "implementacion", "seguimiento"]


def test_forum_seed_has_team_categories(seeded):
    cats = {c.slug: c for c in Category.objects.filter(retired=False)}
    assert len(cats) == 9
    for slug in TEAM + ["autodesk", "bentley", "topografia-captura", "mecanica"]:
        assert slug in cats, slug
    assert cats["ideas-mejoras"].name == "Propuestas y mejoras"
    order = list(
        Category.objects.filter(retired=False).order_by("order").values_list("slug", flat=True)
    )
    assert order[:6] == [
        "general",
        "autodesk",
        "bentley",
        "topografia-captura",
        "mecanica",
        "ideas-mejoras",
    ]  # lo nuevo va al final


def test_poll_category_unchanged(seeded, member):
    assert opinions.POLL_CATEGORY == "ideas-mejoras"
    thread = forum.create_thread(
        member,
        Category.objects.get(slug="ideas-mejoras"),
        Thread.Kind.DISCUSSION,
        "¿Qué curso sigue?",
        "votemos",
        poll_options="Uno\nDos",
    )
    assert thread.poll_options.count() == 2
    with pytest.raises(ValueError, match="Propuestas y mejoras"):
        forum.create_thread(
            member,
            Category.objects.get(slug="ideas"),
            Thread.Kind.DISCUSSION,
            "Idea",
            "x",
            poll_options="a\nb",
        )


@pytest.mark.parametrize("where", ["/foro/", "/"])
def test_forum_index_team_cards_links(site_world, client_for, where):
    html = page(client_for(site_world["member"].login), where)
    section = html.split('id="conversaciones"')[1].split("</section>")[0]
    assert "Conversaciones del equipo" in html
    assert section.count('class="tt-card"') == 5
    names = ["General", "Ideas", "Propuestas y mejoras", "Implementación", "Seguimiento"]
    for slug, name in zip(TEAM, names, strict=True):
        assert f'href="/foro/?categoria={slug}"' in section, slug
        assert f"<b>{name}</b>" in section
    assert "1 hilo" in section  # el hilo de prueba de cada categoría
    assert 'href="/conocimiento/mejoras/"' in section
    assert page(client_for(site_world["member"].login), "/foro/?categoria=seguimiento")


def test_team_cards_do_not_count_hidden_threads(seeded, member, lead):
    cat = Category.objects.get(slug="ideas")
    forum.create_thread(member, cat, Thread.Kind.DISCUSSION, "Visible", "x")
    hidden = forum.create_thread(member, cat, Thread.Kind.DISCUSSION, "Oculto", "x")
    Thread.objects.filter(pk=hidden.pk).update(is_hidden=True)
    count = {c["slug"]: c["count"] for c in forum.team_conversations()}
    assert count["ideas"] == 1
    assert {c["slug"]: c["count"] for c in forum.team_conversations(show_hidden=True)}["ideas"] == 2


def test_team_conversations_queries_constant(seeded, member):
    with CaptureQueriesContext(connection) as ctx:
        forum.team_conversations()
    assert len(ctx) == 2
    for slug in TEAM:
        forum.create_thread(member, Category.objects.get(slug=slug), "discussion", f"T {slug}", "x")
    with CaptureQueriesContext(connection) as ctx2:
        forum.team_conversations()
    assert len(ctx2) == 2
