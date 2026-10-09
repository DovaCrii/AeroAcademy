import json

import httpx
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command

from apps.assistant import client, context, search, services
from apps.assistant.models import BotLog, BotUsage
from apps.community import forum, moderation
from apps.community import services as notes
from apps.community.models import Category
from apps.credentials import services as creds
from apps.paths.models import LearningPath

pytestmark = pytest.mark.django_db
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF\n" + b"x" * 200
SECRET_KEY = "nvapi-TEST-KEY-NOT-REAL"


@pytest.fixture(autouse=True)
def bot(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.NIM_API_KEY = SECRET_KEY
    settings.BOT_ENABLED = True
    settings.BOT_DAILY_LIMIT = 40
    call_command("seed_catalog", verbosity=0)
    yield
    client.TRANSPORT = None


class Recorder:
    """Transporte simulado que guarda cada petición saliente."""

    def __init__(self, status=200, content="Hola, soy Teo [1].", raise_timeout=False):
        self.requests, self.status, self.content, self.raise_timeout = (
            [],
            status,
            content,
            raise_timeout,
        )

    def __call__(self, request):
        if self.raise_timeout:
            raise httpx.ReadTimeout("lento", request=request)
        self.requests.append(request)
        body = {"choices": [{"message": {"content": self.content}}], "usage": {"total_tokens": 42}}
        return httpx.Response(self.status, json=body if self.status == 200 else {"error": "x"})

    def install(self):
        client.TRANSPORT = httpx.MockTransport(self)
        return self

    @property
    def sent(self):
        return "\n".join(r.content.decode() for r in self.requests)


def ask(person, question="¿Qué es Forma Home?"):
    return services.answer(person, question)


# --- llamada y respaldos ------------------------------------------------------------------------------------------


def test_normal_answer_has_sources_and_metadata_only_log(member):
    rec = Recorder().install()
    out = ask(member)
    assert out.status == "ok" and out.text.startswith("Hola") and out.mood == "happy"
    assert any("Forma Home" in s["title"] for s in out.sources)
    request = rec.requests[0]
    assert request.url == "https://integrate.api.nvidia.com/v1/chat/completions"
    assert request.headers["authorization"] == f"Bearer {SECRET_KEY}"
    log = BotLog.objects.get()
    assert log.tokens == 42 and log.error == "" and log.person == member
    # el log no tiene dónde guardar la pregunta ni la respuesta
    assert {f.name for f in BotLog._meta.get_fields()} == {
        "id",
        "person",
        "created_at",
        "kind",
        "latency_ms",
        "tokens",
        "error",
    }


@pytest.mark.parametrize(
    ("status", "code"), [(401, "auth"), (403, "auth"), (429, "rate"), (500, "http")]
)
def test_http_errors_give_the_friendly_message_and_refund_the_slot(member, status, code):
    Recorder(status=status).install()
    out = ask(member)
    assert out.status == "error" and "empañó el lente" in out.text
    assert BotLog.objects.get().error == code
    assert services.remaining(member) == 40


def test_timeout_and_network_errors(member):
    Recorder(raise_timeout=True).install()
    assert ask(member).status == "error"
    assert BotLog.objects.get().error == "timeout"
    client.TRANSPORT = httpx.MockTransport(
        lambda r: (_ for _ in ()).throw(httpx.ConnectError("x", request=r))
    )
    assert ask(member).status == "error"
    assert list(BotLog.objects.values_list("error", flat=True).order_by("id")) == [
        "timeout",
        "network",
    ]


@pytest.mark.parametrize(
    "payload", [{"nope": 1}, {"choices": []}, {"choices": [{"message": {"content": ""}}]}]
)
def test_malformed_responses(member, payload):
    client.TRANSPORT = httpx.MockTransport(lambda r: httpx.Response(200, json=payload))
    assert ask(member).status == "error"
    assert BotLog.objects.get().error == "bad_response"


def test_non_json_response(member):
    client.TRANSPORT = httpx.MockTransport(lambda r: httpx.Response(200, content=b"<html>"))
    assert ask(member).status == "error"


def test_the_api_key_never_reaches_logs_or_answers(member, caplog):
    Recorder(status=401).install()
    out = ask(member)
    assert SECRET_KEY not in out.text and SECRET_KEY not in caplog.text
    assert SECRET_KEY not in repr(list(BotLog.objects.values()))


# --- apagado y límite ---------------------------------------------------------------------------------------------


def test_disabled_or_without_key_the_site_still_works(client_for, member, settings):
    rec = Recorder().install()
    settings.NIM_API_KEY = ""
    out = ask(member)
    assert out.status == "disabled" and out.mood == "sleep" and not rec.requests
    assert client_for(member.login).get("/").status_code == 200
    page = client_for(member.login).get("/teo/").content.decode()
    assert "durmiendo" in page
    settings.NIM_API_KEY, settings.BOT_ENABLED = SECRET_KEY, False
    assert ask(member).status == "disabled"
    assert "teo-sleep.svg" in client_for(member.login).get("/").content.decode()


def test_daily_limit(member, settings):
    settings.BOT_DAILY_LIMIT = 2
    rec = Recorder().install()
    assert ask(member).status == "ok" and ask(member).status == "ok"
    out = ask(member)
    assert out.status == "limit" and "mañana seguimos" in out.text
    assert len(rec.requests) == 2
    assert BotUsage.objects.get().count == 2


def test_limit_is_per_person(member, lead, settings):
    settings.BOT_DAILY_LIMIT = 1
    Recorder().install()
    assert ask(member).status == "ok" and ask(lead).status == "ok" and ask(member).status == "limit"


def test_empty_and_long_questions(member):
    rec = Recorder().install()
    assert ask(member, "   ").status == "empty" and not rec.requests
    ask(member, "x " * 600)
    sent = json.loads(rec.requests[0].content)["messages"][1]["content"]
    assert len(sent.split("PREGUNTA:\n")[1]) <= context.QUESTION_MAX


# --- privacidad -----------------------------------------------------------------------------------------------------


def test_nothing_from_credentials_or_logins_reaches_the_payload(member, lead):
    unique = "ZXQ-CRED-ID-98765"
    cred = creds.create_credential(
        member,
        {
            "title": "Certificado Secretísimo QWERTY",
            "issuer": "Emisor Privado ZZZ",
            "credential_id": unique,
            "verify_url": "https://verify.example/secret-token-abc",
            "issued_on": "2026-01-02",
            "expires_on": "2027-01-02",
            "kind": "certification",
            "visibility": "private",
        },
        SimpleUploadedFile("c.pdf", PDF),
    )
    creds.verify(cred, lead)
    rec = Recorder().install()
    ask(member, "mi certificado verificado, su emisor, su identificador y su vencimiento")
    ask(lead, "¿qué me falta?")
    sent = rec.sent
    for forbidden in (
        unique,
        "Secretísimo",
        "Emisor Privado",
        "secret-token-abc",
        "2027-01-02",
        member.login,
        lead.login,
        cred.file.name,
        cred.file_sha256,
        SECRET_KEY,
    ):
        assert forbidden not in sent, forbidden


def test_only_the_visible_name_and_pending_titles_identify_the_person(member):
    rec = Recorder().install()
    ask(member, "¿Qué sigue?")
    sent = json.loads(rec.requests[0].content)["messages"][1]["content"]
    assert member.name in sent and member.login not in sent and "@" not in sent
    assert "MISIONES PENDIENTES" in sent


def test_hidden_deleted_and_private_content_is_not_searchable(member, lead):
    path = LearningPath.objects.get(slug="forma-revit")
    visible = notes.create_note(member, path, "Truco zorrillo para vistas", "tip")
    hidden = notes.create_note(member, path, "Truco zorrillo oculto", "tip")
    gone = notes.create_note(member, path, "Truco zorrillo borrado", "tip")
    search.reindex()
    moderation.set_hidden(hidden, lead, True, "no va")
    notes.delete_note(gone, member)  # el índice aún los tiene: se revalidan al consultar
    titles = [h["body"] for h in search.search("zorrillo")]
    assert titles == ["Truco zorrillo para vistas"] and visible
    search.reindex()
    assert [h["body"] for h in search.search("zorrillo")] == ["Truco zorrillo para vistas"]


def test_hidden_threads_and_posts_are_not_indexed(member, lead):
    t = forum.create_thread(
        member, Category.objects.get(slug="general"), "question", "Hilo quimera", "cuerpo"
    )
    p = forum.reply(t, lead, "respuesta quimera")
    search.reindex()
    assert len(search.search("quimera")) == 2
    moderation.set_hidden(p, lead, True, "x")
    assert len(search.search("quimera")) == 1
    moderation.set_hidden(t, lead, True, "x")
    assert search.search("quimera") == []


def test_unpublished_paths_are_not_searchable(member):
    LearningPath.objects.filter(slug="bentley-learn").update(is_published=False)
    search.reindex()
    assert not [h for h in search.search("Bentley") if h["kind"] == "path"]


def test_the_index_has_no_credential_or_person_data(member, lead):
    creds.create_credential(
        member,
        {
            "title": "TituloUnicoCredencial",
            "credential_id": "IDUNICO123",
            "kind": "completion",
            "visibility": "team",
        },
        SimpleUploadedFile("c.pdf", PDF),
    )
    search.reindex()
    from django.db import connection

    with connection.cursor() as cur:
        cur.execute(
            "SELECT group_concat(title || ' ' || body || ' ' || url, ' ') FROM assistant_fts"
        )
        blob = cur.fetchone()[0]
    for forbidden in ("TituloUnicoCredencial", "IDUNICO123", member.login, lead.login):
        assert forbidden not in blob


# --- búsqueda ----------------------------------------------------------------------------------------------------------


def test_search_finds_glossary_help_and_resources(member):
    assert any(h["kind"] == "glossary" for h in search.search("Forma Home"))
    assert any(
        h["kind"] == "help" and "certificado" in h["title"].lower()
        for h in search.search("subir certificado")
    )
    assert search.search("") == [] and search.search("!!") == []


def test_search_is_accent_insensitive_and_safe_against_fts_syntax(member):
    assert search.search("certificacion")  # sin tilde
    assert search.search('" OR * NEAR( AND') == [] or isinstance(
        search.search('" OR * NEAR('), list
    )


def test_reindex_command_and_freshness(member):
    call_command("reindex_assistant", verbosity=0)
    from apps.assistant.models import IndexState

    first = IndexState.objects.get().built_at
    search.ensure_fresh()
    assert IndexState.objects.get().built_at == first  # reciente: no se reconstruye


# --- vistas ------------------------------------------------------------------------------------------------------------


def test_page_works_without_js_and_offers_a_forum_question(client_for, member):
    Recorder().install()
    response = client_for(member.login).post("/teo/", {"question": "¿Cómo subo un certificado?"})
    html = response.content.decode()
    assert response.status_code == 200 and "Hola, soy Teo" in html
    assert "/foro/nuevo/?titulo=" in html and "Abrir una consulta" in html


def test_ask_returns_a_fragment_and_escapes_the_model_output(client_for, member):
    Recorder(content="<script>alert(1)</script> hola").install()
    html = client_for(member.login).post("/teo/ask/", {"question": "hola teo"}).content.decode()
    assert (
        "<html" not in html and "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html
    )


def test_model_cannot_inject_links(client_for, member):
    Recorder(content="Mira [aquí](https://evil.com) o https://evil.com").install()
    html = client_for(member.login).post("/teo/ask/", {"question": "hola teo"}).content.decode()
    assert 'href="https://evil.com' not in html


def test_only_internal_sources_are_linked(client_for, member):
    Recorder().install()
    html = client_for(member.login).post("/teo/ask/", {"question": "Forma Home"}).content.decode()
    for href in __import__("re").findall(r'href="([^"]+)"', html):
        assert href.startswith("/")


def test_forum_prefill_uses_only_what_the_person_typed(client_for, member):
    html = (
        client_for(member.login)
        .get("/foro/nuevo/?titulo=Mi duda&detalle=Detalle largo")
        .content.decode()
    )
    assert 'value="Mi duda"' in html and "Detalle largo" in html


def test_summarize_a_thread(client_for, member, lead):
    t = forum.create_thread(
        member, Category.objects.get(slug="general"), "discussion", "Charla larga", "Arranque"
    )
    for i in range(6):
        forum.reply(t, lead, f"mensaje número {i}")
    hidden = forum.reply(t, lead, "texto oculto xyz")
    moderation.set_hidden(hidden, lead, True, "no")
    rec = Recorder().install()
    page = client_for(member.login).get(f"/foro/{t.pk}/").content.decode()
    assert "Resumir con Nala" in page
    response = client_for(member.login).post(f"/teo/resumir/{t.pk}/")
    assert response.status_code == 200 and "Hola, soy Teo" in response.content.decode()
    assert "mensaje número 3" in rec.sent and "texto oculto xyz" not in rec.sent
    assert BotLog.objects.get().kind == "summary"


def test_summarizing_a_hidden_thread_is_404_for_members(client_for, member, lead):
    t = forum.create_thread(
        member, Category.objects.get(slug="general"), "discussion", "Oculto", "x"
    )
    moderation.set_hidden(t, lead, True, "x")
    Recorder().install()
    assert client_for(member.login).post(f"/teo/resumir/{t.pk}/").status_code == 404


def test_pending_people_cannot_ask(client_for, make_person):
    rec = Recorder().install()
    pending = make_person("nuevo@lev.cl", status="pending")
    assert client_for(pending.login).post("/teo/ask/", {"question": "hola"}).status_code != 200
    assert not rec.requests


def test_help_pages(client_for, member):
    c = client_for(member.login)
    assert "Cómo subo un certificado" in c.get("/ayuda/").content.decode()
    assert c.get("/ayuda/subir-certificado/").status_code == 200
    assert c.get("/ayuda/no-existe/").status_code == 404
    assert c.get("/ayuda/..%2f..%2fsettings/").status_code == 404


def test_widget_is_in_the_page_and_awake(client_for, member):
    Recorder().install()
    html = client_for(member.login).get("/").content.decode()
    assert "teo-widget" in html and "teo-idle.svg" in html and "teo.js" in html


def test_pending_titles_are_titles_only(member):
    titles = context.pending_titles(member)
    assert (
        titles and all(isinstance(t, str) for t in titles) and len(titles) <= context.PENDING_LIMIT
    )
