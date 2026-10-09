"""Puesta a punto en p340: Teo sin razonamiento a la vista, aprobar desde la VM y primer día organizado."""

import json

import httpx
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts import services
from apps.accounts.models import Person, PersonStatus
from apps.assistant import client
from apps.community.models import Thread
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db
LEAK = "Here's a thinking process:\n\n1.  **Analyze User Input:** The user wants me to introduce myself"


@pytest.fixture(autouse=True)
def api(settings):
    settings.NIM_API_KEY = "nvapi-X"
    client._no_think_rejected.clear()
    yield
    client.TRANSPORT = None
    client._no_think_rejected.clear()


def reply(content):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


# --- Teo: solo la respuesta final, en español ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        (LEAK, ""),  # error real en p340: razonamiento sin etiquetas y en inglés
        (
            "Okay, the user asks who I am. </think>Soy Teo.",
            "Soy Teo.",
        ),  # el <think> lo abrió la plantilla
        ("pienso…</think>\n\n¡Hola! Soy Teo.", "¡Hola! Soy Teo."),
        ("Hola, soy Teo, tu colega de terreno.", "Hola, soy Teo, tu colega de terreno."),
        ("Thinking about Revit families is fun", "Thinking about Revit families is fun"),
    ],
)
def test_strip_reasoning_without_tags(raw, clean):
    assert client.strip_reasoning(raw) == clean


def test_requests_ask_the_model_not_to_think(settings):
    sent = []
    client.TRANSPORT = httpx.MockTransport(
        lambda r: sent.append(json.loads(r.content)) or reply("Hola")
    )
    client.chat([{"role": "user", "content": "hola"}])
    assert sent[0]["chat_template_kwargs"] == {"enable_thinking": False}


def test_a_model_that_rejects_the_option_is_asked_again_without_it(settings):
    sent = []

    def handler(request):
        body = json.loads(request.content)
        sent.append(body)
        if "chat_template_kwargs" in body:
            return httpx.Response(400, json={"detail": "unexpected field chat_template_kwargs"})
        return reply("Hola, soy Teo.")

    client.TRANSPORT = httpx.MockTransport(handler)
    assert client.chat([{"role": "user", "content": "hola"}])[0] == "Hola, soy Teo."
    client.chat([{"role": "user", "content": "otra"}])
    assert ["chat_template_kwargs" in b for b in sent] == [True, False, False]  # se recuerda


def test_a_model_that_only_reasons_falls_back_to_the_next(settings):
    settings.NIM_MODEL = "a/piensa"
    settings.NIM_MODEL_FALLBACKS = ["b/responde"]

    def handler(request):
        model = json.loads(request.content)["model"]
        return reply(LEAK if model == "a/piensa" else "Soy Teo, tu asistente.")

    client.TRANSPORT = httpx.MockTransport(handler)
    text, _, _ = client.chat([{"role": "user", "content": "hola"}])
    assert text == "Soy Teo, tu asistente." and client.last_model == "b/responde"


def test_system_prompt_demands_spanish_and_only_the_final_answer(member):
    from apps.assistant import context

    messages, _ = context.build(member, "hola")
    assert "español" in messages[0]["content"] and "razonamiento" in messages[0]["content"]


# --- aprobar desde la VM -----------------------------------------------------------------------------------------


def test_aprobar_lists_pending_people(make_person, capsys):
    make_person("nueva@lev.cl", status=PersonStatus.PENDING)
    call_command("aprobar")
    assert "nueva@lev.cl" in capsys.readouterr().out


def test_aprobar_approves_and_promotes_an_existing_person(make_person):
    make_person("cristobal@gmail.com", status=PersonStatus.PENDING)
    call_command("aprobar", "Cristobal@gmail.com", "--rol", "admin")
    person = Person.objects.get(login="cristobal@gmail.com")
    assert person.status == PersonStatus.APPROVED and person.role == "admin"
    assert Notification.objects.filter(recipient=person, kind="welcome").count() == 1


def test_aprobar_before_first_login_lets_the_person_straight_in(client_for):
    call_command("aprobar", "cmunoz@jej.cl", "--rol", "lead")
    response = client_for("cmunoz@jej.cl").get("/")
    assert response.status_code == 200 and "Esperando aprobación" not in response.content.decode()
    person = Person.objects.get(login="cmunoz@jej.cl")
    assert person.role == "lead" and person.last_login is not None
    assert not Notification.objects.filter(
        kind="person_pending"
    ).exists()  # no avisa una solicitud ya resuelta


