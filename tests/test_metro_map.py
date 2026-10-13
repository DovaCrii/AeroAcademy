"""Mapa de metro de las rutas y línea de niveles de cada ruta."""

import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.catalog.models import Discipline, Vendor
from apps.paths import metro
from apps.paths.models import LearningPath, Level, Milestone, QuizQuestion
from apps.progress import services as progress

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(db):
    vendor = Vendor.objects.create(slug="v", name="V", order=0)
    arq = Discipline.objects.create(
        slug="arquitectura", name="Arquitectura", default_world="architecture", order=0
    )
    civ = Discipline.objects.create(
        slug="civil-estructural", name="Civil", default_world="civil", order=1
    )
    ia = Discipline.objects.create(
        slug="ia-datos", name="IA y Datos", default_world="civil", order=2
    )

    def make(slug, discs, published=True, levels=2):
        p = LearningPath.objects.create(
            slug=slug,
            title=slug.upper(),
            vendor=vendor,
            world="architecture",
            is_published=published,
        )
        p.disciplines.set(discs)
        for i in range(levels):
            lv = Level.objects.create(
                path=p, code=f"n{i}", order=i, short=f"Nivel {i}", title=f"T{i}"
            )
            Milestone.objects.create(path=p, level=lv, key=f"{slug}-m{i}", order=0, text="m")
        return p

    return {"make": make, "arq": arq, "civ": civ, "ia": ia}


def station(data, slug):
    return next(s for s in data["stations"] if s["slug"] == slug)


def test_map_page_renders_with_lines_and_stations(world, member_client):
    world["make"]("bim-101", [world["arq"], world["civ"]])
    world["make"]("agentes", [world["ia"]])
    r = member_client.get(reverse("paths:map"))
    assert r.status_code == 200
    html = r.content.decode()
    assert "<svg" in html and "Mapa de rutas" in html
    assert 'href="/rutas/bim-101/"' in html and 'href="/rutas/agentes/"' in html
    for name in ("Arquitectura", "Civil", "IA y Datos"):
        assert name in html
    assert "Mapa en texto" in html  # lista para lectores de pantalla


def test_map_empty_without_paths(member_client):
    r = member_client.get(reverse("paths:map"))
    assert r.status_code == 200 and "Todavía no hay rutas" in r.content.decode()


def test_draft_routes_hidden_for_members_visible_for_leads(world, member, lead, client_for):
    world["make"]("publica", [world["arq"]])
    world["make"]("borrador", [world["arq"]], published=False)
    mine = client_for(member.login).get(reverse("paths:map")).content.decode()
    assert "/rutas/publica/" in mine and "/rutas/borrador/" not in mine
    assert "BORRADOR" not in mine
    theirs = client_for(lead.login).get(reverse("paths:map")).content.decode()
    assert "/rutas/borrador/" in theirs


def test_interchange_detection_and_geometry(world, member):
    world["make"]("autocad", [world["arq"], world["civ"]])
    world["make"]("revit", [world["arq"]])
    world["make"]("roads", [world["civ"]])
    data = metro.build_map(member)
    assert station(data, "autocad")["interchange"] is True
    assert station(data, "revit")["interchange"] is False
    assert [s["slug"] for s in data["interchanges"]] == ["autocad"]
    assert data["counts"] == {"lines": 2, "stations": 3, "interchanges": 1, "done": 0}
    # Una sola estación compartida: ambas líneas la contienen en la misma posición.
    lines = {ln.slug: ln for ln in data["lines"]}
    a = [s for s in lines["arquitectura"].stations if s["slug"] == "autocad"][0]
    c = [s for s in lines["civil-estructural"].stations if s["slug"] == "autocad"][0]
    assert a is c
    # Columnas estrictamente crecientes dentro de cada línea (sin estaciones encimadas).
    for ln in data["lines"]:
        cols = [s["x"] for s in ln.stations]
        assert cols == sorted(set(cols))


def test_layout_is_deterministic(world, member):
    for slug, d in (("a", "arq"), ("b", "civ"), ("c", "ia")):
        world["make"](slug, [world[d]])
    world["make"]("x", [world["arq"], world["ia"]])
    first = metro.build_map(member)
    second = metro.build_map(member)
    key = lambda d: [(s["slug"], s["x"], s["top"], s["bottom"]) for s in d["stations"]]  # noqa: E731
    assert key(first) == key(second)
    assert [ln.d for ln in first["lines"]] == [ln.d for ln in second["lines"]]


def test_route_without_discipline_goes_to_other_line(world, member):
    world["make"]("suelta", [])
    data = metro.build_map(member)
    assert [ln.name for ln in data["lines"]] == ["Otras rutas"]


def test_progress_states_and_here_marker(world, member):
    p1 = world["make"]("uno", [world["arq"]])
    p2 = world["make"]("dos", [world["arq"]])
    world["make"]("tres", [world["arq"]])
    for m in Milestone.objects.filter(path=p1):
        progress.set_milestone(member, m, True)
    progress.set_milestone(member, Milestone.objects.filter(path=p2).first(), True)
    data = metro.build_map(member)
    assert station(data, "uno")["state"] == "done" and station(data, "uno")["pct"] == 100
    assert station(data, "dos")["state"] == "progress" and station(data, "dos")["pct"] == 50
    assert station(data, "tres")["state"] == "todo"
    # «Estás aquí»: la ruta en curso con actividad más reciente.
    assert [s["slug"] for s in data["stations"] if s["current"]] == ["dos"]
    assert data["counts"]["done"] == 1


