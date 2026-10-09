"""Rutas de conocimiento general (Topografía 101, BIM 101…): logros, títulos, «Próximo logro» y catálogo.

Las rutas se arman aquí (no dependen de las semillas de `seed/rutas`, que otros agentes editan); las insignias y los
títulos sí salen del `seed/` real, que es lo que se está probando.
"""

import json
from pathlib import Path

import pytest
from django.conf import settings as dj_settings
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.catalog.models import Discipline, Platform, Resource, Vendor
from apps.catalog.seeding import SeedError
from apps.gamification import game, goals, rules
from apps.gamification.models import Badge
from apps.gamification.seeding import load_game, validate_game
from apps.paths.models import LearningPath, Level, LevelResource, Milestone, QuizQuestion
from apps.progress import services as progress

pytestmark = pytest.mark.django_db
SEED = Path(dj_settings.BASE_DIR) / "seed"
BADGES = json.loads((SEED / "insignias.json").read_text(encoding="utf-8"))
TITLES = json.loads((SEED / "titulos.json").read_text(encoding="utf-8"))
NEW_BADGES = {
    "primer-cuadrante": "common",
    "datum-dominado": "rare",
    "cartografo-de-bolsillo": "epic",
    "piensa-en-modelos": "epic",
    "gemelo-en-marcha": "rare",
    "doble-101": "epic",
    "sabio-transversal": "legendary",
}
GEMELO_LEVEL = next(b for b in BADGES["badges"] if b["slug"] == "gemelo-en-marcha")["rule"]["level"]


@pytest.fixture(autouse=True)
def game_seed():
    load_game(BADGES, TITLES)


def _base():
    vendor, _ = Vendor.objects.get_or_create(slug="aeroacademy", defaults={"name": "AeroAcademy"})
    platform, _ = Platform.objects.get_or_create(
        slug="interna", defaults={"name": "Interna", "kind": "vendor", "vendor": vendor}
    )
    transversal, _ = Discipline.objects.get_or_create(
        slug="transversal", defaults={"name": "Transversal", "default_world": "architecture"}
    )
    return vendor, platform, transversal


def make_route(slug, *, codes=("n0", "n1", "n2"), quiz=("n1", "n2"), general=True, published=True):
    """Ruta estructurada: una misión por capítulo y 2 preguntas en los capítulos de `quiz`."""
    vendor, platform, transversal = _base()
    if not general:
        platform = Platform.objects.get_or_create(
            slug="autodesk-learning", defaults={"name": "Autodesk", "kind": "learning"}
        )[0]
    path = LearningPath.objects.create(
        slug=slug,
        title=f"Ruta {slug}",
        platform=platform,
        vendor=vendor,
        kind=LearningPath.Kind.STRUCTURED,
        world="survey",
        is_published=published,
    )
    if general:
        path.disciplines.add(transversal)
    for i, code in enumerate(codes):
        level = Level.objects.create(
            path=path, code=code, order=i, short=code, title=f"Capítulo {code}"
        )
        Milestone.objects.create(path=path, level=level, key=f"{code}-m0", order=0, text="Mide")
        if code in quiz:
            for j in range(2):
                QuizQuestion.objects.create(
                    path=path,
                    level=level,
                    key=f"{code}-q{j}",
                    order=j,
                    question="¿?",
                    options=["a", "b"],
                    answer_index=1,
                )
    return path


def do_level(person, path, code, *, correct=True):
    for m in Milestone.objects.filter(path=path, level__code=code):
        progress.set_milestone(person, m, True)
    for q in QuizQuestion.objects.filter(path=path, level__code=code):
        progress.answer_question(person, q, q.answer_index if correct else 0)


def finish(person, path):
    for code in path.levels.values_list("code", flat=True):
        do_level(person, path, code)


def badges(person):
    return game.unlocked_badges(person)


@pytest.fixture
def routes():
    codes = ("n0", "n1", "n2", "n3", GEMELO_LEVEL)
    return (
        make_route("topografia-101", codes=("n0", "n1", "n2", "n3")),
        make_route("bim-101", codes=tuple(dict.fromkeys(codes)), quiz=("n1",)),
    )


# --- las semillas -------------------------------------------------------------------------------------------------


def test_seed_has_the_new_badges_with_their_rarity_and_32px_sprites():
    by_slug = {b["slug"]: b for b in BADGES["badges"]}
    assert not validate_game(BADGES, TITLES)
    for slug, rarity in NEW_BADGES.items():
        assert by_slug[slug]["rarity"] == rarity
        svg = (SEED.parent / "apps/core/static/game/badges" / by_slug[slug]["sprite"]).read_text(
            encoding="utf-8"
        )
        assert 'viewBox="0 0 32 32"' in svg and "<title>" in svg and 'role="img"' in svg
    # se agregan al final, después de las anteriores
    assert [b["slug"] for b in BADGES["badges"]][-len(NEW_BADGES) :] == list(NEW_BADGES)


