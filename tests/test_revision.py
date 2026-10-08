"""Regresiones de la revisión independiente de los bloques 13 a 8: cada prueba reproduce un hallazgo."""

import json
from pathlib import Path

import httpx
import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command

from apps.assistant import client, context, search
from apps.assistant import services as bot
from apps.community import forum, moderation
from apps.community import services as notes
from apps.community.models import Category, Note
from apps.core import dashboard
from apps.core.markdown import render
from apps.credentials import export
from apps.credentials import services as creds
from apps.gamification import game
from apps.gamification.models import XPEvent
from apps.knowledge import services as knowledge
from apps.paths.models import ExternalCourse, LearningPath
from apps.team import services as team

pytestmark = pytest.mark.django_db
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF\n" + b"x" * 200
FORMA, BENTLEY = "forma-revit", "bentley-learn"


@pytest.fixture(autouse=True)
def seeded(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.NIM_API_KEY = "nvapi-TEST"
    call_command("seed_catalog", verbosity=0)
    yield
    client.TRANSPORT = None


def cred(owner, lead=None, *, verify=True, **extra):
    data = {"title": "Curso", "kind": "completion", "visibility": "team", **extra}
    c = creds.create_credential(owner, data, SimpleUploadedFile("c.pdf", PDF))
    if verify:
        creds.verify(c, lead)
    return c


def thread(author, title="Duda"):
    return forum.create_thread(
        author, Category.objects.get(slug="general"), "question", title, "Detalle"
    )


def draft_path():
    LearningPath.objects.filter(slug=FORMA).update(is_published=False)
    return LearningPath.objects.get(slug=FORMA)


class Rec:
    def __init__(self):
        self.requests = []

    def install(self):
        def handler(request):
            self.requests.append(request)
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

        client.TRANSPORT = httpx.MockTransport(handler)
        return self

    @property
    def sent(self):
        return "\n".join(r.content.decode() for r in self.requests)


# 1 · una credencial verificada no cambia sin nueva revisión -----------------------------------------------------------


def test_finding1_xp_follows_the_current_value_of_a_verified_credential(member, lead):
    c = cred(member, lead, kind="other")
    assert not member.xp_events.filter(kind="credential").exists()
    creds.update_credential(c, {"kind": "certification"})  # ya no cuela: vuelve a revisión
    c.refresh_from_db()
    assert c.status == "pending" and not member.xp_events.filter(kind="credential").exists()


# 3 · el índice de Teo ----------------------------------------------------------------------------------------------------


def test_finding3_notes_of_unpublished_paths_never_reach_the_index_or_the_payload(member, lead):
    n = notes.create_note(
        lead, LearningPath.objects.get(slug=FORMA), "SECRETO-DEL-BORRADOR kappa", "tip"
    )
    search.reindex()
    assert search.search("kappa")
    draft_path()
    assert search.search("kappa") == []  # el índice viejo se revalida
    rec = Rec().install()
    bot.answer(member, "kappa")
    assert "SECRETO-DEL-BORRADOR" not in rec.sent and n


def test_finding3_replies_of_hidden_or_deleted_parents_are_not_indexed(member, lead, make_person):
    path = LearningPath.objects.get(slug=FORMA)
    parent = notes.create_note(member, path, "Nota madre", "tip")
    notes.create_note(lead, path, "Respuesta lambda", "reply", parent=parent)
    search.reindex()
    assert search.search("lambda")
    moderation.set_hidden(parent, lead, True, "no")
    assert search.search("lambda") == []
    search.reindex()
    assert search.search("lambda") == []


def test_finding3_nobody_replies_to_a_hidden_note(member, lead):
    path = LearningPath.objects.get(slug=FORMA)
    parent = notes.create_note(member, path, "Nota madre", "tip")
    moderation.set_hidden(parent, lead, True, "no")
    with pytest.raises(ValueError):
        notes.create_note(lead, path, "x", "reply", parent=parent)


def test_finding3_glossary_of_an_unpublished_path_is_not_served(member):
    search.reindex()
    assert any(h["kind"] == "glossary" for h in search.search("Forma Home"))
    draft_path()
    assert not any(h["kind"] == "glossary" for h in search.search("Forma Home"))


# 4 y 5 · tablero --------------------------------------------------------------------------------------------------------


def test_finding4_the_board_hides_notes_of_draft_paths(client_for, member, lead):
    notes.create_note(lead, LearningPath.objects.get(slug=FORMA), "SECRETO-BORRADOR", "tip")
    draft_path()
    assert "SECRETO-BORRADOR" not in client_for(member.login).get("/equipo/").content.decode()
    assert "SECRETO-BORRADOR" in client_for(lead.login).get("/equipo/").content.decode()


def test_finding5_private_credentials_do_not_show_up_in_the_progress_percentage(
    member, lead, make_person
):
    other = make_person("otra@lev.cl")
    bentley = LearningPath.objects.get(slug=BENTLEY)
    for course in ExternalCourse.objects.filter(path=bentley, is_required=True):
        cred(
            other,
            lead,
            resource=course.resource,
            path=bentley,
            title=course.key,
            visibility="private",
        )
    seen_by_member = team.path_percentages([other], [bentley], member)[(other.pk, bentley.pk)]
    seen_by_owner = team.path_percentages([other], [bentley], other)[(other.pk, bentley.pk)]
    seen_by_lead = team.path_percentages([other], [bentley], lead)[(other.pk, bentley.pk)]
    assert seen_by_member == 0 and seen_by_owner > 0 and seen_by_lead == seen_by_owner


# 6 · lo que viaja a NVIDIA -----------------------------------------------------------------------------------------------------


def test_finding6_the_login_never_travels_when_there_is_no_display_name(make_person):
    person = make_person("juan.perez@gmail.com")
    person.display_name = ""
    person.save()
    rec = Rec().install()
    bot.answer(person, "¿qué sigue?")
    assert "juan.perez" not in rec.sent and "la persona" in rec.sent


def test_finding6_which_courses_are_missing_is_not_sent(member, lead):
    bentley = LearningPath.objects.get(slug=BENTLEY)
    LearningPath.objects.exclude(pk=bentley.pk).update(is_published=False)
    first = ExternalCourse.objects.filter(path=bentley, is_required=True).first()
    cred(member, lead, resource=first.resource, path=bentley)
    rec = Rec().install()
    bot.answer(member, "¿qué sigue?")
    assert "Registra tu certificado" not in rec.sent
    titles = context.pending_titles(member)
    assert titles == [f"{bentley.title}: sigue con los cursos de la ruta"]


def test_finding6_unpublished_paths_do_not_reach_the_provider(lead):
    LearningPath.objects.update(is_published=False)
    assert dashboard.suggested_mission(lead) is not None  # el responsable la ve en la portada
    assert context.pending_titles(lead) == []  # pero no viaja


# 7 · respuesta aceptada y moderación ----------------------------------------------------------------------------------------


def test_finding7_a_hidden_answer_cannot_be_accepted(member, lead, make_person):
    spammer = make_person("spam@lev.cl")
    t = thread(member)
    post = forum.reply(t, spammer, "spam")
    moderation.set_hidden(post, lead, True, "spam")
    with pytest.raises(ValueError):
        forum.accept(t, post, member)
    assert not XPEvent.objects.filter(person=spammer, kind="accepted_answer").exists()


def test_finding7_hiding_the_accepted_answer_takes_back_the_xp(member, lead, make_person):
    other = make_person("otra@lev.cl")
    t = thread(member)
    post = forum.reply(t, other, "buena")
    forum.accept(t, post, member)
    assert XPEvent.objects.get(person=other, kind="accepted_answer").points == 50
    moderation.set_hidden(post, lead, True, "no")
    t.refresh_from_db()
    assert (
        t.accepted_post is None
        and not XPEvent.objects.filter(person=other, kind="accepted_answer").exists()
    )


def test_finding7_hiding_a_note_takes_back_its_xp(member, lead):
    n = notes.create_note(member, LearningPath.objects.get(slug=FORMA), "spam", "tip")
    assert game.total_xp(member) >= 5
    moderation.set_hidden(n, lead, True, "spam")
    assert not member.xp_events.filter(source=f"note:{n.pk}").exists()


def test_finding7_two_accepts_with_stale_objects_pay_only_the_last(member, lead, make_person):
    a, b = make_person("a@lev.cl"), make_person("b@lev.cl")
    t = thread(member)
    pa, pb = forum.reply(t, a, "A"), forum.reply(t, b, "B")
    stale_for_lead, stale_for_author = Thread_get(t), Thread_get(t)
    forum.accept(stale_for_lead, pa, lead)
    forum.accept(stale_for_author, pb, member)  # su copia ya estaba vieja
    total = XPEvent.objects.filter(kind="accepted_answer", points__gt=0).count()
    assert total == 1 and XPEvent.objects.get(kind="accepted_answer").person == b


def Thread_get(t):
    from apps.community.models import Thread

    return Thread.objects.get(pk=t.pk)


def test_finding7_accepted_answer_xp_has_a_daily_cap(member, make_person):
    expert = make_person("experta@lev.cl")
    for i in range(forum.DAILY_ACCEPTED_XP + 2):
        t = thread(member, f"q{i}")
        forum.accept(t, forum.reply(t, expert, "r"), member)
    paid = XPEvent.objects.filter(person=expert, kind="accepted_answer", points__gt=0).count()
    assert paid == forum.DAILY_ACCEPTED_XP


# 8 · enlaces del perfil -------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example\\@linkedin.com/in/x",
        "https://linkedin.com@evil.example/in/x",
        "https://www.linkedin.com:444/in/x",
        "https://www.linkedin.com/in/x y",
        "https://evil.example\\.linkedin.com/",
    ],
)
def test_finding8_profile_links_cannot_hide_another_site(client_for, member, url):
    client_for(member.login).post("/perfil/editar/", {"linkedin": url, "show_game_view": "on"})
    member.refresh_from_db()
    assert "linkedin" not in member.links


