"""Cómo tomar cursos (P1-1, P1-2, P1-4): llamada a la acción por ruta, tarjeta única, portada y migas."""

import re

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.paths import services as path_services
from apps.paths.models import LearningPath, Milestone, QuizQuestion
from apps.progress import services as progress
from apps.progress import services as progress_services

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded(db):
    call_command("seed_catalog", verbosity=0)


def do_level(person, path, code):
    for m in Milestone.objects.filter(path=path, level__code=code, retired=False):
        progress.set_milestone(person, m, True)
    for q in QuizQuestion.objects.filter(path=path, level__code=code, retired=False):
        progress.answer_question(person, q, q.answer_index)


def structured(slug="topografia-101"):
    return LearningPath.objects.get(slug=slug)


# --- cta_for ------------------------------------------------------------------------------------------------------


def test_cta_states(seeded, member):
    path = structured()
    codes = list(path.levels.order_by("order").values_list("code", flat=True))
    cta = path_services.cta_for(member, path)
    assert cta["state"] == "start" and cta["label"] == "Empezar la ruta →"
    assert cta["url"] == f"/rutas/{path.slug}/?nivel={codes[0]}#panel" and cta["pct"] == 0

    do_level(member, path, codes[0])
    cta = path_services.cta_for(member, path)
    assert cta["state"] == "continue" and re.fullmatch(r"Continuar · \d+ % →", cta["label"])
    assert 0 < cta["pct"] < 100
    assert cta["url"] == f"/rutas/{path.slug}/?nivel={codes[1]}#panel"  # el primer nivel pendiente

    for code in codes[1:]:
        do_level(member, path, code)
    cta = path_services.cta_for(member, path)
    assert cta["state"] == "done" and cta["pct"] == 100
    assert cta["label"] == "Ver diploma ✦" and cta["url"] == f"/diplomas/{path.slug}/"


def test_cta_continue_matches_where_the_route_opens(seeded, member, member_client):
    """El botón «Continuar» lleva al mismo nivel que abre la ruta sin `?nivel=` (world_context)."""
    path = structured()
    codes = list(path.levels.order_by("order").values_list("code", flat=True))
    do_level(member, path, codes[0])
    cta = path_services.cta_for(member, path)
    ctx = progress_services.world_context(member, path)
    assert cta["url"].split("nivel=")[1].split("#")[0] == ctx["current"]["level"].code


def test_cta_for_external_track(seeded, member):
    path = LearningPath.objects.filter(kind=LearningPath.Kind.EXTERNAL_TRACK).first()
    cta = path_services.cta_for(member, path)
    assert cta["state"] == "start" and cta["label"] == "Registrar mi primer curso →"
    assert cta["url"] == f"/rutas/{path.slug}/"


def test_cta_queries_constant(seeded, member):
    paths = list(LearningPath.objects.select_related("vendor").order_by("kind", "slug"))
    ext = next(p for p in paths if p.kind == LearningPath.Kind.EXTERNAL_TRACK)
    st = next(p for p in paths if p.kind == LearningPath.Kind.STRUCTURED)
    two = [st, ext]  # una de cada tipo: las consultas son fijas por tipo, no por ruta
    path_services.route_ctas(member, two)  # calienta cachés
    with CaptureQueriesContext(connection) as few:
        path_services.route_ctas(member, two)
    with CaptureQueriesContext(connection) as many:
        path_services.route_ctas(member, paths)
    assert len(paths) > 5 and len(many) == len(few)


# --- tarjeta única de ruta -----------------------------------------------------------------------------------------


def cards(html):
    return re.findall(r'<article class="card route-card.*?</article>', html, flags=re.S)


@pytest.mark.parametrize(
    "url",
    ["/", "/rutas/", "/rutas/?vendor=aeroacademy", "/catalogo/", "/foro/"],
    ids=["home", "rutas", "rutas-aeroacademy", "catalogo", "foro"],
)
def test_route_cards_have_icon_and_cta(site_world, client_for, url):
    html = client_for(site_world["member"].login).get(url).content.decode()
    found = cards(html)
    assert found, url
    for card in found:
        assert re.search(r'<img class="route-ico" src="[^"]*ruta-[a-z0-9-]+\.svg"', card), card[
            :200
        ]
        assert card.count('class="btn primary route-cta"') == 1
        assert (
            "Empezar la ruta" in card
            or "Continuar" in card
            or "Ver diploma" in card
            or "Ver notas" in card
            or "Registrar" in card
            or "Repasar" in card
        )


def test_forum_notes_card_has_two_links(site_world, client_for):
    html = client_for(site_world["member"].login).get("/foro/").content.decode()
    card = next(c for c in cards(html) if "/notas/" in c)
    assert "Ver notas →" in card and 'class="rc-sec"' in card and "Ir a la ruta" in card


def test_route_card_escapes_text(site_world, client_for):
    LearningPath.objects.filter(slug="topografia-101").update(title="<script>alert(1)</script>")
    html = client_for(site_world["member"].login).get("/rutas/?vendor=aeroacademy").content.decode()
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html
