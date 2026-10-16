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
