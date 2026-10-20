"""Plataformas oficiales (D43): Bentley y Autodesk, con Bentley primero, y el avance de QUIEN MIRA.

Orden de áreas y filtro, marca «Plataforma oficial», avance con credenciales verificadas, pendientes y rechazadas,
«Siguiente sugerido», privacidad entre personas, portada con y sin avance, consultas acotadas y escape de texto.
"""

import re

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils.html import escape

from apps.catalog import official, services, software
from apps.catalog.models import Platform, Resource
from apps.credentials.models import Credential
from apps.paths.models import ExternalCourse, LearningPath, LevelResource

pytestmark = pytest.mark.django_db

OK, PEND, REJ = Credential.Status.VERIFIED, Credential.Status.PENDING, Credential.Status.REJECTED


@pytest.fixture(autouse=True)
def seeded():
    call_command("seed_catalog", verbosity=0)


def page(client, url="/catalogo/"):
    r = client.get(url)
    assert r.status_code == 200, url
    return r.content.decode()


def main_of(html):
    return html.split("<main")[1]


def cred(owner, resource, status):
    """Credencial de prueba (sin archivo real: el avance solo mira dueño, curso y estado)."""
    return Credential.objects.create(
        owner=owner,
        title=resource.title,
        resource=resource,
        status=status,
        file="credentials/prueba.pdf",
    )


def data():
    paths = list(
        LearningPath.objects.filter(is_published=True)
        .select_related("vendor")
        .prefetch_related("products")
    )
    every = list(services.resource_queryset())
    links = services.published_path_links()
    areas = software.areas_of(every, paths, links, set(services.general_ids()))
    return every, areas, paths, links


def of_area(area):
    every, areas, _paths, _links = data()
    return sorted((r for r in every if areas[r.pk] == area), key=official._relevance)


def bentley_starters():
    every, areas, _paths, _links = data()
    sections = software.vendor_sections(software.group_by_software(every, areas=areas))
    return next(s for s in sections if s["key"] == "bentley")["starters"]


def summary(person):
    every, areas, paths, links = data()
    states = official.credential_services.states_by_resource(person)
    return official.progress(every, areas, states, paths, links)


# ---- orden y marca -------------------------------------------------------------------------------------------


def test_areas_are_ordered_bentley_first_everywhere(member_client):
    html = page(member_client)
    nav = html.split('aria-label="Mapa del catálogo"')[1].split("</nav>")[0]
    hrefs = re.findall(r'href="#([a-z-]+)"', nav)
    assert hrefs == [
        "vendor-bentley",
        "vendor-autodesk",
        "vendor-ia",
        "vendor-internal",
        "conocimiento-general",
    ]
    main = main_of(html)
    positions = [main.index(f'id="{key}"') for key in hrefs]
    assert positions == sorted(positions)  # las secciones siguen el orden del mapa
    select = html.split('<select name="vendor">')[1].split("</select>")[0]
    assert re.findall(r'<option value="([a-z]*)"', select) == [
        "",
        "bentley",
        "autodesk",
        "ia",
        "internal",
        "general",
    ]


def test_old_vendor_urls_and_anchors_still_work(member_client):
    for key in ("autodesk", "bentley", "ia", "internal", "general"):
        assert page(member_client, f"/catalogo/?vendor={key}")
    assert 'id="sw-revit"' in page(member_client, "/catalogo/?vendor=autodesk")
    assert "MicroStation" in page(member_client, "/catalogo/?software=microstation")
    assert 'id="vendor-autodesk"' in page(member_client) and 'id="vendor-bentley"' in page(
        member_client
    )


def test_only_bentley_and_autodesk_carry_the_official_mark(member_client):
    html = page(member_client)
    nav = html.split('aria-label="Mapa del catálogo"')[1].split("</nav>")[0]
    assert nav.count("Plataforma oficial") == 2
    assert nav.index("Plataforma oficial") < nav.index("Autodesk")  # la primera es la de Bentley
    for key, mark in (("bentley", 1), ("autodesk", 1), ("ia", 0), ("internal", 0)):
        area = html.split(f'id="vendor-{key}"')[1].split("</section>")[0]
        assert area.count("Plataforma oficial") == mark, key
    assert "Plataforma oficial" not in html.split('id="conocimiento-general"')[1]
    view = page(member_client, "/catalogo/?vendor=bentley")
    assert "Plataforma oficial" in view
    assert "Plataforma oficial" not in page(member_client, "/catalogo/?vendor=ia")