def test_aprobar_is_idempotent_and_rejects_bad_logins(make_person):
    call_command("aprobar", "ana2@lev.cl")
    call_command("aprobar", "ana2@lev.cl")
    assert Person.objects.filter(login="ana2@lev.cl").count() == 1
    assert Notification.objects.filter(kind="welcome").count() == 1
    with pytest.raises(CommandError):
        call_command("aprobar", "sin-arroba")


def test_bootstrap_admin_stays_admin_whatever_the_command_says(settings):
    settings.BOOTSTRAP_ADMINS = ["jefa@lev.cl"]
    person, created = services.grant_access("jefa@lev.cl", "member")
    assert created and person.role == "admin" and person.status == PersonStatus.APPROVED


# --- primer día organizado ---------------------------------------------------------------------------------------


@pytest.fixture
def seeded():
    call_command("seed_catalog", verbosity=0)


def test_puesta_en_marcha_pins_one_welcome_thread(seeded, settings, capsys):
    settings.BOOTSTRAP_ADMINS = ["cmunoz@jej.cl"]
    call_command("puesta_en_marcha")
    call_command("puesta_en_marcha")
    thread = Thread.objects.get(title__startswith="Bienvenida a la Academia")
    assert (
        thread.is_pinned
        and thread.author.login == "cmunoz@jej.cl"
        and thread.category.slug == "general"
    )
    out = capsys.readouterr().out
    assert "ya existe" in out and "aún no entra" in out and "rutas publicadas" in out


def test_puesta_en_marcha_needs_an_author(seeded, settings):
    settings.BOOTSTRAP_ADMINS = []
    with pytest.raises(CommandError, match="BOOTSTRAP_ADMINS"):
        call_command("puesta_en_marcha")


def test_home_shows_first_steps_until_they_are_done(seeded, client_for, member):
    html = client_for(member.login).get("/").content.decode()
    assert "Primeros pasos" in html and "Sube tu primer certificado" in html
    member.headline = "Modeladora BIM"
    member.save()
    html = client_for(member.login).get("/").content.decode()
    assert 'class="done"><a href="/perfil/editar/">' in html


def test_first_steps_disappear_when_all_are_done(seeded, member, settings, tmp_path):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.community import forum
    from apps.community.models import Category
    from apps.core import dashboard
    from apps.credentials import services as creds
    from apps.paths.models import Milestone
    from apps.progress import services as progress

    settings.MEDIA_ROOT = tmp_path
    member.character_class = Person._meta.get_field("character_class").choices[0][0]
    member.save()
    progress.set_milestone(member, Milestone.objects.filter(retired=False).first(), True)
    pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF\n" + b"x" * 200
    creds.create_credential(
        member,
        {"title": "Curso", "kind": "completion", "visibility": "private"},
        SimpleUploadedFile("c.pdf", pdf),
    )
    assert dashboard.first_steps(member) is not None
    forum.create_thread(
        member, Category.objects.get(slug="general"), "discussion", "Hola", "Soy Ana"
    )
    assert dashboard.first_steps(member) is None


# --- ícono y app instalable -------------------------------------------------------------------------------------------


def test_pages_carry_the_icon_and_the_manifest(client_for, member):
    html = client_for(member.login).get("/").content.decode()
    for needle in (
        'rel="manifest"',
        'rel="apple-touch-icon"',
        "core/app/icon.svg",
        'name="theme-color"',
    ):
        assert needle in html


def test_the_waiting_page_also_has_the_icon(client_for, make_person):
    make_person("nuevo@lev.cl", status=PersonStatus.PENDING)
    html = client_for("nuevo@lev.cl").get("/", follow=True).content.decode()
    assert "Esperando aprobación" in html and 'rel="manifest"' in html


def test_manifest_icons_exist():
    from pathlib import Path

    from django.conf import settings

    folder = Path(settings.BASE_DIR) / "apps/core/static/core/app"
    manifest = json.loads((folder / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["start_url"] == "/" and manifest["display"] == "standalone"
    assert all((folder / icon["src"]).is_file() for icon in manifest["icons"])
    assert any(icon.get("purpose") == "maskable" for icon in manifest["icons"])
