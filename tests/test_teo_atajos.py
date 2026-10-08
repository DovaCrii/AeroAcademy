from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.utils import timezone

from apps.assistant import client, followup, quick, search
from apps.assistant.models import BotLog, BotUsage
from apps.credentials import services as creds
from apps.credentials.models import Credential
from apps.library import services as library
from apps.notifications.models import Notification
from apps.paths.models import LearningPath, Milestone
from apps.progress import services as progress

pytestmark = pytest.mark.django_db
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF\n" + b"x" * 200


@pytest.fixture(autouse=True)
def seeded(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.NIM_API_KEY = ""  # los atajos funcionan con Teo durmiendo
    call_command("seed_catalog", verbosity=0)
    calls = []
    client.TRANSPORT = httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(500))
    yield calls
    client.TRANSPORT = None


def cred(owner, lead, **extra):
    data = {"title": "Curso", "kind": "completion", "visibility": "team", **extra}
    c = creds.create_credential(owner, data, SimpleUploadedFile("c.pdf", PDF))
    creds.verify(c, lead)
    return c


# --- cada atajo -----------------------------------------------------------------------------------------------------


def test_mission_shortcut_gives_the_next_steps(member):
    LearningPath.objects.filter(slug="bentley-learn").update(is_published=False)
    first = Milestone.objects.filter(path__slug="forma-revit", retired=False).first()
    progress.set_milestone(member, first, True)
    out = quick.answer(member, "mision")
    assert out.status == "ok" and "Tu próxima misión" in out.text and "Después vienen" in out.text
    assert out.sources[0]["url"].startswith("/rutas/forma-revit/")


def test_mission_shortcut_when_everything_is_done(member):
    LearningPath.objects.update(is_published=False)
    out = quick.answer(member, "mision")
    assert "Completaste todas las campañas" in out.text


def test_expiring_shortcut_lists_only_my_credentials(member, lead, make_person):
    other = make_person("otra@lev.cl")
    cred(member, lead, title="Mi licencia", expires_on=timezone.localdate() + timedelta(days=10))
    cred(member, lead, title="Mi vencida", expires_on=timezone.localdate() - timedelta(days=3))
    cred(other, lead, title="La de otra", expires_on=timezone.localdate() + timedelta(days=5))
    out = quick.answer(member, "vence")
    assert "Mi licencia" in out.text and "Mi vencida" in out.text and "La de otra" not in out.text


def test_expiring_shortcut_with_nothing_due(member):
    assert "Nada vence" in quick.answer(member, "vence").text


def test_course_shortcut_recommends_catalog_entries(member):
    LearningPath.objects.filter(slug="bentley-learn").update(is_published=False)
    out = quick.answer(member, "curso")
    assert out.sources and all(s["url"].startswith("/catalogo/?q=") for s in out.sources)


def test_upload_shortcut_links_to_the_form_and_the_guide(member):
    urls = [s["url"] for s in quick.answer(member, "subir").sources]
    assert "/certificados/nueva/" in urls and "/ayuda/subir-certificado/" in urls


def test_unknown_shortcut(member):
    assert quick.answer(member, "zzz").status == "empty"


# --- privacidad y límites -------------------------------------------------------------------------------------------


def test_shortcuts_never_call_the_api_nor_spend_the_daily_limit(member, lead, seeded, settings):
    settings.NIM_API_KEY = "nvapi-X"  # aun con Teo despierto
    cred(
        member,
        lead,
        title="Privada",
        visibility="private",
        expires_on=timezone.localdate() + timedelta(days=2),
    )
    for key, _ in quick.SHORTCUTS:
        quick.answer(member, key)
    assert seeded == [] and not BotUsage.objects.exists()
    assert set(BotLog.objects.values_list("kind", flat=True)) == {"quick"}


# --- HTTP -------------------------------------------------------------------------------------------------------------