# ---- avance: credenciales verificadas, pendientes y rechazadas -----------------------------------------------


def test_progress_counts_verified_pending_and_rejected(member):
    items = of_area("bentley")
    cred(member, items[0], OK)
    cred(member, items[1], OK)
    cred(member, items[2], PEND)
    cred(member, items[3], REJ)  # rechazada: sigue por hacer
    cred(member, items[4], REJ)
    cred(member, items[4], PEND)  # la mejor credencial gana: en revisión
    p = summary(member)["bentley"]
    assert p["total"] == len(items) == 51
    assert (p["done"], p["review"]) == (2, 2)
    assert p["pct"] == official.percent(2, 51) == 4
    assert p["started"] is True
    assert p["essential_total"] == len([r for r in items if official.is_essential(r)])
    essential_done = len([r for r in items[:2] if official.is_essential(r)])
    assert p["essential_done"] == essential_done
    assert summary(member)["autodesk"]["done"] == 0  # el avance de otra plataforma no se mezcla


def test_progress_uses_the_same_done_rule_as_external_routes(member):
    """Verificada = hecho; pendiente = en revisión: igual que `progress/external.py`."""
    from apps.credentials import services as credential_services

    item = of_area("bentley")[0]
    cred(member, item, PEND)
    states = credential_services.states_by_resource(member)
    assert official.state_of(states, item.pk) == official.REVIEW
    Credential.objects.filter(owner=member).update(status=OK)
    states = credential_services.states_by_resource(member)
    assert official.state_of(states, item.pk) == official.DONE
    Credential.objects.filter(owner=member).update(status=REJ)
    states = credential_services.states_by_resource(member)
    assert official.state_of(states, item.pk) == official.TODO


def test_catalog_shows_numbers_bar_and_essentials(member, member_client):
    items = of_area("bentley")
    for r in items[:3]:
        cred(member, r, OK)
    html = page(member_client)
    area = html.split('id="vendor-bentley"')[1].split("</section>")[0]
    assert "<b>3 de 51</b> cursos · 6 %" in area
    assert "Esenciales: <b>" in area
    bar = re.search(r'<progress class="of-bar" max="51" value="3" aria-label="([^"]+)">', area)
    assert bar and "3 de 51 cursos" in bar.group(1) and "6 por ciento" in bar.group(1)
    nav = html.split('aria-label="Mapa del catálogo"')[1].split("</nav>")[0]
    assert re.search(
        r'<progress class="of-bar" max="51" value="3" aria-label="[^"]*">6 %</progress>', nav
    )
    assert "<b>3 de 51</b> cursos · 6 %" in nav
    assert "<b>0 de" not in html and "0 de 123" not in html  # sin ceros fríos
    other = html.split('id="vendor-ia"')[1].split("</section>")[0]
    assert "of-bar" not in other and "Siguiente sugerido" not in other  # solo las oficiales


def test_vendor_view_shows_the_panel_too(member, member_client):
    cred(member, of_area("autodesk")[0], OK)
    html = page(member_client, "/catalogo/?vendor=autodesk")
    assert "<b>1 de 123</b> cursos" in html and "Siguiente sugerido" in html
    assert "Esenciales:" in html
    assert "of-bar" not in page(member_client, "/catalogo/?vendor=ia")


# ---- siguiente sugerido --------------------------------------------------------------------------------------


def test_next_is_the_pending_essential_and_never_a_done_one(member):
    items = of_area("bentley")
    essentials = [r for r in items if official.is_essential(r)]
    assert len(essentials) >= 3
    first = summary(member)["bentley"]["next"]
    assert first["essential"] is True and first["resource"] in essentials
    assert first["path"] is not None
    cred(member, first["resource"], OK)
    second = summary(member)["bentley"]["next"]
    assert second["resource"] != first["resource"] and second["essential"] is True
    cred(member, second["resource"], PEND)  # en revisión tampoco se sugiere
    third = summary(member)["bentley"]["next"]
    assert third["resource"] not in (first["resource"], second["resource"])
    cred(member, third["resource"], REJ)  # rechazada: se vuelve a sugerir
    assert summary(member)["bentley"]["next"]["resource"] == third["resource"]


def test_next_moves_on_to_other_courses_when_essentials_are_done(member):
    items = of_area("autodesk")
    for r in items:
        if official.is_essential(r):
            cred(member, r, OK)
    nxt = summary(member)["autodesk"]["next"]
    assert nxt and nxt["essential"] is False
    p = summary(member)["autodesk"]
    assert p["essential_done"] == p["essential_total"] > 0


