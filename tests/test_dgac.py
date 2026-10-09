"""Sección DGAC / RPAS (apps/dgac): prueba de conocimientos, diploma, privacidad del contenido y mundo `aero`.

El contenido real de JEJ vive fuera del repositorio; estas pruebas usan una carpeta sintética (tests/fixtures/dgac).
"""

import json
import shutil
from datetime import date
from pathlib import Path

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.assistant import context, search
from apps.community.models import Note
from apps.credentials.models import Credential
from apps.dgac import assessment, constants, data, services
from apps.dgac.models import KnowledgeAttempt
from apps.gamification import game
from apps.gamification.models import XPEvent
from apps.paths.models import LearningPath, Milestone

pytestmark = pytest.mark.django_db
FIXTURES = Path(__file__).parent / "fixtures" / "dgac"


@pytest.fixture(autouse=True)
def dgac_data(settings):
    settings.DGAC_DATA_DIR = FIXTURES
    call_command("seed_catalog", verbosity=0)
    call_command("cargar_dgac", verbosity=0)


def correct_given(question_ids):
    by_id = {q["id"]: q for q in data.load_bank()}
    return {qid: by_id[qid]["answer"] for qid in question_ids}


def wrong_given(question_ids):
    by_id = {q["id"]: q for q in data.load_bank()}
    out = {}
    for qid in question_ids:
        key = by_id[qid]["answer"]
        out[qid] = next(o["key"] for o in by_id[qid]["options"] if o["key"] != key)
    return out


def attempt_with(person, n_correct, total=25):
    """Intento real con `n_correct` aciertos de `total` (corregido por el servicio)."""
    ids = [q["id"] for q in assessment.draw(total, seed=3)]
    given = wrong_given(ids)
    good = correct_given(ids)
    for qid in ids[:n_correct]:
        given[qid] = good[qid]
    return services.submit_attempt(person, ids, given)


def take_and_submit(client, answers="correct"):
    page = client.get("/dgac/prueba/rendir/")
    assert page.status_code == 200
    ids = [q["id"] for q in page.context["questions"]]
    given = correct_given(ids) if answers == "correct" else wrong_given(ids)
    form = {"draw": page.context["token"]} | {f"q{qid}": key for qid, key in given.items()}
    return client.post("/dgac/prueba/rendir/", form)


# --- la prueba: sorteo, corrección, umbral, vigencia -------------------------------------------------------------


def test_take_page_never_contains_the_answer(member_client):
    page = member_client.get("/dgac/prueba/rendir/")
    assert page.status_code == 200
    html = page.content.decode()
    for q in page.context["questions"]:
        assert "answer" not in q and "correct" not in q
    form = html[html.index("data-dgac-quiz") : html.index("</form>", html.index("data-dgac-quiz"))]
    assert "answer" not in form.lower() and "checked" not in form
    inputs = {n for n in __import__("re").findall(r'name="([^"]+)"', form)}
    assert {n for n in inputs if n.startswith("q")} and all(
        n in {"draw", "csrfmiddlewaretoken"} or n.startswith("q") for n in inputs
    )
    session_ids = next(iter(member_client.session["dgac_draws"].values()))
    assert all(isinstance(i, int) for i in session_ids)  # en sesión solo ids, jamás la clave


def test_draws_25_unique_questions_and_seed_is_only_for_tests():
    first = assessment.draw(seed=1)
    assert len(first) == assessment.QUESTIONS_PER_ATTEMPT == 25
    assert len({q["id"] for q in first}) == 25
    assert [q["id"] for q in assessment.draw(seed=1)] == [q["id"] for q in first]
    # sin semilla usa SystemRandom: tres sorteos no pueden salir idénticos
    draws = {tuple(q["id"] for q in assessment.draw()) for _ in range(3)}
    assert len(draws) > 1