def test_widget_and_page_offer_the_shortcuts_even_when_teo_sleeps(client_for, member):
    home = client_for(member.login).get("/").content.decode()
    assert 'name="atajo" value="mision"' in home and "teo-sleep.svg" in home
    assert 'name="atajo" value="vence"' in client_for(member.login).get("/teo/").content.decode()


def test_shortcut_over_http_fragment_and_full_page(client_for, member):
    client = client_for(member.login)
    fragment = client.post("/teo/ask/", {"atajo": "subir"}).content.decode()
    assert "<html" not in fragment and "Subir certificado" in fragment
    assert "Abrir una consulta" not in fragment  # un atajo no propone abrir consulta
    page = client.post("/teo/", {"atajo": "vence"}).content.decode()
    assert "Nada vence" in page


def test_shortcut_text_is_escaped(client_for, member, lead):
    cred(
        member,
        lead,
        title="<script>alert(1)</script>",
        expires_on=timezone.localdate() + timedelta(days=3),
    )
    html = client_for(member.login).post("/teo/ask/", {"atajo": "vence"}).content.decode()
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html


# --- documentos en el índice ---------------------------------------------------------------------------------------------


def up():
    return SimpleUploadedFile("m.pdf", PDF)


def test_open_documents_are_searchable_and_restricted_ones_are_not(member, lead):
    library.create_document(member, title="Manual zirconio abierto", doc_type="manual", upload=up())
    secret = library.create_document(
        lead, title="Manual zirconio secreto", doc_type="manual", upload=up(), restricted=True
    )
    search.reindex()
    titles = [h["title"] for h in search.search("zirconio")]
    assert titles == ["Manual zirconio abierto"] and secret


def test_a_document_restricted_after_indexing_is_not_served(member):
    doc = library.create_document(
        member,
        title="Plantilla kriptón",
        doc_type="template_rte",
        upload=SimpleUploadedFile("p.rte", b"\xd0\xcf\x11\xe0" + b"0" * 40),
    )
    search.reindex()
    assert search.search("kriptón")
    doc.is_restricted = True
    doc.save()
    assert search.search("kriptón") == []


def test_document_files_never_reach_the_index(member):
    doc = library.create_document(member, title="Con archivo", doc_type="manual", upload=up())
    search.reindex()
    from django.db import connection

    with connection.cursor() as cur:
        cur.execute("SELECT group_concat(body, ' ') FROM assistant_fts WHERE kind = 'document'")
        blob = cur.fetchone()[0] or ""
    assert doc.current.file.name not in blob and doc.current.file_sha256 not in blob


# --- seguimiento -----------------------------------------------------------------------------------------------------------


def test_digest_mentions_certificates_waiting_more_than_a_week(member, lead):
    c = creds.create_credential(
        member,
        {"title": "Pendiente", "kind": "completion", "visibility": "team"},
        SimpleUploadedFile("c.pdf", PDF),
    )
    Credential.objects.filter(pk=c.pk).update(created_at=timezone.now() - timedelta(days=10))
    followup.run()
    digest = Notification.objects.get(recipient=lead, kind="teo_digest")
    assert "1 esperan hace más de 7 días" in digest.body


def test_the_widget_answers_inline_even_when_teo_sleeps(client_for, member):
    """Revisado en el navegador: con Teo dormido el atajo recargaba la página porque faltaba el recuadro de respuesta."""
    home = client_for(member.login).get("/").content.decode()
    widget = home.split('class="teo-widget"')[1]
    assert (
        'class="teo-shortcuts"' in widget
        and "data-teo-answer" in widget
        and "teo-sleep.svg" in home
    )


def test_mobile_header_puts_the_navigation_on_its_own_row():
    """Revisado a 375 px: con 10 secciones la cabecera desbordaba 24 px."""
    from django.conf import settings

    css = (Path(settings.BASE_DIR) / "apps/core/static/core/base.css").read_text(encoding="utf-8")
    mobile = css.split("@media (max-width:640px){", 1)[1]
    assert ".top .nav{grid-column:1/-1;grid-row:2" in mobile