def test_finding8_a_real_linkedin_link_still_works(client_for, member):
    client_for(member.login).post(
        "/perfil/editar/", {"linkedin": "https://www.linkedin.com/in/ana", "show_game_view": "on"}
    )
    member.refresh_from_db()
    assert member.links["linkedin"] == "https://www.linkedin.com/in/ana"


# 9 · Markdown -------------------------------------------------------------------------------------------------------------------


def test_finding9_backslash_links_are_not_links():
    assert "href=" not in str(render("[a](/\\evil.com)"))
    assert 'href="/foro/"' in str(render("[a](/foro/)"))


def test_finding9_bold_never_enters_an_href():
    html = str(render("[**fuerte**](https://x.y/**b**)"))
    assert 'href="https://x.y/**b**"' in html and "<strong>fuerte</strong>" in html
    assert 'href="https://x.y/<strong>' not in html


# 10 · artículos y moderación ------------------------------------------------------------------------------------------------------


def test_finding10_hiding_a_thread_unpublishes_the_articles_copied_from_it(member, lead):
    t = thread(member)
    post = forum.reply(t, lead, "respuesta")
    forum.accept(t, post, member)
    t.refresh_from_db()
    art = knowledge.create_article(
        member, title="Copia", body="texto", kind="faq", source_thread=t, publish=True
    )
    moderation.set_hidden(t, lead, True, "datos personales")
    art.refresh_from_db()
    assert art.is_published is False
    search.reindex()
    assert search.search("Copia") == []