def test_threshold_is_80_percent():
    assert assessment.PASS_PERCENT == 80
    ids = list(range(1, 26))
    good = correct_given(ids)
    assert assessment.grade(ids, good)[2:] == (100.0, True)
    bad = wrong_given(ids)
    twenty = {**bad, **{qid: good[qid] for qid in ids[:20]}}
    assert assessment.grade(ids, twenty)[1:] == (20, 80.0, True)
    nineteen = {**bad, **{qid: good[qid] for qid in ids[:19]}}
    assert assessment.grade(ids, nineteen)[1:] == (19, 76.0, False)
    assert assessment.grade(ids, {})[1:] == (0, 0.0, False)  # sin responder = incorrecta


def test_validity_is_twelve_months():
    assert assessment.VALID_MONTHS == 12
    assert assessment.valid_until(date(2026, 10, 9)) == date(2027, 10, 9)
    assert assessment.valid_until(date(2028, 2, 29)) == date(2029, 2, 28)
    assert assessment.valid_until(date(2026, 12, 31)) == date(2027, 12, 31)


def test_passed_attempt_stores_expiry_and_failed_does_not(member):
    ok = attempt_with(member, 25)
    assert ok.passed and ok.expires_on == assessment.valid_until(timezone.localdate())
    assert ok.is_current
    no = attempt_with(member, 10)
    assert not no.passed and no.expires_on is None and not no.is_current


def test_whitespace_collapsed_and_roman_enumeration_split_for_display_only():
    bank = {q["id"]: q for q in data.load_bank()}
    assert (
        bank[1]["text"] == "Pregunta de práctica 01: ¿cuánto es 1 + 3?"
    )  # espacios dobles colapsados
    lines = assessment.enumerated_lines(bank[7]["text"])
    assert len(lines) == 4 and lines[1].startswith("I.") and lines[3].startswith("III.")
    assert " ".join(lines) == bank[7]["text"]  # solo presentación: el texto no cambia
    assert assessment.enumerated_lines("Una sola I. suelta no parte") == [
        "Una sola I. suelta no parte"
    ]


def test_full_flow_through_the_web(member_client, member):
    resp = take_and_submit(member_client)
    assert resp.status_code == 302
    attempt = KnowledgeAttempt.objects.get(person=member)
    assert attempt.passed and attempt.question_count == 25 and float(attempt.score_percent) == 100.0
    page = member_client.get(resp["Location"])
    assert page.status_code == 200 and "Aprobada" in page.content.decode()


def test_tampered_or_stale_draw_is_not_graded(member_client, member):
    resp = member_client.post("/dgac/prueba/rendir/", {"draw": "inventado", "q1": "a"})
    assert resp.status_code == 302 and resp["Location"].endswith("/dgac/prueba/rendir/")
    assert not KnowledgeAttempt.objects.exists()
    # un sorteo se usa una sola vez
    page = member_client.get("/dgac/prueba/rendir/")
    token = page.context["token"]
    member_client.post("/dgac/prueba/rendir/", {"draw": token})
    assert KnowledgeAttempt.objects.count() == 1
    member_client.post("/dgac/prueba/rendir/", {"draw": token})
    assert KnowledgeAttempt.objects.count() == 1


def test_extra_posted_questions_are_ignored(member_client, member):
    page = member_client.get("/dgac/prueba/rendir/")
    ids = [q["id"] for q in page.context["questions"]]
    outside = next(i for i in range(1, 31) if i not in ids)
    form = {"draw": page.context["token"], f"q{outside}": data.load_bank()[outside - 1]["answer"]}
    member_client.post("/dgac/prueba/rendir/", form)
    attempt = KnowledgeAttempt.objects.get(person=member)
    assert outside not in [r["id"] for r in attempt.answers] and attempt.correct_count == 0


# --- el intento guarda su propia copia -------------------------------------------------------------------------------


