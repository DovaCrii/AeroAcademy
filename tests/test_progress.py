import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client

from apps.paths.models import LearningPath, Milestone, QuizQuestion
from apps.progress import services
from apps.progress.models import MilestoneCheck, PathGoal, QuizAnswer

pytestmark = pytest.mark.django_db

REVIT = "forma-revit"
FORMA = "forma-coordinacion"  # n0 conserva los hitos de la antigua ruta Forma + Revit


@pytest.fixture(autouse=True)
def seeded():
    call_command("seed_catalog", verbosity=0)


def url(kind, key=None, slug=FORMA):
    return f"/rutas/{slug}/{kind}/" + (f"{key}/" if key else "")


def toggle(client, key, checked=True, **extra):
    return client.post(url("hitos", key), {"checked": "1" if checked else "0"}, **extra)


def answer(client, key, choice, **extra):
    return client.post(url("quiz", key), {"choice": str(choice)}, **extra)


def chapter(person, code, slug=FORMA):
    ctx = services.world_context(person, LearningPath.objects.get(slug=slug))
    return next(ch for ch in ctx["chapters"] if ch["level"].code == code)


def correct_choice(key):
    return QuizQuestion.objects.get(path__slug=FORMA, key=key).answer_index


def wrong_choice(key):
    q = QuizQuestion.objects.get(path__slug=FORMA, key=key)
    return next(i for i in range(len(q.options)) if i != q.answer_index)


# --- persistencia por persona ---


def test_milestone_check_persists_and_is_personal(client_for, make_person):
    ana, luis = make_person("ana@lev.cl"), make_person("luis@lev.cl")
    assert toggle(client_for(ana.login), "n0-t0").status_code == 302

    assert MilestoneCheck.objects.filter(person=ana, milestone__key="n0-t0").exists()
    assert not MilestoneCheck.objects.filter(person=luis).exists()
    html = client_for(ana.login).get(f"/rutas/{FORMA}/?nivel=n0").content.decode()
    assert 'aria-pressed="true"' in html
    html_luis = client_for(luis.login).get(f"/rutas/{FORMA}/?nivel=n0").content.decode()
    assert 'aria-pressed="true"' not in html_luis


def test_uncheck_removes_and_both_directions_are_idempotent(client_for, member):
    client = client_for(member.login)
    toggle(client, "n0-t0")
    toggle(client, "n0-t0")
    assert MilestoneCheck.objects.filter(person=member).count() == 1
    toggle(client, "n0-t0", checked=False)
    toggle(client, "n0-t0", checked=False)
    assert MilestoneCheck.objects.filter(person=member).count() == 0


def test_quiz_answer_persists_and_can_be_replaced(client_for, member):
    client = client_for(member.login)
    answer(client, "n0-q0", wrong_choice("n0-q0"))
    assert QuizAnswer.objects.get(person=member).selected_index == wrong_choice("n0-q0")
    answer(client, "n0-q0", correct_choice("n0-q0"))
    assert QuizAnswer.objects.filter(person=member).count() == 1
    assert QuizAnswer.objects.get(person=member).is_correct


def test_database_rejects_duplicate_checks(member):
    milestone = Milestone.objects.get(path__slug=FORMA, key="n0-t0")
    MilestoneCheck.objects.create(person=member, milestone=milestone)
    with pytest.raises(IntegrityError), transaction.atomic():
        MilestoneCheck.objects.create(person=member, milestone=milestone)


# --- regla del porcentaje ---


def test_level_percent_follows_the_rule(client_for, member):
    client = client_for(member.login)
    ch = chapter(member, "n0")
    assert (ch["done"], ch["total"], ch["pct"]) == (0, 6, 0)  # 4 hitos + 2 preguntas

    toggle(client, "n0-t0")
    toggle(client, "n0-t1")
    answer(client, "n0-q0", correct_choice("n0-q0"))
    ch = chapter(member, "n0")
    assert (ch["done"], ch["total"], ch["pct"]) == (3, 6, 50)


def test_wrong_answers_do_not_count(client_for, member):
    answer(client_for(member.login), "n0-q0", wrong_choice("n0-q0"))
    assert chapter(member, "n0")["done"] == 0


