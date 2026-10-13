"""Diapositivas por nivel (pasos `?paso=`), quiz en su página y fotos privadas de los cursos (`cursos:foto`)."""

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.catalog import guides
from apps.core import private_files
from apps.gamification.models import XPEvent
from apps.paths.models import LearningPath, QuizQuestion
from apps.progress import services

pytestmark = pytest.mark.django_db

FORMA = "forma-coordinacion"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64

SLIDES = [
    {
        "title": "Qué es un modelo",
        "body": "Un **modelo** guarda datos, no solo líneas.",
        "points": ["Primero punto", "Segundo punto"],
        "image": "core/img/bim/gemelo-digital.svg",
        "caption": "Gemelo digital",
        "callout": {"kind": "dato", "text": "El *RTK* corrige en tiempo real."},
        "terms": ["*RTK*", "*NTRIP*"],
        "diagram": {
            "nodes": [
                {
                    "id": "base",
                    "label": "Base GNSS",
                    "sub": "coordenada conocida",
                    "kind": "equipo",
                    "x": 15,
                    "y": 40,
                },
                {
                    "id": "rover",
                    "label": "Rover",
                    "sub": "mide el punto",
                    "kind": "persona",
                    "x": 50,
                    "y": 40,
                },
                {
                    "id": "nube",
                    "label": "Nube <script>x</script>",
                    "kind": "producto",
                    "x": 85,
                    "y": 40,
                },
            ],
            "edges": [
                {"from": "base", "to": "rover", "label": "correcciones RTCM", "flow": True},
                {"from": "rover", "to": "nube", "label": "puntos"},
            ],
            "steps": [["base"], ["rover", "base-rover"], ["nube", "rover-nube"]],
        },
    },
    {
        "title": "Con foto real",
        "body": "Texto.",
        "image": "priv:base-rover.png",
        "caption": "Base y rover",
    },
    {
        "title": "<script>alert(1)</script>",
        "image": "../../etc/passwd.png",
        "callout": {"kind": "inventado", "text": "no debe salir"},
    },
    {"sin": "titulo"},
    "no es un dict",
]


@pytest.fixture(autouse=True)
def seeded(settings, tmp_path):
    settings.PRIVATE_COURSES_DIR = tmp_path / "cursos"
    call_command("seed_catalog", verbosity=0)


@pytest.fixture
def slides(monkeypatch):
    """La ruta real, con diapositivas sintéticas en el nivel n0 (la semilla no se toca)."""
    real = guides._route_json

    def patched(slug):
        data = real(slug)
        if slug != FORMA:
            return data
        levels = [
            dict(lv, slides=SLIDES) if lv.get("code") == "n0" else lv for lv in data["levels"]
        ]
        return {**data, "levels": levels}

    monkeypatch.setattr(guides, "_route_json", patched)


@pytest.fixture
def photo(settings):
    folder = settings.PRIVATE_COURSES_DIR / FORMA / "fotos"
    folder.mkdir(parents=True)
    (folder / "base-rover.png").write_bytes(PNG)
    return folder


def page(client, nivel="n0", paso=None, **extra):
    q = f"?nivel={nivel}" + (f"&paso={paso}" if paso is not None else "")
    return client.get(f"/rutas/{FORMA}/{q}", **extra)


def ctx_for(person, nivel="n0", paso=None):
    return services.world_context(person, LearningPath.objects.get(slug=FORMA), nivel, paso)


# --- validación de la clave `slides` ---------------------------------------------------------------------------------


def test_slides_for_validates_and_drops_the_invalid(slides, photo):
    got = guides.slides_for(FORMA, "n0")
    assert [s["title"] for s in got] == [
        "Qué es un modelo",
        "Con foto real",
        "<script>alert(1)</script>",
    ]
    assert got[0]["callout"] == {
        "kind": "dato",
        "label": "Dato",
        "text": "El *RTK* corrige en tiempo real.",
    }
    assert got[0]["image_url"].endswith("gemelo-digital.svg")
    assert got[1]["image_url"] == f"/cursos/foto/{FORMA}/base-rover.png"
    assert (
        got[2]["image"] == "" and got[2]["callout"] is None
    )  # imagen con traversal y tipo de aviso inválidos
    assert guides.slides_for(FORMA, "n1") == [] and guides.slides_for("no-existe", "n0") == []