def test_attempt_copy_survives_bank_edits(settings, tmp_path, member_client, member):
    attempt = attempt_with(member, 20)
    before = json.loads(json.dumps(attempt.answers))
    copy = tmp_path / "dgac"
    shutil.copytree(FIXTURES, copy)
    bank = json.loads((copy / "banco.json").read_text(encoding="utf-8"))
    for q in bank["questions"]:
        q["text"] = "TEXTO EDITADO"
        q["answer"] = "d"
    bank["questions"] = bank["questions"][:5]  # y además se borran preguntas
    (copy / "banco.json").write_text(json.dumps(bank), encoding="utf-8")
    settings.DGAC_DATA_DIR = copy
    page = member_client.get(f"/dgac/prueba/{attempt.pk}/")
    html = page.content.decode()
    assert (
        page.status_code == 200 and "TEXTO EDITADO" not in html and "Pregunta de práctica" in html
    )
    attempt.refresh_from_db()
    assert attempt.answers == before and attempt.correct_count == 20 and attempt.passed


def test_result_shows_what_to_reinforce(member_client, member):
    attempt = attempt_with(member, 12)
    page = member_client.get(f"/dgac/prueba/{attempt.pk}/")
    html = page.content.decode()
    assert "A reforzar" in html and "Qué reforzar" in html
    assert {t["topic"] for t in page.context["topics"]} <= {"Tema A", "Tema B", "Tema C"}
    assert len(page.context["wrong"]) == 13
    assert "Intentar de nuevo" in html


# --- diploma y credencial -------------------------------------------------------------------------------------------


def test_diploma_only_for_passed_attempts(member_client, member):
    failed = attempt_with(member, 5)
    assert member_client.get(f"/dgac/diploma/{failed.pk}/").status_code == 404
    passed = attempt_with(member, 25)
    resp = member_client.get(f"/dgac/diploma/{passed.pk}/")
    html = resp.content.decode()
    assert resp.status_code == 200 and "Diploma de prueba" in html and member.name in html
    assert passed.code in html and "@media print" not in html  # el CSS va en el archivo estático
    assert "100.0" in html.replace(",", ".")


def test_pass_issues_internal_credential_and_xp_once(member):
    first = attempt_with(member, 25)
    cred = first.credential
    assert cred.kind == Credential.Kind.INTERNAL and cred.status == Credential.Status.VERIFIED
    assert (
        cred.owner == member and cred.path.slug == constants.ROUTE_SLUG and cred.reviewed_by is None
    )
    assert cred.expires_on == first.expires_on and cred.credential_id == constants.CREDENTIAL_ID
    xp = XPEvent.objects.filter(person=member, source=f"credential:{cred.pk}")
    assert xp.count() == 1 and xp.first().points == game.CREDENTIAL_POINTS[Credential.Kind.INTERNAL]
    total = game.total_xp(member)
    again = attempt_with(member, 25)  # aprobar otra vez renueva, no duplica
    assert again.credential_id == cred.pk
    assert Credential.objects.filter(owner=member).count() == 1
    assert game.total_xp(member) == total


def test_failed_attempt_issues_nothing(member):
    attempt = attempt_with(member, 3)
    assert attempt.credential is None and not Credential.objects.exists()


def test_latest_valid_ignores_expired_attempts(member):
    attempt = attempt_with(member, 25)
    assert services.latest_valid(member) == attempt
    KnowledgeAttempt.objects.filter(pk=attempt.pk).update(expires_on=date(2020, 1, 1))
    assert services.latest_valid(member) is None


# --- quién ve qué ---------------------------------------------------------------------------------------------------


def test_member_only_sees_own_attempts_and_lead_sees_all(client_for, member, lead, make_person):
    other = make_person("otra@lev.cl")
    mine = attempt_with(member, 25)
    theirs = attempt_with(other, 25)
    own = client_for(member.login)
    assert own.get(f"/dgac/prueba/{mine.pk}/").status_code == 200
    assert own.get(f"/dgac/prueba/{theirs.pk}/").status_code == 404
    assert own.get(f"/dgac/diploma/{theirs.pk}/").status_code == 404
    listing = own.get("/dgac/prueba/")
    assert [a.pk for a in listing.context["attempts"]] == [mine.pk] and listing.context[
        "team"
    ] is None
    boss = client_for(lead.login)
    assert boss.get(f"/dgac/prueba/{theirs.pk}/").status_code == 200
    assert boss.get(f"/dgac/diploma/{theirs.pk}/").status_code == 200
    team = boss.get("/dgac/prueba/").context["team"]
    assert {row["person"].pk for row in team if row["attempt"]} == {member.pk, other.pk}


