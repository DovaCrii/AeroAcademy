from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.utils import timezone

from apps.accounts import services as accounts
from apps.accounts.models import Person, PersonStatus
from apps.community import forum, moderation
from apps.community import services as notes
from apps.community.models import Category, ModerationLog, Post, Report, Thread
from apps.credentials import services as creds
from apps.notifications import services as notifications
from apps.notifications.models import Announcement, Notification
from apps.paths.models import LearningPath
from tests.conftest import tailscale_client

pytestmark = pytest.mark.django_db
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF\n" + b"x" * 200


@pytest.fixture(autouse=True)
def seeded(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    call_command("seed_catalog", verbosity=0)


def thread(author, title="Duda", kind="question"):
    return forum.create_thread(author, Category.objects.get(slug="general"), kind, title, "Detalle")


def inbox(person, kind=None):
    qs = Notification.objects.filter(recipient=person)
    return qs.filter(kind=kind) if kind else qs


# --- notificaciones --------------------------------------------------------------------------------------------------


def test_notify_is_idempotent_by_key(member):
    assert notifications.notify(member, "x", "Hola", key="k1")
    assert notifications.notify(member, "x", "Hola", key="k1") is None
    assert inbox(member).count() == 1
    notifications.notify(member, "x", "Sin clave")
    notifications.notify(member, "x", "Sin clave")
    assert inbox(member).count() == 3


def test_inactive_people_get_nothing(member):
    member.is_active = False
    member.save()
    assert notifications.notify(member, "x", "Hola") is None


def test_mark_read_only_touches_own(member, lead):
    mine = notifications.notify(member, "x", "mío")
    theirs = notifications.notify(lead, "x", "suyo")
    assert notifications.mark_read(member, theirs.pk) == 0
    assert notifications.mark_read(member, mine.pk) == 1
    assert notifications.unread_count(member) == 0 and notifications.unread_count(lead) == 1


def test_read_endpoint_follows_local_links_only(client_for, member):
    local = notifications.notify(member, "x", "a", url="/foro/")
    away = notifications.notify(member, "x", "b", url="https://evil.com")
    protocol = notifications.notify(member, "x", "c", url="//evil.com")
    client = client_for(member.login)
    assert client.post(f"/avisos/{local.pk}/leer/")["Location"] == "/foro/"
    assert client.post(f"/avisos/{away.pk}/leer/")["Location"] == "/avisos/"
    assert client.post(f"/avisos/{protocol.pk}/leer/")["Location"] == "/avisos/"


def test_cannot_read_someone_elses_notice(client_for, member, lead):
    n = notifications.notify(lead, "x", "suyo")
    assert client_for(member.login).post(f"/avisos/{n.pk}/leer/").status_code == 404
    n.refresh_from_db()
    assert not n.is_read


def test_inbox_and_bell(client_for, member):
    notifications.notify(member, "x", "Aviso importante", "con detalle")
    client = client_for(member.login)
    home = client.get("/").content.decode()
    assert "Aviso importante" in home and "1 sin leer" in home
    page = client.get("/avisos/").content.decode()
    assert "Aviso importante" in page
    client.post("/avisos/leer/")
    assert "sin leer" not in client.get("/").content.decode()


# --- ganchos --------------------------------------------------------------------------------------------------------


def test_new_pending_person_notifies_leads(lead):
    client = tailscale_client("nueva@lev.cl", name="Nueva")
    assert client.get("/").status_code in (200, 302)
    person = Person.objects.get(login="nueva@lev.cl")
    assert person.status == PersonStatus.PENDING
    assert inbox(lead, "person_pending").filter(title__contains="Nueva").exists()


def test_approving_welcomes_the_person(make_person, lead):
    person = make_person("nuevo@lev.cl", status="pending")
    accounts.approve(person, lead)
    accounts.approve(person, lead)
    assert inbox(person, "welcome").count() == 1


def test_credential_flow_notifications(member, lead):
    cred = creds.create_credential(
        member,
        {"title": "Curso", "kind": "completion", "visibility": "team"},
        SimpleUploadedFile("c.pdf", PDF),
    )
    assert inbox(lead, "credential_submitted").count() == 1
    assert not inbox(member, "credential_submitted").exists()
    creds.verify(cred, lead)
    assert inbox(member, "credential_verified").count() == 1
    creds.reject(cred, lead, "Borroso")
    rejected = inbox(member, "credential_rejected").get()
    assert rejected.body == "Borroso"
    creds.update_credential(cred, {"issuer": "Otro"})
    assert inbox(lead, "credential_submitted").count() == 2


def test_badge_and_level_notifications(member, lead):
    cred = creds.create_credential(
        member,
        {"title": "Curso", "kind": "certification", "visibility": "team"},
        SimpleUploadedFile("c.pdf", PDF),
    )
    creds.verify(cred, lead)
    assert inbox(member, "badge").filter(title__contains="Primer Trofeo").exists()
    assert inbox(member, "level_up").filter(title__contains="nivel 3").exists()  # 500 XP


def test_forum_notifications(member, lead):
    t = thread(member)
    post = forum.reply(t, lead, "Mira")
    assert inbox(member, "thread_reply").count() == 1
    forum.reply(t, member, "gracias")
    assert inbox(member, "thread_reply").count() == 1  # no se avisa a sí mismo
    forum.accept(t, post, member)
    assert inbox(lead, "answer_accepted").count() == 1


def test_note_reply_notifies_author(member, lead):
    path = LearningPath.objects.get(slug="forma-revit")
    n = notes.create_note(member, path, "Funciona", "works")
    notes.create_note(lead, path, "Qué bien", "reply", parent=n)
    assert inbox(member, "note_reply").count() == 1


# --- anuncios -------------------------------------------------------------------------------------------------------


def test_announcement_reaches_everyone_and_shows_on_home(client_for, member, lead, make_person):
    pending = make_person("nuevo@lev.cl", status="pending")
    ann = notifications.publish_announcement(
        lead, "Expedición", "Seis trofeos", timezone.localdate() + timedelta(days=5)
    )
    assert inbox(member, "announcement").count() == 1 and inbox(lead, "announcement").count() == 1
    assert not inbox(pending, "announcement").exists()
    assert "Seis trofeos" in client_for(member.login).get("/").content.decode()
    ann.expires_on = timezone.localdate() - timedelta(days=1)
    ann.save()
    assert 'class="announce"' not in client_for(member.login).get("/").content.decode()
    assert not notifications.active_announcements().filter(pk=ann.pk).exists()


@pytest.mark.parametrize(
    ("title", "body", "delta"),
    [("", "x", 1), ("t", "", 1), ("t" * 121, "x", 1), ("t", "x" * 501, 1), ("t", "x", -1)],
)
def test_announcement_validation(lead, title, body, delta):
    with pytest.raises(ValueError):
        notifications.publish_announcement(
            lead, title, body, timezone.localdate() + timedelta(days=delta)
        )
    assert not Announcement.objects.exists()


def test_members_cannot_publish_announcements(member):
    with pytest.raises(PermissionError):
        notifications.publish_announcement(member, "t", "b", timezone.localdate())


# --- moderación: acciones --------------------------------------------------------------------------------------------


def test_pinned_threads_come_first_and_are_logged(member, lead):
    old, new = thread(member, "Vieja"), thread(member, "Nueva")
    moderation.pin(old, lead)
    assert [t.title for t in forum.listing()][:2] == ["Vieja", "Nueva"]
    moderation.pin(old, lead, False)
    assert [t.title for t in forum.listing()][0] == "Nueva" and new
    assert ModerationLog.objects.filter(action__in=["pin", "unpin"]).count() == 2


def test_only_leads_moderate(member):
    t = thread(member)
    with pytest.raises(PermissionError):
        moderation.pin(t, member)
    with pytest.raises(PermissionError):
        moderation.set_hidden(t, member, True, "x")


def test_hiding_needs_a_reason_hides_it_from_members_and_tells_the_author(client_for, member, lead):
    t = thread(member)
    with pytest.raises(ValueError, match="motivo"):
        moderation.set_hidden(t, lead, True, " ")
    moderation.set_hidden(t, lead, True, "Datos de un cliente")
    assert client_for(member.login).get(f"/foro/{t.pk}/").status_code == 404
    assert "Duda" not in client_for(member.login).get("/foro/").content.decode().split("<main")[1]
    assert client_for(lead.login).get(f"/foro/{t.pk}/").status_code == 200
    assert inbox(member, "content_hidden").get().body == "Datos de un cliente"
    assert forum.open_questions_count() == 0
    moderation.set_hidden(t, lead, False)
    assert client_for(member.login).get(f"/foro/{t.pk}/").status_code == 200


def test_hidden_posts_and_notes_only_show_to_leads(client_for, member, lead):
    t = thread(member)
    post = forum.reply(t, lead, "Texto problemático")
    moderation.set_hidden(post, lead, True, "No va")
    assert (
        "Texto problemático" not in client_for(member.login).get(f"/foro/{t.pk}/").content.decode()
    )
    assert "Texto problemático" in client_for(lead.login).get(f"/foro/{t.pk}/").content.decode()
    path = LearningPath.objects.get(slug="forma-revit")
    n = notes.create_note(member, path, "Nota fea", "tip")
    moderation.set_hidden(n, lead, True, "No va")
    assert (
        "Nota fea" not in client_for(member.login).get("/rutas/forma-revit/notas/").content.decode()
    )
    assert "Nota fea" in client_for(lead.login).get("/rutas/forma-revit/notas/").content.decode()


def test_move_and_rename(member, lead):
    t = thread(member)
    moderation.move_thread(t, lead, Category.objects.get(slug="bentley"))
    moderation.rename_thread(t, lead, "Título nuevo")
    t.refresh_from_db()
    assert t.category.slug == "bentley" and t.title == "Título nuevo"
    with pytest.raises(ValueError):
        moderation.rename_thread(t, lead, " ")
    retired = Category.objects.get(slug="general")
    retired.retired = True
    with pytest.raises(ValueError):
        moderation.move_thread(t, lead, retired)
    assert ModerationLog.objects.filter(action__in=["move", "rename"]).count() == 2


def test_lead_closing_or_accepting_for_someone_else_is_logged(member, lead):
    t = thread(member)
    forum.set_closed(t, lead, True)
    forum.set_closed(t, member, False)  # el autor no deja registro
    post = forum.reply(t, member, "r")
    forum.accept(t, post, lead)
    assert list(ModerationLog.objects.order_by("id").values_list("action", flat=True)) == [
        "close",
        "accept",
    ]


# --- reportes ------------------------------------------------------------------------------------------------------------


def test_report_flow(member, lead, make_person):
    other = make_person("otra@lev.cl")
    t = thread(member)
    post = forum.reply(t, other, "Mal comentario")
    rep = moderation.report_content(member, "post", post.pk, "Es ofensivo")
    assert inbox(lead, "report").count() == 1
    with pytest.raises(ValueError, match="Ya reportaste"):
        moderation.report_content(member, "post", post.pk, "otra vez")
    moderation.resolve_report(rep, lead, hide=True)
    post.refresh_from_db()
    rep.refresh_from_db()
    assert post.is_hidden and rep.status == "hidden" and rep.resolved_by == lead
    with pytest.raises(ValueError, match="ya estaba resuelto"):
        moderation.resolve_report(rep, lead, hide=False)


def test_report_validation(member, make_person):
    mine = forum.reply(thread(member), member, "mío")
    with pytest.raises(ValueError, match="propio"):
        moderation.report_content(member, "post", mine.pk, "x")
    with pytest.raises(ValueError):
        moderation.report_content(member, "post", mine.pk + 99, "x")
    with pytest.raises(ValueError):
        moderation.report_content(member, "thread", 1, "x")
    other = make_person("otra@lev.cl")
    theirs = forum.reply(thread(other, "otro"), other, "suyo")
    with pytest.raises(ValueError, match="motivo"):
        moderation.report_content(member, "post", theirs.pk, "  ")
    with pytest.raises(ValueError):
        moderation.report_content(member, "post", theirs.pk, "x" * 301)


def test_dismissing_a_report_logs_it(member, lead, make_person):
    other = make_person("otra@lev.cl")
    post = forum.reply(thread(other), other, "ok")
    rep = moderation.report_content(member, "post", post.pk, "no me gusta")
    moderation.resolve_report(rep, lead, hide=False, reason="Todo bien")
    post.refresh_from_db()
    assert not post.is_hidden and Report.objects.get().status == "dismissed"
    assert ModerationLog.objects.filter(action="dismiss_report", reason="Todo bien").exists()


# --- pantalla de moderación --------------------------------------------------------------------------------------------


def test_moderation_pages_are_for_leads(client_for, member):
    client = client_for(member.login)
    assert client.get("/moderacion/").status_code == 403
    for url in (
        "/moderacion/anuncios/nuevo/",
        "/moderacion/personas/1/aprobar/",
        "/moderacion/reportes/1/resolver/",
    ):
        assert client.post(url, {}).status_code == 403
    t = thread(member)
    assert client.post(f"/foro/{t.pk}/moderar/", {"action": "pin"}).status_code == 403
    t.refresh_from_db()
    assert not t.is_pinned


def test_dashboard_lists_everything(client_for, lead, member, make_person):
    pending = make_person("nuevo@lev.cl", status="pending")
    other = make_person("otra@lev.cl")
    post = forum.reply(thread(other), other, "contenido reportado")
    moderation.report_content(member, "post", post.pk, "Motivo del reporte")
    moderation.pin(thread(member, "Fijar"), lead)
    html = client_for(lead.login).get("/moderacion/").content.decode()
    assert pending.name in html and "contenido reportado" in html and "Motivo del reporte" in html
    assert "Bitácora" in html and "pin" in html


def test_approve_person_assigns_role_discipline_and_class(client_for, admin_person, make_person):
    pending = make_person("nuevo@lev.cl", status="pending")
    response = client_for(admin_person.login).post(
        f"/moderacion/personas/{pending.pk}/aprobar/",
        {"role": "lead", "character_class": "pilot", "disciplines": ["arquitectura"]},
    )
    pending.refresh_from_db()
    assert response.status_code == 302
    assert (
        pending.status == "approved"
        and pending.role == "lead"
        and pending.character_class == "pilot"
    )
    assert [d.slug for d in pending.disciplines.all()] == ["arquitectura"]
    assert pending.approved_by == admin_person
    assert ModerationLog.objects.filter(action="approve_person").exists()


def test_a_plain_lead_cannot_name_leads(client_for, lead, make_person):
    pending = make_person("nuevo@lev.cl", status="pending")
    client_for(lead.login).post(f"/moderacion/personas/{pending.pk}/aprobar/", {"role": "lead"})
    pending.refresh_from_db()
    assert pending.status == "approved" and pending.role == "member"


def test_reject_person_suspends(client_for, lead, make_person):
    pending = make_person("nuevo@lev.cl", status="pending")
    client_for(lead.login).post(f"/moderacion/personas/{pending.pk}/rechazar/")
    pending.refresh_from_db()
    assert pending.status == "suspended"
    assert client_for(pending.login).get("/").status_code == 403


def test_only_pending_people_can_be_approved_this_way(client_for, lead, member):
    assert (
        client_for(lead.login).post(f"/moderacion/personas/{member.pk}/rechazar/").status_code
        == 404
    )


def test_http_report_and_resolution(client_for, member, lead, make_person):
    other = make_person("otra@lev.cl")
    t = thread(other)
    post = forum.reply(t, other, "algo")
    client_for(member.login).post(
        f"/reportar/post/{post.pk}/", {"reason": "Spam", "next": f"/foro/{t.pk}/"}
    )
    rep = Report.objects.get()
    client_for(lead.login).post(
        f"/moderacion/reportes/{rep.pk}/resolver/", {"action": "hide", "reason": "Spam"}
    )
    assert Post.objects.get(pk=post.pk).is_hidden


@pytest.mark.parametrize("target", ["//evil.com", "https://evil.com", "/\\evil.com"])
def test_report_redirect_is_safe(client_for, member, make_person, target):
    other = make_person("otra@lev.cl")
    post = forum.reply(thread(other), other, "algo")
    response = client_for(member.login).post(
        f"/reportar/post/{post.pk}/", {"reason": "x", "next": target}
    )
    assert response["Location"] == "/foro/"


def test_http_thread_moderation(client_for, member, lead):
    t = thread(member)
    client = client_for(lead.login)
    client.post(f"/foro/{t.pk}/moderar/", {"action": "pin"})
    client.post(f"/foro/{t.pk}/moderar/", {"action": "rename", "title": "Nuevo título"})
    client.post(f"/foro/{t.pk}/moderar/", {"action": "move", "category": "mecanica"})
    client.post(f"/foro/{t.pk}/moderar/", {"action": "hide", "reason": "Fuera de lugar"})
    t.refresh_from_db()
    assert (
        t.is_pinned and t.title == "Nuevo título" and t.category.slug == "mecanica" and t.is_hidden
    )
    assert Thread.objects.get().hidden_reason == "Fuera de lugar"


def test_home_announcement_and_lead_counters(client_for, lead, member, make_person):
    make_person("nuevo@lev.cl", status="pending")
    notifications.publish_announcement(
        lead, "Ruta nueva", "Se abrió una campaña", timezone.localdate()
    )
    html = client_for(lead.login).get("/").content.decode()
    assert "Se abrió una campaña" in html and "personas por aprobar" in html
    assert "personas por aprobar" not in client_for(member.login).get("/").content.decode()


def test_moderation_link_only_for_leads(client_for, lead, member):
    assert 'href="/moderacion/"' in client_for(lead.login).get("/").content.decode()
    assert 'href="/moderacion/"' not in client_for(member.login).get("/").content.decode()


def test_bell_query_count_does_not_grow_with_notices(client_for, member):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    client = client_for(member.login)

    def count():
        with CaptureQueriesContext(connection) as ctx:
            assert client.get("/").status_code == 200
        return len(ctx)

    notifications.notify(member, "x", "uno")
    few = count()
    for i in range(30):
        notifications.notify(member, "x", f"Aviso {i}")
    assert count() <= few