def test_nothing_next_when_everything_is_done_or_in_review(member, member_client):
    for i, r in enumerate(of_area("bentley")):
        cred(member, r, OK if i % 2 else PEND)
    p = summary(member)["bentley"]
    assert p["next"] is None and p["done"] + p["review"] == p["total"]
    html = page(member_client)
    area = html.split('id="vendor-bentley"')[1].split("</section>")[0]
    assert "Todo al día" in area and "Siguiente sugerido" not in area


def test_next_has_a_link(member, member_client):
    nxt = summary(member)["bentley"]["next"]
    area = page(member_client).split('id="vendor-bentley"')[1].split("</section>")[0]
    link = re.search(r'<p class="of-next-t"><a href="([^"]+)"', area)
    assert link
    assert link.group(1) == escape(nxt["resource"].url)  # el curso sugerido, no otro
    assert f'href="/rutas/{nxt["path"].slug}/"' in area  # y su ruta


# ---- privacidad: solo el avance de quien mira ---------------------------------------------------------------


def test_progress_of_another_person_never_shows(member, member_client, make_person, client_for):
    other = make_person("otra@example.com")
    for r in of_area("bentley")[:5]:
        cred(other, r, OK)
    mine = page(member_client)
    assert "5 de 51" not in mine and "<b>0 de" not in mine
    assert "Empieza por lo esencial" in mine
    theirs = page(client_for("otra@example.com"))
    assert "<b>5 de 51</b> cursos" in theirs
    home_mine = page(member_client, "/")
    assert "5 de 51" not in home_mine
    assert "5 de 51" in page(client_for("otra@example.com"), "/")
    assert Credential.objects.filter(owner=member).count() == 0


def test_card_states_are_only_mine(member, member_client, make_person, client_for):
    other = make_person("otra@example.com")
    starters = bentley_starters()
    cred(other, starters[0], OK)
    assert "chip st st-done" not in page(member_client)
    cred(member, starters[0], OK)
    cred(member, starters[1], PEND)
    html = main_of(page(member_client))
    area = html.split('id="vendor-bentley"')[1].split("</section>")[0]
    assert area.count("chip st st-done") == 1 and area.count("chip st st-review") == 1
    assert area.count("chip st st-todo") == 6  # 8 tarjetas de Bentley
    assert "✓ </span>Hecho" in area and "En revisión</span>" in area and "Por hacer</span>" in area
    ia = html.split('id="vendor-ia"')[1].split("</section>")[0]
    assert "chip st" not in ia  # las demás áreas no llevan estado


def test_cards_mark_essentials_in_official_areas(member_client):
    area = page(member_client).split('id="vendor-bentley"')[1].split("</section>")[0]
    assert 'class="chip ess"' in area  # «Esencial» con texto, no solo color
    assert "of-mark" in area


# ---- persona sin avance: primer paso, no ceros ---------------------------------------------------------------


def test_person_without_credentials_sees_the_first_step(member_client):
    html = page(member_client)
    area = html.split('id="vendor-bentley"')[1].split("</section>")[0]
    assert "Aún no empiezas aquí" in area and "Primer paso sugerido" in area
    assert "of-bar" not in area and "0 %" not in area
    assert "51 cursos" in area
    nav = html.split('aria-label="Mapa del catálogo"')[1].split("</nav>")[0]
    assert "Empieza por lo esencial" in nav and "of-bar" not in nav


# ---- portada -------------------------------------------------------------------------------------------------


def test_home_strip_without_progress(member_client):
    html = main_of(page(member_client, "/"))
    assert 'id="oficiales"' in html and "Tus plataformas oficiales" in html
    strip = html.split('id="oficiales"')[1].split("</section>")[0]
    assert strip.index("<h3>Bentley Systems") < strip.index("<h3>Autodesk")
    assert strip.count("Empezar con") == 2 and "Seguir con" not in strip
    assert "Aún no empiezas aquí" in strip and "of-bar" not in strip
    assert strip.count("Plataforma oficial") == 2
    assert (
        'href="/catalogo/?vendor=bentley"' in strip and 'href="/catalogo/?vendor=autodesk"' in strip
    )


def test_home_strip_with_progress(member, member_client):
    cred(member, of_area("bentley")[0], OK)
    cred(member, of_area("autodesk")[0], OK)
    cred(member, of_area("autodesk")[1], OK)
    strip = main_of(page(member_client, "/")).split('id="oficiales"')[1].split("</section>")[0]
    assert "<b>1 de 51</b> cursos · 2 %" in strip
    assert "<b>2 de 123</b> cursos · 2 %" in strip
    assert strip.count("Seguir con") == 2 and "Empezar con" not in strip
    assert re.search(
        r'<progress class="of-bar" max="51" value="1" aria-label="[^"]*51 cursos', strip
    )
    assert strip.count("Esenciales:") == 2