@pytest.mark.parametrize(
    "rule",
    [
        {"type": "level_complete", "path": "x"},  # falta el capítulo
        {"type": "quiz_correct", "path": "x", "levels": "n1"},  # no es lista
        {"type": "quiz_correct", "path": "x", "levels": []},
        {"type": "paths_complete", "paths": [1]},
        {"type": "general_complete", "max": 3},  # campo desconocido
    ],
)
def test_seed_validation_rejects_bad_progress_rules(rule):
    bad = {
        "badges": [{"slug": "b", "name": "B", "description": "d", "rarity": "common", "rule": rule}]
    }
    with pytest.raises(SeedError):
        load_game(bad, {"titles": []}, check_sprites=False)


def test_new_titles_point_to_real_badges_and_known_careers():
    classes = {c["slug"] for c in TITLES["classes"]}
    slugs = {b["slug"] for b in BADGES["badges"]}
    new = [t for t in TITLES["titles"] if t.get("badge") in NEW_BADGES]
    assert {t["name"] for t in new} >= {
        "Aprendiz de Datum",
        "Lector de Nubes",
        "Modelador Consciente",
        "Guardián del As-Built",
    }
    for t in new:
        assert t["badge"] in slugs and t.get("character_class", "") in classes | {""}


# --- insignias: se otorgan, son idempotentes y se retiran con la regla ------------------------------------------------


def test_primer_cuadrante_first_chapter_only(member, routes):
    topo, _ = routes
    assert "primer-cuadrante" not in badges(member)
    progress.set_milestone(member, Milestone.objects.get(path=topo, key="n1-m0"), True)
    assert "primer-cuadrante" not in badges(member)  # otro capítulo no cuenta
    do_level(member, topo, "n0")
    assert "primer-cuadrante" in badges(member)


def test_badge_is_idempotent_and_revoked_when_the_rule_stops_holding(member, routes):
    topo, _ = routes
    do_level(member, topo, "n0")
    assert game.evaluate(member) == [] and game.evaluate(member) == []  # no se repite
    assert member.badges.filter(badge__slug="primer-cuadrante").count() == 1
    progress.set_milestone(member, Milestone.objects.get(path=topo, key="n0-m0"), False)
    assert "primer-cuadrante" not in badges(member)  # misma semántica que las demás reglas
    progress.set_milestone(member, Milestone.objects.get(path=topo, key="n0-m0"), True)
    assert member.badges.filter(badge__slug="primer-cuadrante").count() == 1


def test_datum_dominado_needs_every_geodesy_and_coordinates_question(member, routes):
    topo, _ = routes
    do_level(member, topo, "n1")
    assert "datum-dominado" not in badges(member)  # faltan las de coordenadas
    do_level(member, topo, "n2", correct=False)
    assert "datum-dominado" not in badges(member)  # una mal y ya no
    last = QuizQuestion.objects.get(path=topo, key="n2-q0")
    progress.answer_question(member, last, 1)
    assert "datum-dominado" not in badges(member)  # falta la otra
    progress.answer_question(member, QuizQuestion.objects.get(path=topo, key="n2-q1"), 1)
    assert "datum-dominado" in badges(member)
    progress.answer_question(member, last, 0)  # cambia a incorrecta: se retira
    assert "datum-dominado" not in badges(member)


def test_route_badges_doble_and_gemelo(member, routes):
    topo, bim = routes
    finish(member, topo)
    got = badges(member)
    assert "cartografo-de-bolsillo" in got and "piensa-en-modelos" not in got
    assert "doble-101" not in got and "gemelo-en-marcha" not in got
    do_level(member, bim, GEMELO_LEVEL)
    assert "gemelo-en-marcha" in badges(member) and "piensa-en-modelos" not in badges(member)
    finish(member, bim)
    got = badges(member)
    assert {"piensa-en-modelos", "doble-101"} <= got
    assert Badge.objects.get(slug="doble-101").rule["paths"] == ["topografia-101", "bim-101"]


def test_missing_route_never_awards_by_default(member):
    # sin rutas cargadas ninguna regla de avance se cumple (ni «Sabio transversal» con cero rutas)
    assert game.evaluate(member) == []
    assert not (badges(member) & set(NEW_BADGES))


def test_sabio_transversal_counts_new_general_routes_automatically(member, routes):
    topo, bim = routes
    finish(member, topo)
    assert "sabio-transversal" not in badges(member)  # con una sola ruta no basta
    finish(member, bim)
    assert "sabio-transversal" in badges(member)
    # llega una ruta general nueva: solo con datos, sin tocar código ni semillas
    third = make_route("normativa-101", codes=("n0", "n1"))
    assert "sabio-transversal" in badges(member)  # hasta la próxima evaluación
    game.evaluate(member)
    assert "sabio-transversal" not in badges(member)
    finish(member, third)
    assert "sabio-transversal" in badges(member)