def test_complete_level_shows_badge_and_marks_floor(client_for, member):
    client = client_for(member.login)
    for key in ("n0-t0", "n0-t1", "n0-t2", "n0-t3"):
        toggle(client, key)
    answer(client, "n0-q0", correct_choice("n0-q0"))
    answer(client, "n0-q1", correct_choice("n0-q1"))
    ch = chapter(member, "n0")
    assert ch["pct"] == 100 and ch["complete"]
    html = client.get(f"/rutas/{FORMA}/?nivel=n0").content.decode()
    assert "Nivel completo" in html and "ar-floor on done" in html


def test_path_percent_and_levels_done_in_stats(client_for, member):
    ctx = services.world_context(member, LearningPath.objects.get(slug=FORMA))
    assert ctx["stats"]["pct"] == 0 and ctx["stats"]["levels_done"] == 0
    assert ctx["stats"]["levels_total"] == 5
    toggle(client_for(member.login), "n0-t0")
    ctx = services.world_context(member, LearningPath.objects.get(slug=FORMA))
    assert ctx["stats"]["pct"] == round(100 * 1 / (24 + 8))


def test_retired_items_do_not_count_and_cannot_be_toggled(client_for, member):
    Milestone.objects.filter(path__slug=FORMA, key="n0-t3").update(retired=True)
    assert chapter(member, "n0")["total"] == 5
    assert toggle(client_for(member.login), "n0-t3").status_code == 404
    QuizQuestion.objects.filter(path__slug=FORMA, key="n0-q1").update(retired=True)
    assert chapter(member, "n0")["total"] == 4
    assert answer(client_for(member.login), "n0-q1", 0).status_code == 404


def test_default_level_is_the_first_incomplete(client_for, member):
    client = client_for(member.login)
    html = client.get(f"/rutas/{FORMA}/").content.decode()
    assert 'aria-label="Nivel N0' in html
    for key in ("n0-t0", "n0-t1", "n0-t2", "n0-t3"):
        toggle(client, key)
    answer(client, "n0-q0", correct_choice("n0-q0"))
    answer(client, "n0-q1", correct_choice("n0-q1"))
    html = client.get(f"/rutas/{FORMA}/").content.decode()
    assert 'aria-label="Nivel N1' in html


# --- validaciones y permisos ---


@pytest.mark.parametrize("choice", ["99", "-1", "abc", ""])
def test_invalid_quiz_choice_is_400(client_for, member, choice):
    response = client_for(member.login).post(url("quiz", "n0-q0"), {"choice": choice})
    assert response.status_code == 400
    assert not QuizAnswer.objects.exists()


def test_actions_require_post(member_client):
    assert member_client.get(url("hitos", "n0-t0")).status_code == 405
    assert member_client.get(url("quiz", "n0-q0")).status_code == 405
    assert member_client.get(url("meta")).status_code == 405


def test_unknown_keys_and_paths_are_404(member_client):
    assert toggle(member_client, "n9-t9").status_code == 404
    assert member_client.post(url("hitos", "n0-t0", slug="no-existe")).status_code == 404


def test_external_tracks_have_no_milestone_actions(member_client):
    assert member_client.post(url("hitos", "ms-c0", slug="bentley-learn")).status_code == 404


def test_pending_person_cannot_act(client_for, make_person):
    pending = make_person("p@lev.cl", status="pending")
    response = toggle(client_for(pending.login), "n0-t0")
    assert response.status_code == 302 and response.url == "/espera/"
    assert not MilestoneCheck.objects.exists()


def test_unpublished_path_is_hidden_from_actions(client_for, member, lead):
    LearningPath.objects.filter(slug=FORMA).update(is_published=False)
    assert toggle(client_for(member.login), "n0-t0").status_code == 404
    assert toggle(client_for(lead.login), "n0-t0").status_code == 302


def test_csrf_is_enforced(member):
    client = Client(
        enforce_csrf_checks=True, REMOTE_ADDR="127.0.0.1", HTTP_TAILSCALE_USER_LOGIN=member.login
    )
    assert client.post(url("hitos", "n0-t0"), {"checked": "1"}).status_code == 403
    assert not MilestoneCheck.objects.exists()