def test_home_strip_sits_below_the_welcome_block_and_suite_stays_hidden(member_client):
    html = page(member_client, "/")
    main = main_of(html)
    assert main.index('id="inicio"') < main.index('id="oficiales"') < main.index('id="rutas"')
    assert 'id="suite"' not in html  # «Suite Aero» sigue oculto


def test_home_strip_is_hidden_without_a_catalog(member_client):
    LevelResource.objects.all().delete()
    ExternalCourse.objects.all().delete()
    Resource.objects.all().delete()
    html = page(member_client, "/")
    assert 'id="oficiales"' not in html


# ---- consultas acotadas, escape, accesibilidad ---------------------------------------------------------------


def grow(member):
    """Más recursos, rutas y credenciales (también duplicadas): las consultas no deben crecer."""
    extra = Platform.objects.get(slug="bentley-learn")
    level = LearningPath.objects.get(slug="ia-101").levels.first()
    for i in range(25):
        r = Resource.objects.create(
            platform=extra, title=f"MicroStation curso {i}", tags=["Esencial"]
        )
        LevelResource.objects.create(level=level, resource=r)
        cred(member, r, OK if i % 2 else PEND)
        cred(member, r, PEND)  # duplicada: la mejor gana
    path = LearningPath.objects.get(slug="ia-101")
    for slug in ("copia-a", "copia-b"):
        clone = LearningPath.objects.create(slug=slug, title=slug, vendor=path.vendor)
        lvl = clone.levels.create(code="n0", order=0, short="N0", title="N0")
        LevelResource.objects.create(level=lvl, resource=Resource.objects.order_by("pk").first())


def test_catalog_and_home_queries_do_not_grow_with_data(member, member_client):
    urls = ["/catalogo/", "/catalogo/?vendor=bentley", "/catalogo/?software=microstation", "/"]

    def counts():
        out = []
        for url in urls:
            with CaptureQueriesContext(connection) as ctx:
                assert member_client.get(url).status_code == 200
            out.append(len(ctx))
        return out

    counts()
    before = counts()
    assert before[0] <= 55  # techo de /catalogo/ con el seguimiento (hoy 44)
    grow(member)
    assert counts() == before


def test_titles_and_next_course_are_escaped(member, member_client):
    bad = "<script>alert(1)</script>"
    level = LearningPath.objects.get(slug="ia-101").levels.first()
    r = Resource.objects.create(
        platform=Platform.objects.get(slug="bentley-learn"),
        title=f"{bad} MicroStation introduction",
        description=bad,
        tags=["Esencial"],
        is_official=True,
        url="https://example.com/curso",
    )
    LevelResource.objects.create(level=level, resource=r)
    nxt = summary(member)["bentley"]["next"]["resource"]
    assert nxt == r  # esencial, básico y oficial: el primero sugerido
    for url in ("/", "/catalogo/", "/catalogo/?vendor=bentley", "/catalogo/?q=alert"):
        html = page(member_client, url)
        assert bad not in html, url
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page(member_client, "/catalogo/")
    cred(member, r, OK)
    assert "&lt;script&gt;" in page(member_client, "/catalogo/?vendor=bentley")


def test_progress_bars_are_accessible_without_color(member, member_client):
    for r in of_area("bentley")[:2]:
        cred(member, r, OK)
    cred(member, of_area("autodesk")[0], OK)
    html = page(member_client)
    bars = re.findall(r"<progress[^>]*>[^<]*</progress>", html)
    assert len(bars) >= 3  # mapa (2) y bandas (2)
    for bar in bars:
        assert 'max="' in bar and 'value="' in bar and 'aria-label="' in bar
        assert re.search(r"\d+ de \d+ cursos", bar)
        assert re.search(r">\d+ %</progress>", bar)  # texto de reserva
    assert "<b>2 de 51</b> cursos · 4 %" in html  # el número también va escrito, no solo la barra


def test_official_css_uses_only_tokens():
    from pathlib import Path

    css = (Path(official.__file__).parent / "static" / "catalog" / "official.css").read_text(
        encoding="utf-8"
    )
    assert not re.search(r"#[0-9A-Fa-f]{3,8}\b", css)
    assert "rgb(" not in css and "rgba(" not in css