def test_sabio_transversal_ignores_routes_that_are_not_general(member, routes):
    topo, bim = routes
    finish(member, topo)
    finish(member, bim)
    make_route("forma-x", general=False)  # plataforma de un fabricante
    make_route("borrador-101", published=False)  # general, pero sin publicar
    game.evaluate(member)
    assert "sabio-transversal" in badges(member)


def test_unpublished_general_route_is_not_general(routes):
    from apps.catalog import services as catalog

    make_route("borrador-101", published=False)
    assert {p.slug for p in catalog.general_paths()} == {"topografia-101", "bim-101"}


def test_check_without_context_is_never_true():
    rule = {"type": "level_complete", "path": "x", "level": "n0"}
    assert not rules.check(rule, None, lambda s: 100)
    assert not rules.check({"type": "general_complete", "min": 2}, None, lambda s: 100)
    assert rules.progress({"type": "manual"}, lambda s: 0, None) is None


# --- títulos -----------------------------------------------------------------------------------------------------------


def titles_of(person):
    return {t.slug for t in game.available_titles(person)}


def test_titles_unlock_with_their_badge_and_leave_with_it(member, routes):
    topo, bim = routes
    assert not titles_of(member) & {"aprendiz-de-datum", "lector-de-nubes"}
    finish(member, topo)
    got = titles_of(member)
    assert {"aprendiz-de-datum", "lector-de-nubes"} <= got
    assert "modelador-consciente" not in got
    finish(member, bim)
    assert {"modelador-consciente", "puente-topo-bim"} <= titles_of(member)
    progress.set_milestone(member, Milestone.objects.get(path=bim, key="n0-m0"), False)
    assert "modelador-consciente" not in titles_of(member)  # se va con la insignia


def test_career_titles_only_show_to_their_career(member, routes):
    _, bim = routes
    do_level(member, bim, GEMELO_LEVEL)
    assert "gemelo-en-marcha" in badges(member)
    assert "guardian-del-as-built" not in titles_of(member)  # sin carrera
    member.character_class = "bim_coord"
    assert "guardian-del-as-built" in titles_of(member)
    assert "custodio-del-gemelo" not in titles_of(member)
    member.character_class = "lev_lead"
    assert "custodio-del-gemelo" in titles_of(member) and "guardian-del-as-built" not in titles_of(
        member
    )


def test_level_titles_and_displayed_title_are_untouched(member, routes):
    topo, _ = routes
    finish(member, topo)
    shown = game.displayed_title(member)
    assert shown is not None and not shown.badge_id  # un título de badge solo sale si se elige


# --- «Próximo logro» --------------------------------------------------------------------------------------------------


def test_next_goal_says_what_is_missing_and_the_title(member, routes):
    topo, _ = routes
    progress.set_milestone(member, Milestone.objects.get(path=topo, key="n0-m0"), False)
    for g in goals.next_goals(member, path=topo, limit=10):
        assert g["done"] < g["total"]
    do_level(member, topo, "n1")
    rows = {g["badge"].slug: g for g in goals.next_goals(member, path=topo, limit=10)}
    datum = rows["datum-dominado"]
    assert datum["text"] == "Te faltan 2 preguntas por acertar" and datum["pct"] == 50
    assert [t.name for t in datum["titles"]] == ["Aprendiz de Datum"]
    assert "primer-cuadrante" in rows and "piensa-en-modelos" not in rows  # solo esta ruta
    assert rows["cartografo-de-bolsillo"]["text"].startswith("Te falta")


def test_next_goal_orders_closest_first_and_skips_earned(member, routes):
    topo, _ = routes
    do_level(member, topo, "n0")
    slugs = [g["badge"].slug for g in goals.next_goals(member, path=topo, limit=10)]
    assert "primer-cuadrante" not in slugs  # ya ganado
    assert slugs[0] in {"cartografo-de-bolsillo", "datum-dominado", "sabio-transversal"}
    assert len(goals.next_goals(member, limit=1)) == 1


def test_sheet_shows_next_goal_to_its_owner_only(client_for, member, make_person, routes):
    topo, _ = routes
    do_level(member, topo, "n0")
    html = client_for(member.login).get("/perfil/").content.decode()
    assert "Próximo logro" in html and "ng-bar" in html
    other = make_person("otra@lev.cl")
    seen = client_for(other.login).get(f"/perfil/{member.pk}/").content.decode()
    assert "Próximo logro" not in seen