def test_pending_people_get_no_access(client_for, make_person):
    pending = make_person("nueva@lev.cl", status="pending")
    c = client_for(pending.login)
    for url in ("/dgac/", "/dgac/prueba/", "/dgac/prueba/rendir/", "/dgac/archivo/demo.svg"):
        resp = c.get(url)
        assert resp.status_code == 302 and "espera" in resp["Location"]
    assert not KnowledgeAttempt.objects.exists()


def test_no_identity_no_access(client_for):
    assert client_for("").get("/dgac/").status_code == 401


def test_history_queries_do_not_grow_with_attempts(client_for, member):
    c = client_for(member.login)
    attempt_with(member, 20)
    c.get("/dgac/prueba/")  # calienta cachés
    with CaptureQueriesContext(connection) as few:
        c.get("/dgac/prueba/")
    for _ in range(8):
        attempt_with(member, 25)
    with CaptureQueriesContext(connection) as many:
        c.get("/dgac/prueba/")
    assert len(many) == len(few)


# --- contenido privado: infografías, carpeta ausente ------------------------------------------------------------


def test_overview_renders_sections_from_the_data_folder(member_client):
    page = member_client.get("/dgac/")
    html = page.content.decode()
    assert page.status_code == 200 and "Sección de ejemplo" in html and "Otra sección" in html
    assert 'src="/dgac/archivo/demo.svg"' in html and "Punto uno" in html
    assert "Topografía" in html


def test_asset_is_served_by_a_protected_view(member_client):
    resp = member_client.get("/dgac/archivo/demo.svg")
    assert resp.status_code == 200 and resp["Content-Type"] == "image/svg+xml"
    assert (
        resp["X-Content-Type-Options"] == "nosniff" and "sandbox" in resp["Content-Security-Policy"]
    )
    for bad in (
        "nada.svg",
        "demo.txt",
        "..%2Fruta.json",
        "%2e%2e%2fruta.json",
        "ruta.json",
        ".svg",
    ):
        assert member_client.get(f"/dgac/archivo/{bad}").status_code == 404
    assert data.image_path("../ruta.json") is None and data.image_path("a/../demo.svg") is None


def test_missing_data_dir_is_handled(settings, tmp_path, member_client, capsys):
    settings.DGAC_DATA_DIR = tmp_path / "no-existe"
    home = member_client.get("/dgac/")
    assert home.status_code == 200 and "aún no instalado" in home.content.decode()
    test_page = member_client.get("/dgac/prueba/")
    assert test_page.status_code == 200 and "aún no instalado" in test_page.content.decode()
    take = member_client.get("/dgac/prueba/rendir/")
    assert take.status_code == 503 and "aún no instalado" in take.content.decode()
    assert member_client.get("/dgac/archivo/demo.svg").status_code == 404
    assert data.load_bank() == [] and data.load_overview() is None
    call_command("cargar_dgac")  # no revienta: avisa
    assert "no está instalado" in capsys.readouterr().out


def test_invalid_json_does_not_crash(settings, tmp_path, member_client):
    folder = tmp_path / "dgac"
    folder.mkdir()
    (folder / "banco.json").write_text("{esto no es json", encoding="utf-8")
    (folder / "operaciones.json").write_text("[]", encoding="utf-8")
    settings.DGAC_DATA_DIR = folder
    assert member_client.get("/dgac/").status_code == 200
    assert member_client.get("/dgac/prueba/rendir/").status_code == 503