# --- meta de certificación ---


def test_goal_can_be_set_changed_and_cleared(client_for, member):
    client = client_for(member.login)
    goal = "Autodesk Certified User: Revit"
    assert client.post(url("meta", slug=REVIT), {"goal": goal, "nivel": "n0"}).status_code == 302
    assert PathGoal.objects.get(person=member).certification_goal == goal
    html = client.get(f"/rutas/{REVIT}/").content.decode()
    assert f'<option value="{goal}" selected>' in html

    client.post(url("meta", slug=REVIT), {"goal": "ACP Revit Structural Design", "nivel": "n0"})
    assert PathGoal.objects.filter(person=member).count() == 1
    client.post(url("meta", slug=REVIT), {"goal": "", "nivel": "n0"})
    assert not PathGoal.objects.exists()


def test_goal_must_be_one_of_the_path_goals(client_for, member):
    response = client_for(member.login).post(url("meta"), {"goal": "Título inventado"})
    assert response.status_code == 400 and not PathGoal.objects.exists()


def test_goals_are_personal(client_for, make_person):
    ana, luis = make_person("ana@lev.cl"), make_person("luis@lev.cl")
    client_for(ana.login).post(url("meta", slug=REVIT), {"goal": "Autodesk Certified User: Revit"})
    assert not PathGoal.objects.filter(person=luis).exists()
    html = client_for(luis.login).get(f"/rutas/{REVIT}/").content.decode()
    assert "selected>" not in html.split('id="goal"')[1].split("</select>")[0]


# --- sin JS y con JS (respuesta parcial) ---


def test_without_js_redirects_back_to_the_level(member_client):
    response = toggle(member_client, "n1-t0")
    assert response.status_code == 302
    assert response.url == f"/rutas/{FORMA}/?nivel=n1#panel"


def test_partial_response_is_only_the_fragment_and_has_new_percentages(member_client):
    response = toggle(member_client, "n0-t0", HTTP_X_PARTIAL="1")
    html = response.content.decode()
    assert response.status_code == 200
    assert "<html" not in html and 'id="corte"' in html and 'id="panel"' in html
    assert "17 %" in html  # 1 de 6 en el nivel 0


def test_partial_get_returns_selected_level_only(member_client):
    html = member_client.get(f"/rutas/{FORMA}/?nivel=n2", HTTP_X_PARTIAL="1").content.decode()
    assert "<html" not in html and "Send to Revit" in html and "ar-cover" not in html


def test_full_page_reads_without_js(member_client):
    html = member_client.get(f"/rutas/{FORMA}/?nivel=n2").content.decode()
    assert "ar-cover" in html and "Levantamiento Digital" in html and "CC 410" in html
    assert html.count('class="ar-lv') == 5  # Project Browser
    assert html.count("ar-floor") >= 5  # corte del edificio
    assert '<em class="term">Send to Revit</em>' in html
    assert "<form" in html and 'method="post"' in html  # funciona sin JS: formularios normales
    assert "enhance.js" in html and "architecture.css" in html


def test_cover_uses_the_levantamiento_style_with_real_data(member_client):
    html = member_client.get(f"/rutas/{FORMA}/").content.decode()
    assert "levantamiento.css" in html and "levantamiento.js" in html
    assert 'data-scene="building"' in html
    assert 'class="lv-title">Ruta Forma · Coordinación' in html  # recuadro de anotación
    assert "// 01" in html and "// 05" in html  # pasos numerados como consola
    readouts = html.split('class="lv-readouts"')[1].split("</div>")[0]
    for label, value in (("Niveles", 5), ("Misiones", 24), ("Preguntas", 8)):
        assert f"{label}<b>{value}</b>" in readouts
    assert "Tu avance<b>0 %</b>" in readouts


def test_cover_readouts_follow_my_progress(client_for, member):
    toggle(client_for(member.login), "n0-t0")
    html = client_for(member.login).get(f"/rutas/{FORMA}/").content.decode()
    assert "Tu avance<b>3 %</b>" in html and "Equipo<b>1</b>" in html


