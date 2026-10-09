from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.utils import timezone

from apps.core import dashboard
from apps.credentials import services as creds
from apps.gamification import game
from apps.gamification.models import PersonBadge, XPEvent
from apps.paths.models import LearningPath, Milestone, QuizQuestion
from apps.progress import services as progress

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF\n" + b"x" * 200
FORMA, BENTLEY = "forma-revit", "bentley-learn"


@pytest.fixture(autouse=True)
def seeded(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    call_command("seed_catalog", verbosity=0)


def make_cred(owner, **extra):
    data = {"title": "Curso", "kind": "completion", "visibility": "team", **extra}
    return creds.create_credential(owner, data, SimpleUploadedFile("c.pdf", PDF))


def only_forma():
    LearningPath.objects.exclude(slug=FORMA).update(is_published=False)


def forma():
    return LearningPath.objects.get(slug=FORMA)


# --- misión sugerida --------------------------------------------------------------------------------------------


def test_a_new_person_gets_a_first_mission(member):
    mission = dashboard.suggested_mission(member)
    assert mission and mission["pct"] == 0 and mission["url"].startswith("/rutas/")


def test_mission_follows_the_real_progress(member):
    only_forma()
    first = Milestone.objects.filter(path=forma(), retired=False).first()
    before = dashboard.suggested_mission(member)
    progress.set_milestone(member, first, True)
    after = dashboard.suggested_mission(member)
    assert after["path"].slug == FORMA and after["pct"] > 0
    assert after["title"] != before["title"]
    assert "*" not in after["title"]


def test_mission_continues_the_most_advanced_path(member):
    first = Milestone.objects.filter(path=forma(), retired=False).first()
    progress.set_milestone(member, first, True)
    assert dashboard.suggested_mission(member)["path"].slug == FORMA


def test_external_mission_asks_for_a_certificate_and_skips_what_is_in_review(member):
    path = LearningPath.objects.get(slug=BENTLEY)
    first = dashboard._next_for_external(member, path)
    assert first["url"].startswith(f"/rutas/{BENTLEY}/registrar/?curso=")
    key = first["url"].split("curso=")[1]
    from apps.paths.models import ExternalCourse

    course = ExternalCourse.objects.get(path=path, key=key)
    make_cred(member, resource=course.resource, path=path)
    second = dashboard._next_for_external(member, path)
    assert second["url"] != first["url"]


def test_no_mission_when_everything_is_complete(member):
    only_forma()
    for m in Milestone.objects.filter(path=forma(), retired=False):
        progress.set_milestone(member, m, True)
    for q in QuizQuestion.objects.filter(path=forma(), retired=False):
        progress.answer_question(member, q, q.answer_index)
    assert dashboard.suggested_mission(member) is None


def test_unpublished_paths_are_not_suggested_to_members_but_are_to_leads(member, lead):
    LearningPath.objects.update(is_published=False)
    assert dashboard.suggested_mission(member) is None
    assert dashboard.suggested_mission(lead) is not None


# --- tablón -------------------------------------------------------------------------------------------------------


def test_board_shows_this_weeks_badges_and_team_certificates(member, lead, make_person):
    other = make_person("otra@lev.cl")
    cred = make_cred(other, title="Certificado Revit")
    creds.verify(cred, lead)
    texts = [i["text"] for i in dashboard.guild_board(member)["items"]]
    assert any("otra" in t and "Primer Trofeo" in t for t in texts)
    assert any("Certificado Revit" in t for t in texts)


def test_board_hides_private_credentials(member, lead, make_person):
    other = make_person("otra@lev.cl")
    creds.verify(make_cred(other, title="Secreto", visibility="private"), lead)
    texts = " ".join(i["text"] for i in dashboard.guild_board(member)["items"])
    assert "Secreto" not in texts


def test_board_ignores_old_events_and_pending_people(member, make_person):
    old = make_person("vieja@lev.cl")
    game.award(old, "x:1", "manual", 10)
    badge = PersonBadge.objects.create(
        person=old,
        badge=__import__("apps.gamification.models", fromlist=["Badge"]).Badge.objects.get(
            slug="primera-luz"
        ),
    )
    PersonBadge.objects.filter(pk=badge.pk).update(earned_at=timezone.now() - timedelta(days=30))
    XPEvent.objects.filter(person=old).update(created_at=timezone.now() - timedelta(days=30))
    pending = make_person("nuevo@lev.cl", status="pending")
    PersonBadge.objects.create(
        person=pending,
        badge=__import__("apps.gamification.models", fromlist=["Badge"]).Badge.objects.get(
            slug="primera-nube"
        ),
    )
    board = dashboard.guild_board(member)
    assert board["items"] == [] and board["weekly_xp"] == 0


def test_board_counts_weekly_xp_without_the_streak_bonus(member):
    game.award(member, "x:1", "manual", 50)
    game.award(member, "streak:2026-W41", "streak", 40)
    assert dashboard.guild_board(member)["weekly_xp"] == 50


# --- contadores ---------------------------------------------------------------------------------------------------


def test_counters_for_members_and_leads(member, lead):
    creds.verify(make_cred(member, expires_on=timezone.localdate() + timedelta(days=10)), lead)
    make_cred(member, title="Otro")
    assert dashboard.counters(member) == {"expiring": 1, "to_review": None, "open_questions": 0}
    assert dashboard.counters(lead)["to_review"] == 1


def test_expired_or_far_credentials_do_not_count_as_expiring(member, lead):
    creds.verify(make_cred(member, expires_on=timezone.localdate() - timedelta(days=1)), lead)
    creds.verify(
        make_cred(member, title="Lejos", expires_on=timezone.localdate() + timedelta(days=900)),
        lead,
    )
    assert dashboard.counters(member)["expiring"] == 0


# --- la portada ---------------------------------------------------------------------------------------------------


def test_home_shows_the_new_sections(client_for, member):
    html = client_for(member.login).get("/").content.decode()
    assert "Tu misión sugerida" in html and "Tablón del gremio" in html and "teo-idle.svg" in html
    assert "por vencer" in html and "por revisar" not in html


def test_home_shows_review_counter_to_leads(client_for, member, lead):
    make_cred(member)
    assert "1</b> certificados por revisar" in client_for(lead.login).get("/").content.decode()


def test_home_still_has_the_sponsor_and_modules(client_for, member):
    html = client_for(member.login).get("/").content.decode()
    assert "Suite Aero" in html and "Módulos" in html


def test_home_query_count_is_bounded(client_for, member, django_assert_max_num_queries):
    with django_assert_max_num_queries(55):  # primera visita; no crece con las rutas
        assert client_for(member.login).get("/").status_code == 200


# --- consultas acotadas: no crecen con rutas, capítulos, hitos ni cursos --------------------------------------------


def _add_routes(person, n, start=0):
    """`n` rutas nuevas (mitad estructuradas, mitad externas) con capítulos, hitos, preguntas, cursos y productos."""
    from apps.catalog.models import Discipline, Platform, Product, Resource, Vendor
    from apps.paths.models import ExternalCourse, Level

    vendor = Vendor.objects.first()
    platform = Platform.objects.first()
    product = Product.objects.first()
    disc = Discipline.objects.first()
    for i in range(start, start + n):
        external = i % 2 == 1
        path = LearningPath.objects.create(
            slug=f"extra-{i}",
            title=f"Ruta extra {i}",
            vendor=vendor,
            kind=LearningPath.Kind.EXTERNAL_TRACK if external else LearningPath.Kind.STRUCTURED,
            is_published=True,
        )
        path.products.add(product)
        path.disciplines.add(disc)
        for j in range(2):
            level = Level.objects.create(
                path=path,
                code=f"L{j}",
                order=j,
                short=f"N{j}",
                title=f"Nivel {j}",
                completion_rule="any_one" if (external and j) else "all_required",
            )
            if external:
                for k in range(2):
                    res = Resource.objects.create(
                        platform=platform, title=f"Curso {i}-{j}-{k}", kind="course"
                    )
                    ExternalCourse.objects.create(
                        path=path,
                        level=level,
                        key=f"c{j}{k}",
                        order=k,
                        resource=res,
                        reward="trophy",
                    )
                    if k == 0:
                        make_cred(person, resource=res, path=path)
            else:
                for k in range(3):
                    m = Milestone.objects.create(
                        path=path, level=level, key=f"m{j}{k}", order=k, text=f"Hito {k}"
                    )
                    if k == 0:
                        progress.set_milestone(person, m, True)
                QuizQuestion.objects.create(
                    path=path,
                    level=level,
                    key=f"q{j}",
                    question="¿?",
                    options=["a", "b"],
                    answer_index=0,
                )


def _queries(client, url):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as ctx:
        assert client.get(url).status_code == 200
    return len(ctx)


@pytest.mark.parametrize("url", ["/", "/rutas/", "/catalogo/"])
def test_listing_query_count_does_not_grow_with_routes(client_for, member, url):
    client = client_for(member.login)
    client.get(url)  # la primera visita crea el estado de la persona: no se mide
    _add_routes(member, 2)
    few = _queries(client, url)
    _add_routes(member, 5, start=2)
    many = _queries(client, url)
    assert many == few, f"{url}: {few} consultas con 2 rutas extra, {many} con 7"


def test_path_percents_match_the_per_path_state(member):
    from apps.progress import external

    _add_routes(member, 4)
    paths = list(LearningPath.objects.all())
    batch = game.path_percents(member, paths)
    for p in paths:
        expected = (
            external.external_context(member, p)["stats"]["pct"]
            if p.kind == LearningPath.Kind.EXTERNAL_TRACK
            else game._structured_state(member, p)["pct"]
        )
        assert batch[p.pk] == expected, p.slug
    assert any(0 < v for v in batch.values())


def test_path_percents_use_a_fixed_number_of_queries(member, django_assert_max_num_queries):
    _add_routes(member, 8)
    paths = list(LearningPath.objects.all())
    with django_assert_max_num_queries(6):
        game.path_percents(member, paths)