def test_quiz_answers_count_as_progress(world, member):
    p = world["make"]("q", [world["arq"]], levels=1)
    lv = p.levels.first()
    qq = QuizQuestion.objects.create(
        path=p, level=lv, key="q1", order=0, question="?", options=["a", "b"], answer_index=1
    )
    progress.answer_question(member, qq, 1)
    assert station(metro.build_map(member), "q")["pct"] == 50


def test_progress_is_personal(world, member, make_person):
    p = world["make"]("uno", [world["arq"]])
    for m in Milestone.objects.filter(path=p):
        progress.set_milestone(member, m, True)
    other = make_person("otra@lev.cl")
    assert station(metro.build_map(other), "uno")["state"] == "todo"


def test_map_html_marks_state_and_here(world, member, member_client):
    p = world["make"]("uno", [world["arq"]])
    progress.set_milestone(member, Milestone.objects.filter(path=p).first(), True)
    html = member_client.get(reverse("paths:map")).content.decode()
    assert "mm-station progress here" in html and "Estás aquí" in html


def test_map_query_count_does_not_grow(world, member, member_client, django_assert_max_num_queries):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    url = reverse("paths:map")
    world["make"]("p0", [world["arq"]])
    with CaptureQueriesContext(connection) as small:
        assert member_client.get(url).status_code == 200
    for i in range(1, 9):
        p = world["make"](f"p{i}", [world["arq"], world["civ"]] if i % 2 else [world["ia"]])
        progress.set_milestone(member, Milestone.objects.filter(path=p).first(), True)
    with CaptureQueriesContext(connection) as big:
        assert member_client.get(url).status_code == 200
    assert len(big) <= len(small) + 1  # (+1: el aviso de la primera marca no cuenta; margen mínimo)


def test_map_with_real_seed(member_client):
    call_command("seed_catalog", verbosity=0)
    r = member_client.get(reverse("paths:map"))
    assert r.status_code == 200
    assert "Topografía" in r.content.decode()


def test_level_line_links_each_level(world, member, member_client):
    p = world["make"]("bim-101", [world["arq"]], levels=3)
    progress.set_milestone(member, Milestone.objects.filter(path=p, level__code="n0").first(), True)
    html = member_client.get(reverse("paths:detail", args=[p.slug])).content.decode()
    assert 'class="ll"' in html
    for code in ("n0", "n1", "n2"):
        assert f'href="/rutas/bim-101/?nivel={code}#panel"' in html
        assert f'data-fid="ll-{code}"' in html
    assert 'id="panel"' in html  # no rompe el panel existente
    assert "ll-scroll" in html and "done" in html


def test_level_line_hidden_for_single_level(world, member_client):
    p = world["make"]("solo", [world["arq"]], levels=1)
    html = member_client.get(reverse("paths:detail", args=[p.slug])).content.decode()
    assert 'class="ll"' not in html


def test_paths_index_links_to_map(world, member_client):
    world["make"]("uno", [world["arq"]])
    assert reverse("paths:map") in member_client.get(reverse("paths:index")).content.decode()


def test_lines_are_straight_and_capsule_per_interchange(world, member):
    world["make"]("autocad", [world["arq"], world["civ"]])
    world["make"]("revit", [world["arq"]])
    world["make"]("roads", [world["civ"]])
    world["make"]("bim", [world["arq"], world["civ"], world["ia"]])
    data = metro.build_map(member)
    for ln in data["lines"]:
        pts = ln.d.replace("M", "").split("L")
        assert len(pts) == 2
        assert len({p.split()[1] for p in pts}) == 1  # una sola y: vía recta
    for s in data["interchanges"]:
        assert s["capsules"] and len(s["lines"]) >= 2
        assert s["top"] < s["bottom"]
    assert all(not s["interchange"] for s in data["stations"] if s["top"] == s["bottom"])


def test_stations_never_share_a_cell(world, member):
    for i in range(6):
        world["make"](f"r{i}", [world["arq"], world["civ"]] if i % 2 else [world["ia"]])
    data = metro.build_map(member)
    seen = set()
    for s in data["stations"]:
        for r in range(s["lines"][0].row, s["lines"][-1].row + 1):
            assert (s["col"], r) not in seen
            seen.add((s["col"], r))


def test_row_order_keeps_sharing_lines_adjacent():
    order = metro.best_row_order(
        ["a", "b", "c", "d"],
        {frozenset({"a", "d"}): 3, frozenset({"b"}): 1},
    )
    assert abs(order.index("a") - order.index("d")) == 1


def test_real_seed_map_is_compact(member_client):
    import re

    call_command("seed_catalog", verbosity=0)
    r = member_client.get(reverse("paths:map"))
    assert r.status_code == 200
    width = int(re.search(r'viewBox="0 0 (\d+) ', r.content.decode()).group(1))
    assert width <= 1400