def test_stats_expose_item_counts(member):
    ctx = services.world_context(member, LearningPath.objects.get(slug=FORMA))
    assert ctx["stats"]["milestones"] == 24 and ctx["stats"]["questions"] == 8


def test_path_without_a_built_world_falls_back_to_the_architecture_world(member_client):
    LearningPath.objects.filter(slug=FORMA).update(world="mechanical")
    html = member_client.get(f"/rutas/{FORMA}/").content.decode()
    assert "ar-cover" in html and "ar-lv" in html


def test_milestone_text_is_escaped(client_for, member):
    Milestone.objects.filter(path__slug=FORMA, key="n0-t0").update(
        text="<script>alert(1)</script> *Revit*"
    )
    html = client_for(member.login).get(f"/rutas/{FORMA}/?nivel=n0").content.decode()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html and '<em class="term">Revit</em>' in html


# --- el equipo en el edificio ---


def floor_marks(person, code):
    ctx = services.world_context(person, LearningPath.objects.get(slug=FORMA))
    floor = next(f for f in ctx["building"]["floors"] if f["code"] == code)
    return [m["initials"] for m in floor["marks"]], ctx


def test_team_member_appears_on_the_floor_where_they_last_worked(client_for, make_person):
    ana = make_person("ana.perez@lev.cl")
    luis = make_person("luis@lev.cl")
    toggle(client_for(ana.login), "n1-t0")
    toggle(client_for(ana.login), "n3-t0")

    marks_n3, _ = floor_marks(luis, "n3")
    marks_n1, _ = floor_marks(luis, "n1")
    assert marks_n3 == ["AP"] and marks_n1 == []
    html = client_for(luis.login).get(f"/rutas/{FORMA}/").content.decode()
    assert "<title>ana</title>" in html or "ana.perez" in html or "ar-mark" in html


def test_my_own_mark_is_flagged(client_for, member):
    toggle(client_for(member.login), "n2-t0")
    html = client_for(member.login).get(f"/rutas/{FORMA}/").content.decode()
    assert "ar-mark me" in html


def test_pending_people_do_not_appear(client_for, make_person):
    pending = make_person("p@lev.cl", status="approved")
    toggle(client_for(pending.login), "n2-t0")
    pending.status = "pending"
    pending.save()
    other = make_person("o@lev.cl")
    marks, ctx = floor_marks(other, "n2")
    assert marks == [] and ctx["stats"]["participants"] == 0


def test_participants_counts_people_with_progress(client_for, make_person):
    for login in ("a@lev.cl", "b@lev.cl"):
        toggle(client_for(make_person(login).login), "n0-t0")
    viewer = make_person("v@lev.cl")
    _, ctx = floor_marks(viewer, "n0")
    assert ctx["stats"]["participants"] == 2


def test_more_than_four_people_show_a_counter(client_for, make_person):
    for i in range(6):
        toggle(client_for(make_person(f"p{i}@lev.cl").login), "n0-t0")
    ctx = services.world_context(make_person("v@lev.cl"), LearningPath.objects.get(slug=FORMA))
    floor = next(f for f in ctx["building"]["floors"] if f["code"] == "n0")
    assert len(floor["marks"]) == 4 and floor["extra"] == 2


# --- servicios ---


def test_services_validate_input(member):
    milestone = Milestone.objects.get(path__slug=FORMA, key="n0-t0")
    question = QuizQuestion.objects.get(path__slug=FORMA, key="n0-q0")
    with pytest.raises(ValueError):
        services.answer_question(member, question, 50)
    milestone.retired = True
    with pytest.raises(ValueError):
        services.set_milestone(member, milestone, True)


@pytest.mark.parametrize(
    ("done", "total", "expected"),
    [(0, 0, 0), (0, 8, 0), (1, 8, 13), (1, 6, 17), (3, 6, 50), (7, 8, 88), (8, 8, 100)],
)
def test_percent_rounds_half_up(done, total, expected):
    assert services.percent(done, total) == expected


def test_initials():
    class P:
        def __init__(self, name, login="x@lev.cl"):
            self.name, self.login = name, login

    assert services.initials(P("Ana Muñoz")) == "AM"
    assert services.initials(P("ana")) == "A"
    assert services.initials(P("luis.gomez")) == "LG"