def test_missing_private_photo_gives_no_image(slides):
    assert guides.slides_for(FORMA, "n0")[1]["image_url"] == ""


def test_private_route_json_is_read_when_there_is_no_seed(settings):
    folder = settings.PRIVATE_COURSES_DIR / "mi-curso-privado"
    folder.mkdir(parents=True)
    (folder / "ruta.json").write_text(
        '{"levels": [{"code": "p0", "slides": [{"title": "Hola"}]}]}', encoding="utf-8"
    )
    assert [s["title"] for s in guides.slides_for("mi-curso-privado", "p0")] == ["Hola"]
    assert guides._route_json("../x") == {}


# --- navegación por pasos --------------------------------------------------------------------------------------------


def test_default_step_is_the_cover(slides, member, member_client):
    html = page(member_client).content.decode()
    ctx = ctx_for(member)
    assert ctx["step"]["key"] == "portada" and ctx["step_no"] == 1
    assert f"Paso 1 de {ctx['step_total']}" in html and "Qué vas a lograr" in html
    assert 'data-step="portada"' in html and "ar-goal" in html
    keys = [s["key"] for s in ctx["steps"]]
    assert keys[:4] == ["portada", "1", "2", "3"] and keys[-1] == "notas"
    assert keys.index("practica") < keys.index("quiz") < keys.index("notas")
    assert [t["label"] for t in ctx["tabs"]][:3] == ["Aprender", "Practicar", "Evaluar"]


def test_slide_step_shows_one_idea_with_callout_terms_and_zoom(slides, member_client):
    html = page(member_client, paso="1").content.decode()
    assert "Qué es un modelo" in html and "<strong>modelo</strong>" in html
    assert "Primero punto" in html and "sl-callout k-dato" in html and "Ojo con esto" not in html
    assert '<em class="term">RTK</em>' in html and "sl-terms" in html
    assert "<details" in html and "gemelo-digital.svg" in html and "Gemelo digital" in html
    assert html.count("sl-h sl-title") == 1  # una idea por página
    assert "Paso 2 de" in html and f'href="/rutas/{FORMA}/?nivel=n0&amp;paso=2#panel"' in html


def test_diagram_renders_nodes_edges_and_parts(slides, member_client):
    html = page(member_client, paso="1").content.decode()
    assert html.count('class="dg-node') == 3 and html.count('class="dg-edge"') == 2
    assert (
        "Base GNSS" in html
        and "correcciones RTCM" in html
        and "k-equipo" in html
        and "k-persona" in html
    )
    assert html.count("dg-dot") == 1  # solo la flecha con flow
    assert html.count('class="dg-step dg-c') == 2 and "dg-c1" in html and "dg-c2" in html
    assert 'data-s="1"' in html and 'data-s="2"' in html
    assert "<script>x</script>" not in html and "Nube &lt;script&gt;x&lt;/script&gt;" in html
    assert (
        "Base GNSS → Rover: correcciones RTCM" in html
    )  # texto alternativo para lectores de pantalla
    assert "dg-canvas" not in page(member_client, paso="2").content.decode()


def test_diagram_validation_and_caps():
    d = guides._diagram(
        {
            "nodes": [
                {"id": "a", "label": "A", "x": 10, "y": 10},
                {"id": "a", "label": "repetido"},
                {"id": "B C", "label": "id inválido"},
                {"id": "b", "label": "B", "kind": "raro", "x": 500, "y": "x"},
                {"id": "c", "label": ""},
            ],
            "edges": [
                {"from": "a", "to": "b"},
                {"from": "a", "to": "a"},
                {"from": "a", "to": "zz"},
                {"from": "a", "to": "b"},
                "no es dict",
            ],
        }
    )
    assert [n["id"] for n in d["nodes"]] == ["a", "b"]
    assert (
        d["nodes"][1]["kind"] == "dato"
        and d["nodes"][1]["x"] == 100.0
        and d["nodes"][1]["y"] == 50.0
    )
    assert [e["id"] for e in d["edges"]] == ["a-b"]
    assert (
        d["parts"] == [] and d["total"] == 1 and all(n["step"] == 0 for n in d["nodes"])
    )  # sin steps, todo visible
    many = {"nodes": [{"id": f"n{i}", "label": "x"} for i in range(30)]}
    many["edges"] = [{"from": f"n{i}", "to": f"n{i + 1}"} for i in range(11)] * 3
    capped = guides._diagram(many)
    assert len(capped["nodes"]) == 12 and len(capped["edges"]) <= 11
    assert guides._diagram({"nodes": []}) is None and guides._diagram("x") is None