def test_finding10_a_hidden_thread_is_a_404_when_converting(client_for, member, lead, make_person):
    other = make_person("otra@lev.cl")
    t = thread(member)
    moderation.set_hidden(t, lead, True, "x")
    assert client_for(other.login).get(f"/conocimiento/nuevo/?hilo={t.pk}").status_code == 404


def test_finding10_articles_of_hidden_threads_do_not_show_to_members(member, lead, make_person):
    other = make_person("otra@lev.cl")
    t = thread(member)
    art = knowledge.create_article(
        member, title="Copia", body="texto", kind="faq", source_thread=t, publish=True
    )
    Note.objects.none()
    assert art in knowledge.visible(other)
    t.is_hidden = True
    t.save()
    assert art not in knowledge.visible(other) and art in knowledge.visible(lead)


def test_finding10_hidden_content_cannot_be_reported(member, lead, make_person):
    other = make_person("otra@lev.cl")
    t = thread(member)
    post = forum.reply(t, other, "x")
    moderation.set_hidden(post, lead, True, "x")
    with pytest.raises(ValueError, match="ya no existe"):
        moderation.report_content(member, "post", post.pk, "motivo")


# 11 · exportación -------------------------------------------------------------------------------------------------------------


def test_finding11_the_zip_is_built_in_a_temporary_file_not_in_memory(member, lead):
    cred(member, lead)
    handle, count = export.build_zip_file(lead, export.select())
    with handle:
        assert count == 1 and handle.read(2) == b"PK"
    assert export.MAX_BYTES <= 200 * 1024 * 1024


def test_finding11_the_http_download_streams(client_for, member, lead):
    cred(member, lead)
    response = client_for(lead.login).post("/certificados/exportar/", {"estado": "verified"})
    assert response.streaming and b"".join(response.streaming_content)[:2] == b"PK"


# 13 · defensa en profundidad -------------------------------------------------------------------------------------------------------


def test_finding13_notification_links_use_the_django_check(client_for, member):
    from apps.notifications import services as notifications

    n = notifications.notify(member, "x", "t", url="/\\evil.com")
    assert client_for(member.login).post(f"/avisos/{n.pk}/leer/")["Location"] == "/avisos/"


def test_finding13_editing_the_sheet_does_not_overwrite_the_role(client_for, member, lead):
    from apps.accounts.models import Person

    stale = client_for(member.login)
    Person.objects.filter(pk=member.pk).update(status="suspended")
    stale.post("/perfil/editar/", {"headline": "x", "show_game_view": "on"})
    member.refresh_from_db()
    assert member.status == "suspended"  # el guardado no pisó el estado


# 2 y 12 · despliegue --------------------------------------------------------------------------------------------------------------


def test_finding2_the_health_check_sends_an_allowed_host():
    text = (Path(settings.BASE_DIR) / "deploy" / "install.sh").read_text(encoding="utf-8")
    assert '-H "Host: $HC_HOST"' in text and "ALLOWED_HOSTS=" in text


def test_finding12_deploy_details():
    install = (Path(settings.BASE_DIR) / "deploy" / "install.sh").read_text(encoding="utf-8")
    assert install.index("umask 077") < install.index('cat > "$ENV_FILE"')
    assert "completado con" in install  # el nombre pasado al volver a correr se aplica
    backup = (Path(settings.BASE_DIR) / "deploy" / "backup.sh").read_text(encoding="utf-8")
    assert ".timeout 10000" in backup and "[ $? -eq 1 ]" in backup


def test_json_sanity():
    assert json.loads('{"ok": true}')["ok"]