def test_cargar_dgac_is_idempotent_and_validates(settings, tmp_path):
    assert LearningPath.objects.filter(slug=constants.ROUTE_SLUG, world="aero").count() == 1
    path = LearningPath.objects.get(slug=constants.ROUTE_SLUG)
    assert {d.slug for d in path.disciplines.all()} == {"captura-rpa", "topografia"}
    n = Milestone.objects.filter(path=path).count()
    call_command("cargar_dgac", verbosity=0)
    assert Milestone.objects.filter(path=path).count() == n == 3
    bad = tmp_path / "dgac"
    shutil.copytree(FIXTURES, bad)
    route = json.loads((bad / "ruta.json").read_text(encoding="utf-8"))
    route["levels"][0]["quiz"][0]["answer"] = 9
    (bad / "ruta.json").write_text(json.dumps(route), encoding="utf-8")
    settings.DGAC_DATA_DIR = bad
    with pytest.raises(Exception, match="error"):
        call_command("cargar_dgac", verbosity=0)


# --- Nala no ve nada de esto ---------------------------------------------------------------------------------------


def test_dgac_content_is_not_in_nala_index_or_context(member):
    path = LearningPath.objects.get(slug=constants.ROUTE_SLUG)
    Note.objects.create(
        path=path,
        level=path.levels.first(),
        author=member,
        type="tip",
        text="procedimiento interno secreto",
    )
    rows = search.reindex()
    assert rows > 0
    with connection.cursor() as cur:
        cur.execute("SELECT kind, ref, title, body, url FROM assistant_fts")
        indexed = cur.fetchall()
    blob = json.dumps(indexed, ensure_ascii=False)
    assert "dgac-rpas" not in blob and "Ruta de práctica" not in blob
    assert "Misión uno" not in blob and "secreto" not in blob
    assert search.search("sintética") == [] and search.search("procedimiento interno secreto") == []
    assert any(r[0] == "path" for r in indexed)  # control: las demás rutas sí se indexan


def test_dgac_missions_never_reach_the_model_as_pending(member):
    LearningPath.objects.exclude(slug=constants.ROUTE_SLUG).update(is_published=False)
    from apps.core import dashboard

    mission = dashboard.suggested_mission(member)
    assert (
        mission and mission["path"].slug == constants.ROUTE_SLUG
    )  # sí se sugiere dentro de la app
    assert context.pending_titles(member) == []  # pero no viaja al proveedor externo


def test_stale_index_rows_are_revalidated(member):
    path = LearningPath.objects.get(slug=constants.ROUTE_SLUG)
    assert search._still_visible(f"path:{path.pk}") is False
    other = LearningPath.objects.exclude(slug=constants.ROUTE_SLUG).first()
    assert search._still_visible(f"path:{other.pk}") is True


# --- mundo aero y avance ligado a la ruta -----------------------------------------------------------------------


def test_aero_world_renders_with_waypoints(member_client):
    page = member_client.get("/rutas/dgac-rpas/")
    html = page.content.decode()
    assert page.status_code == 200 and "world-aero" in html and "ao-flight" in html
    assert html.count('class="ao-wp') == 2 and "Misión uno" in html and "worlds/aero.css" in html
    assert "data-enhance-root" in html
    partial = member_client.get("/rutas/dgac-rpas/?nivel=d1", headers={"X-Partial": "1"})
    assert "<html" not in partial.content.decode() and "Misión tres" in partial.content.decode()


def test_aero_route_progress_and_topography_link(member_client, member):
    assert member_client.post("/rutas/dgac-rpas/hitos/d0-t0/", {"checked": "1"}).status_code in (
        302,
        200,
    )
    path = LearningPath.objects.get(slug=constants.ROUTE_SLUG)
    assert game.path_percent(member, path) > 0
    listing = member_client.get("/rutas/?vendor=dji&discipline=topografia")
    assert "Ruta de práctica" in listing.content.decode()
    home = member_client.get("/dgac/")
    assert home.context["summary"]["path_pct"] > 0