def test_diagram_steps_ignore_unknown_and_repeated_ids():
    d = guides._diagram(
        {
            "nodes": [
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B"},
                {"id": "c", "label": "C"},
            ],
            "edges": [{"from": "a", "to": "b"}],
            "steps": [["a", "nada"], ["a", "b", "a-b"], [], ["c"]],
        }
    )
    steps = {n["id"]: n["step"] for n in d["nodes"]}
    assert steps == {"a": 0, "b": 1, "c": 2} and d["edges"][0]["step"] == 1
    assert d["parts"] == [1, 2] and d["total"] == 3


def test_slide_text_is_escaped(slides, member_client):
    html = page(member_client, paso="3").content.decode()
    assert (
        "<script>alert(1)</script>" not in html and "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    )


def test_prev_next_walk_the_steps(slides, member):
    ctx = ctx_for(member, paso="2")
    assert ctx["step_prev"].endswith("?nivel=n0&paso=1#panel")
    assert ctx["step_next"].endswith("?nivel=n0&paso=3#panel")
    assert ctx_for(member, paso="portada")["step_prev"] is None


def test_after_the_last_step_next_goes_to_the_next_levels_cover(slides, member, member_client):
    ctx = ctx_for(member, paso="notas")
    assert ctx["step_next"].endswith("?nivel=n1&paso=portada#panel") and ctx["step_next_is_level"]
    assert "Siguiente nivel" in page(member_client, paso="notas").content.decode()
    last = ctx_for(member, nivel="n4", paso="notas")
    assert last["step_next"] is None
    assert last["step_prev"].startswith(f"/rutas/{FORMA}/?nivel=n4&paso=")


def test_first_step_goes_back_to_the_previous_level(member):
    assert ctx_for(member, nivel="n1")["step_prev"].endswith("?nivel=n0&paso=portada#panel")


@pytest.mark.parametrize("paso", ["zzz", "99", "0", "-1", "../x", "", "<b>", "guia"])
def test_invalid_step_falls_back_to_the_cover(member, member_client, paso):
    # «guia» es válido solo si el nivel trae guía; n1 de esta ruta no la tiene y debe caer en la portada
    ctx = ctx_for(member, nivel="n1", paso=paso)
    if paso == "guia" and any(s["key"] == "guia" for s in ctx["steps"]):
        return
    assert ctx["step"]["key"] == "portada"
    assert page(member_client, "n1", paso).status_code == 200


def test_level_without_slides_still_has_every_other_step(member, member_client):
    ctx = ctx_for(member, nivel="n1")
    keys = [s["key"] for s in ctx["steps"]]
    assert keys[0] == "portada" and not any(k.isdigit() for k in keys)
    assert {"practica", "quiz", "notas"} <= set(keys)
    assert ctx_for(member, nivel="n1", paso="1")["step"]["key"] == "portada"  # no hay diapositiva 1
    for k in keys:
        assert page(member_client, "n1", k).status_code == 200


def test_every_step_of_every_level_renders(slides, member_client, member):
    for ch in services.world_context(member, LearningPath.objects.get(slug=FORMA))["chapters"]:
        for step in ctx_for(member, ch["level"].code)["steps"]:
            html = page(member_client, ch["level"].code, step["key"]).content.decode()
            assert 'id="panel"' in html and f"Paso {step['n']} de" in html


def test_guide_and_resources_are_steps_when_the_level_has_them(member, member_client):
    for ch in services.world_context(member, LearningPath.objects.get(slug=FORMA))["chapters"]:
        code = ch["level"].code
        keys = {s["key"] for s in ctx_for(member, code)["steps"]}
        html = page(member_client, code, "recursos").content.decode()
        assert ("recursos" in keys) == ("ar-res" in html) or "recursos" not in keys
        if "guia" in keys:
            assert "Guía rápida" in page(member_client, code, "guia").content.decode()


# --- misiones y quiz en su propia página ---------------------------------------------------------------------------


def test_missions_page_keeps_the_hooks(member_client):
    html = page(member_client, paso="practica").content.decode()
    assert (
        'data-fid="ms-n0-t0"' in html and 'aria-pressed="false"' in html and "data-enhance" in html
    )


def test_quiz_is_its_own_page_with_summary_and_explanation(member_client):
    html = page(member_client, paso="quiz").content.decode()
    assert "0 de 2 correctas" in html and 'data-fid="q-n0-q0-0"' in html and 'class="qn">1<' in html
    assert "ar-fb" not in html and "ms-n0-t0" not in html  # sin misiones aquí; aún sin explicación
    q = QuizQuestion.objects.get(path__slug=FORMA, key="n0-q0")

    partial = member_client.post(
        f"/rutas/{FORMA}/quiz/n0-q0/", {"choice": str(q.answer_index)}, HTTP_X_PARTIAL="1"
    ).content.decode()
    assert 'data-step="quiz"' in partial  # responder te deja en el quiz
    assert "1 de 2 correctas" in partial and 'class="ar-fb"' in partial and "Correcto." in partial
    assert "sin responder: 1" in partial and 'class="right"' in partial


def test_answering_without_js_returns_to_the_quiz_step(member_client):
    q = QuizQuestion.objects.get(path__slug=FORMA, key="n0-q0")
    response = member_client.post(
        f"/rutas/{FORMA}/quiz/n0-q0/", {"choice": str(q.answer_index + 1)}
    )
    assert (
        response.status_code == 302 and response.url == f"/rutas/{FORMA}/?nivel=n0&paso=quiz#panel"
    )
    html = member_client.get(response.url).content.decode()
    assert "Casi." in html and "0 de 2 correctas" in html
    response = member_client.post(f"/rutas/{FORMA}/hitos/n0-t0/", {"checked": "1"})
    assert response.url == f"/rutas/{FORMA}/?nivel=n0&paso=practica#panel"


def test_goal_form_keeps_the_step(member_client):
    response = member_client.post(
        f"/rutas/{FORMA}/meta/", {"goal": "", "nivel": "n2", "paso": "quiz"}
    )
    assert response.url == f"/rutas/{FORMA}/?nivel=n2&paso=quiz#panel"
    response = member_client.post(
        f"/rutas/{FORMA}/meta/", {"goal": "", "nivel": "n2", "paso": "x/../y"}
    )
    assert response.url == f"/rutas/{FORMA}/?nivel=n2#panel"


def test_progress_xp_and_completion_work_the_same_through_steps(slides, member, member_client):
    for m in ("n0-t0", "n0-t1", "n0-t2", "n0-t3"):
        member_client.post(f"/rutas/{FORMA}/hitos/{m}/", {"checked": "1"})
    for q in QuizQuestion.objects.filter(path__slug=FORMA, level__code="n0"):
        for _ in range(2):  # repetir no duplica XP
            member_client.post(f"/rutas/{FORMA}/quiz/{q.key}/", {"choice": str(q.answer_index)})
    events = XPEvent.objects.filter(person=member).exclude(kind="streak")
    sources = list(events.values_list("source", flat=True))
    assert len(sources) == len(set(sources))  # una vez por origen
    assert {"milestone", "quiz", "chapter"} <= set(events.values_list("kind", flat=True))
    ctx = ctx_for(member)
    assert ctx["current"]["complete"] and ctx["current"]["quiz_right"] == 2
    for paso in ("portada", "1", "practica", "quiz", "notas"):
        assert "Nivel completo" in page(member_client, paso=paso).content.decode()


def test_query_count_does_not_grow_with_the_slides(monkeypatch, slides, member_client):
    def count(paso):
        with CaptureQueriesContext(connection) as cq:
            assert page(member_client, paso=paso).status_code == 200
        return len(cq)

    count("portada")  # calienta sesión y cachés
    few = {p: count(p) for p in ("portada", "1", "practica", "quiz", "notas")}
    real = guides._route_json
    many = [{"title": f"Idea {i}", "body": "x"} for i in range(25)]

    def patched(slug):
        data = real(slug)
        if slug != FORMA:
            return data
        return {
            **data,
            "levels": [
                dict(lv, slides=many) if lv["code"] == "n0" else lv for lv in data["levels"]
            ],
        }

    monkeypatch.setattr(guides, "_route_json", patched)
    assert {p: count(p) for p in few} == few
    assert max(few.values()) < 60


# --- fotos privadas ------------------------------------------------------------------------------------------------


def test_photo_is_served_to_approved_people_with_safe_headers(slides, photo, member_client):
    url = f"/cursos/foto/{FORMA}/base-rover.png"
    resp = member_client.get(url)
    assert resp.status_code == 200 and resp["Content-Type"] == "image/png"
    assert (
        resp["X-Content-Type-Options"] == "nosniff" and "sandbox" in resp["Content-Security-Policy"]
    )
    assert resp["Cache-Control"].startswith("private")
    assert b"".join(resp.streaming_content) == PNG
    assert url in page(member_client, paso="2").content.decode()  # la diapositiva la usa


def test_photo_is_not_served_to_pending_or_anonymous_people(photo, make_person, client_for):
    url = f"/cursos/foto/{FORMA}/base-rover.png"
    pending = make_person("nuevo@example.com", status="pending")
    assert client_for(pending.login).get(url).status_code in (302, 403, 404)
    assert client_for("").get(url).status_code in (302, 401, 403, 404)
    rejected = make_person("fuera@example.com", status="suspended")
    assert client_for(rejected.login).get(url).status_code in (302, 403, 404)


def test_photo_of_a_draft_route_is_404_for_members_but_not_for_leads(photo, member_client, lead):
    from tests.conftest import tailscale_client

    LearningPath.objects.filter(slug=FORMA).update(is_published=False)
    url = f"/cursos/foto/{FORMA}/base-rover.png"
    assert member_client.get(url).status_code == 404
    assert tailscale_client(lead.login).get(url).status_code == 200


def test_photo_of_unknown_route_or_file_is_404(photo, member_client):
    assert member_client.get("/cursos/foto/no-existe/base-rover.png").status_code == 404
    assert member_client.get(f"/cursos/foto/{FORMA}/otra.png").status_code == 404


@pytest.mark.parametrize(
    "name",
    [
        "..%2Fruta.json",
        "%2E%2E%2Fbase-rover.png",
        "a/../base-rover.png",
        "..\\base-rover.png",
        "base-rover.png%00.txt",
        "ruta.json",
        ".png",
        "base..rover.png",
    ],
)
def test_photo_rejects_traversal_and_odd_names(photo, settings, member_client, name):
    (settings.PRIVATE_COURSES_DIR / FORMA / "ruta.json").write_text("{}", encoding="utf-8")
    assert member_client.get(f"/cursos/foto/{FORMA}/{name}").status_code == 404


def test_shared_module_rules(tmp_path):
    (tmp_path / "ok.webp").write_bytes(b"x")
    (tmp_path / "x.txt").write_text("x")
    assert private_files.safe_file(tmp_path, "ok.webp").name == "ok.webp"
    assert private_files.content_type(tmp_path / "ok.webp") == "image/webp"
    for bad in ("x.txt", "../ok.webp", "sub/ok.webp", "", None, "ok.exe", "a" * 90 + ".png"):
        assert private_files.safe_file(tmp_path, bad) is None
    assert guides.photo_path("../x", "ok.png") is None


def test_missing_photo_does_not_break_the_slide(slides, member_client):
    html = page(member_client, paso="2").content.decode()  # no hay carpeta de fotos instalada
    assert "Con foto real" in html and "sl-fig" not in html and "/cursos/foto/" not in html