def test_next_goal_tag_renders_for_a_route_page(member, routes):
    from django.template import Context, Template

    topo, _ = routes
    html = Template("{% load goal_tags %}{% next_goal path %}").render(
        Context({"user": member, "path": topo})
    )
    assert "Próximo logro" in html and "Primer cuadrante" in html
    assert Template("{% load goal_tags %}{% next_goal %}").render(Context({})).strip() == ""


# --- catálogo ---------------------------------------------------------------------------------------------------------


def tagged(title, tag="Conocimiento general", platform=None):
    platform = (
        platform
        or Platform.objects.get_or_create(
            slug="interna", defaults={"name": "Interna", "kind": "vendor"}
        )[0]
    )
    return Resource.objects.create(
        platform=platform, title=title, tags=[tag, "Esencial"], is_official=False
    )


def test_catalog_section_lists_routes_and_tagged_resources(member_client, routes):
    topo, bim = routes
    level = topo.levels.first()
    res = tagged("Geodesy tutorial")
    LevelResource.objects.create(level=level, resource=res)
    tagged("Otro curso", tag="Intermedio")
    html = member_client.get("/catalogo/").content.decode()
    assert 'id="conocimiento-general"' in html and "Conocimiento general · transversal" in html
    assert 'class="cat-sec cat-gen d-tra"' in html
    assert "/rutas/topografia-101/" in html and "/rutas/bim-101/" in html
    assert (
        "Geodesy tutorial" in html
        and "Otro curso" not in html.split('id="conocimiento-general"')[1].split("</section>")[0]
    )
    assert html.index("conocimiento-general") < html.index("// 01")  # arriba de todo
    assert "?general=1" in html
    section = html.split('id="conocimiento-general"')[1].split("</section>")[0]
    assert section.count('class="dd"') >= 2  # garabato de cada ruta


def test_catalog_general_filter_shows_only_tagged_resources(member_client, routes):
    level = routes[0].levels.first()
    LevelResource.objects.create(level=level, resource=tagged("Solo general"))
    LevelResource.objects.create(level=level, resource=tagged("Curso común", tag="Intermedio"))
    html = member_client.get("/catalogo/?general=1").content.decode()
    assert "Solo general" in html and "Curso común" not in html
    assert 'id="conocimiento-general"' in html and "cat-grid" in html and "// 02" in html
    assert "chip gen on" in html
    other = member_client.get("/catalogo/?q=curso").content.decode()
    assert 'id="conocimiento-general"' not in other  # con otro filtro la sección no estorba


def test_catalog_without_general_content_has_no_section(member_client):
    html = member_client.get("/catalogo/").content.decode()
    assert 'id="conocimiento-general"' not in html
    assert member_client.get("/catalogo/?general=1").status_code == 200
    assert member_client.get("/catalogo/?general=<script>").status_code == 200


def test_catalog_unpublished_general_route_is_hidden(member_client, routes):
    make_route("secreta-101", published=False)
    assert "secreta-101" not in member_client.get("/catalogo/").content.decode()


def test_catalog_shows_my_progress_in_each_route(member, member_client, routes):
    topo, _ = routes
    assert "Empezar la ruta" in member_client.get("/catalogo/").content.decode()
    do_level(member, topo, "n0")
    html = member_client.get("/catalogo/").content.decode()
    assert "completado" in html and 'aria-valuenow="' in html


def test_catalog_queries_do_not_grow_with_general_content(member_client, routes):
    topo, _ = routes
    for i in range(3):
        LevelResource.objects.create(level=topo.levels.first(), resource=tagged(f"Base {i}"))
    member_client.get("/catalogo/")  # calienta cachés

    def count(url):
        with CaptureQueriesContext(connection) as ctx:
            assert member_client.get(url).status_code == 200
        return len(ctx)

    before, before_filter = count("/catalogo/"), count("/catalogo/?general=1")
    for i in range(12):
        tagged(f"Más {i}")
    for slug in ("normativa-101", "gis-101"):
        make_route(slug)
    assert count("/catalogo/") == before
    assert count("/catalogo/?general=1") == before_filter


def test_general_stylesheet_uses_the_transversal_accent_and_theme_tokens():
    css = (SEED.parent / "apps/catalog/static/catalog/catalog.css").read_text(encoding="utf-8")
    block = css[css.index("Conocimiento general · transversal") :]
    assert "#8793A6" in block and "var(--ink)" in block and "var(--sheet)" in block
    assert "prefers-reduced-motion" in block


def test_catalog_lists_only_resources_still_linked_to_a_route(member_client, routes):
    topo, _ = routes
    LevelResource.objects.create(level=topo.levels.first(), resource=tagged("Vinculado"))
    tagged("Huérfano")
    html = member_client.get("/catalogo/?general=1").content.decode()
    assert "Vinculado" in html and "Huérfano" not in html
    assert "Huérfano" not in member_client.get("/catalogo/?todo=1").content.decode()
