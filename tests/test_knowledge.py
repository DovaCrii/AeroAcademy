import re

import pytest
from django.core.management import call_command

from apps.assistant import search
from apps.community import forum
from apps.community import moderation as community_moderation
from apps.community.models import Category
from apps.core.markdown import render
from apps.knowledge import services
from apps.knowledge.models import Article, Improvement
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def seeded():
    call_command("seed_catalog", verbosity=0)


# --- Markdown seguro ---------------------------------------------------------------------------------------------------

XSS = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "[x](javascript:alert(1))",
    "[x](JaVaScRiPt:alert(1))",
    "[x](data:text/html;base64,PHNjcmlwdD4=)",
    "[x](//evil.com)",
    "[x](vbscript:msgbox(1))",
    '[x](https://ok.com" onmouseover="alert(1))',
    "![alt](javascript:alert(1))",
    '<a href="javascript:alert(1)">x</a>',
    "<iframe src=//evil></iframe>",
    "**<b>negrita</b>**",
    "# <script>x</script>",
    "- <svg onload=alert(1)>",
    "> <style>*{}</style>",
    "```\n<script>alert(1)</script>\n```",
    "`<script>alert(1)</script>`",
    "<<script>script>alert(1)<</script>/script>",
]


@pytest.mark.parametrize("payload", XSS)
def test_markdown_never_emits_dangerous_html(payload):
    html = str(render(payload))
    assert (
        "<script" not in html.lower()
        and "<img" not in html.lower()
        and "<iframe" not in html.lower()
    )
    assert "<svg" not in html.lower() and "<style" not in html.lower()
    assert "javascript:" not in " ".join(re.findall(r'href="([^"]*)"', html)).lower()
    assert " onerror=" not in html.lower().replace("&quot;", "") or "&lt;" in html
    for tag in re.findall(r"<(/?\w+)", html):
        assert tag.lower().lstrip("/") in {
            "p",
            "h2",
            "h3",
            "h4",
            "ul",
            "ol",
            "li",
            "blockquote",
            "pre",
            "code",
            "strong",
            "a",
        }
    # los atributos de un enlace son solo href/rel/target
    for attrs in re.findall(r"<a ([^>]*)>", html):
        assert set(re.findall(r"(\w+)=", attrs)) <= {"href", "rel", "target"}


def test_markdown_renders_the_supported_syntax():
    html = str(
        render(
            "# Título\n\nUn **párrafo** con `código` y [enlace](https://ejemplo.cl/a?x=1&y=2).\n\n- uno\n- dos\n\n1. a\n2. b\n\n> cita\n\n```\ncódigo *libre*\n```"
        )
    )
    assert (
        "<h2>Título</h2>" in html
        and "<strong>párrafo</strong>" in html
        and "<code>código</code>" in html
    )
    assert (
        '<a href="https://ejemplo.cl/a?x=1&amp;y=2" rel="noopener noreferrer" target="_blank">enlace</a>'
        in html
    )
    assert "<ul><li>uno</li><li>dos</li></ul>" in html and "<ol><li>a</li><li>b</li></ol>" in html
    assert (
        "<blockquote>cita</blockquote>" in html and "<pre><code>código *libre*</code></pre>" in html
    )


def test_local_links_are_allowed_and_protocol_relative_are_not():
    assert 'href="/foro/"' in str(render("[foro](/foro/)"))
    assert "href=" not in str(render("[x](//evil.com)"))


def test_code_blocks_and_spans_are_not_formatted():
    html = str(render("`**no**` y más\n\n```\n**tampoco**\n```"))
    assert "<strong>" not in html and "<code>**no**</code>" in html


def test_empty_and_unclosed_blocks():
    assert str(render("")) == "" and str(render(None)) == ""
    assert "<pre><code>sin cerrar</code></pre>" in str(render("```\nsin cerrar"))


# --- artículos -----------------------------------------------------------------------------------------------------------


def article(author, title="Cómo cerrar una poligonal", **kw):
    return services.create_article(
        author, title=title, body="Paso **uno**.", kind="procedure", **kw
    )


def test_drafts_are_private_to_author_and_leads(client_for, member, lead, make_person):
    other = make_person("otra@lev.cl")
    a = article(member)
    assert client_for(member.login).get(f"/conocimiento/{a.pk}/").status_code == 200
    assert client_for(lead.login).get(f"/conocimiento/{a.pk}/").status_code == 200
    assert client_for(other.login).get(f"/conocimiento/{a.pk}/").status_code == 404
    assert (
        "poligonal"
        not in client_for(other.login).get("/conocimiento/").content.decode().split("<main")[1]
    )
    services.set_published(a, member, True)
    assert client_for(other.login).get(f"/conocimiento/{a.pk}/").status_code == 200


def test_only_author_or_lead_edit_publish_delete(member, lead, make_person):
    other = make_person("otra@lev.cl")
    a = article(member, publish=True)
    for call in (
        lambda: services.update_article(a, other, title="x", body="y", kind="faq"),
        lambda: services.set_published(a, other, False),
        lambda: services.delete_article(a, other),
    ):
        with pytest.raises(PermissionError):
            call()
    services.update_article(a, lead, title="Editado", body="y", kind="faq")
    a.refresh_from_db()
    assert a.title == "Editado" and a.kind == "faq"


@pytest.mark.parametrize(
    ("title", "body", "kind"),
    [
        ("", "x", "faq"),
        ("t", " ", "faq"),
        ("t" * 151, "x", "faq"),
        ("t", "x" * 20001, "faq"),
        ("t", "x", "otro"),
    ],
)
def test_article_validation(member, title, body, kind):
    with pytest.raises(ValueError):
        services.create_article(member, title=title, body=body, kind=kind)
    assert not Article.objects.exists()


def test_listing_filters(member):
    from apps.catalog.models import Discipline

    arq = Discipline.objects.get(slug="arquitectura")
    a = article(member, "Lección de muros", disciplines=[arq], publish=True)
    b = services.create_article(
        member, title="FAQ de licencias", body="texto", kind="faq", publish=True
    )
    titles = lambda **kw: {x.title for x in services.listing(member, **kw)}  # noqa: E731
    assert titles(kind="faq") == {"FAQ de licencias"} and titles(discipline=arq) == {
        "Lección de muros"
    }
    assert titles(q="licencias") == {"FAQ de licencias"} and titles(q="muros") == {
        "Lección de muros"
    }
    assert a and b


def test_article_page_renders_markdown_safely(client_for, member):
    a = services.create_article(
        member,
        title="<b>Título</b>",
        body="# Hola\n\n<script>alert(1)</script> **fuerte**",
        kind="lesson",
        publish=True,
    )
    html = client_for(member.login).get(f"/conocimiento/{a.pk}/").content.decode()
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html
    assert (
        "<h2>Hola</h2>" in html and "<strong>fuerte</strong>" in html and "&lt;b&gt;Título" in html
    )


def test_article_crud_over_http(client_for, member):
    client = client_for(member.login)
    response = client.post(
        "/conocimiento/nuevo/",
        {
            "title": "Mi lección",
            "body": "Texto",
            "kind": "lesson",
            "disciplines": ["arquitectura"],
            "publish": "on",
        },
    )
    a = Article.objects.get()
    assert (
        response["Location"] == f"/conocimiento/{a.pk}/"
        and a.is_published
        and a.disciplines.count() == 1
    )
    client.post(
        f"/conocimiento/{a.pk}/editar/", {"title": "Cambiada", "body": "Nuevo", "kind": "faq"}
    )
    a.refresh_from_db()
    assert a.title == "Cambiada" and not a.is_published
    client.post(f"/conocimiento/{a.pk}/publicar/", {"published": "1"})
    a.refresh_from_db()
    assert a.is_published
    client.post(f"/conocimiento/{a.pk}/eliminar/")
    assert not Article.objects.exists()


def test_invalid_article_keeps_the_input(client_for, member):
    response = client_for(member.login).post(
        "/conocimiento/nuevo/", {"title": "Sin cuerpo", "body": "", "kind": "lesson"}
    )
    assert (
        response.status_code == 200
        and "Escribe el contenido" in response.content.decode()
        and "Sin cuerpo" in response.content.decode()
    )


# --- consulta resuelta → artículo ----------------------------------------------------------------------------------


def solved(member, lead):
    t = forum.create_thread(
        member,
        Category.objects.get(slug="general"),
        "question",
        "¿Cómo exporto a IFC?",
        "Necesito exportar",
    )
    post = forum.reply(t, lead, "Usa *Export → IFC* con la plantilla del equipo.")
    forum.accept(t, post, member)
    return t


def test_draft_from_a_solved_question(member, lead):
    t = solved(member, lead)
    draft = services.draft_from_thread(t, member)
    assert draft["title"] == "¿Cómo exporto a IFC?" and draft["kind"] == "faq"
    assert (
        "## Pregunta" in draft["body"]
        and "Necesito exportar" in draft["body"]
        and "Export → IFC" in draft["body"]
    )


def test_only_solved_questions_by_the_asker_or_a_lead(member, lead, make_person):
    other = make_person("otra@lev.cl")
    t = solved(member, lead)
    with pytest.raises(PermissionError):
        services.draft_from_thread(t, other)
    services.draft_from_thread(t, lead)
    open_q = forum.create_thread(
        member, Category.objects.get(slug="general"), "question", "Abierta", "x"
    )
    with pytest.raises(ValueError, match="respuesta aceptada"):
        services.draft_from_thread(open_q, member)
    chat = forum.create_thread(
        member, Category.objects.get(slug="general"), "discussion", "Charla", "x"
    )
    with pytest.raises(ValueError):
        services.draft_from_thread(chat, member)


def test_hidden_thread_or_answer_cannot_be_converted(member, lead):
    t = solved(member, lead)
    community_moderation.set_hidden(t.accepted_post, lead, True, "no")
    with pytest.raises(ValueError):
        services.draft_from_thread(t, member)
    community_moderation.set_hidden(t.accepted_post, lead, False)
    community_moderation.set_hidden(t, lead, True, "no")
    with pytest.raises(ValueError):
        services.draft_from_thread(t, member)


def test_convert_flow_over_http_links_the_source(client_for, member, lead):
    t = solved(member, lead)
    client = client_for(member.login)
    assert "Convertir en artículo" in client.get(f"/foro/{t.pk}/").content.decode()
    form = client.get(f"/conocimiento/nuevo/?hilo={t.pk}").content.decode()
    assert "¿Cómo exporto a IFC?" in form and "Export → IFC" in form
    client.post(
        "/conocimiento/nuevo/",
        {
            "thread": t.pk,
            "title": "Exportar a IFC",
            "body": "Texto",
            "kind": "faq",
            "publish": "on",
        },
    )
    a = Article.objects.get()
    assert a.source_thread == t
    assert "Viene de una consulta" in client.get(f"/conocimiento/{a.pk}/").content.decode()


def test_unauthorised_conversion_redirects_back_with_a_message(
    client_for, member, lead, make_person
):
    t = solved(member, lead)
    other = make_person("otra@lev.cl")
    response = client_for(other.login).get(f"/conocimiento/nuevo/?hilo={t.pk}", follow=True)
    assert "Solo quien abrió la consulta" in response.content.decode()
    assert (
        "Convertir en artículo"
        not in client_for(other.login).get(f"/foro/{t.pk}/").content.decode()
    )


# --- Teo -------------------------------------------------------------------------------------------------------------------


def test_published_articles_enter_teos_index_and_drafts_do_not(member):
    published = services.create_article(
        member, title="Guía de topografía cuántica", body="contenido", kind="faq", publish=True
    )
    draft = services.create_article(
        member, title="Borrador de topografía cuántica", body="otro", kind="faq"
    )
    search.reindex()
    hits = search.search("cuántica")
    assert [h["title"] for h in hits] == ["Guía de topografía cuántica"] and draft
    services.set_published(published, member, False)  # el índice viejo se revalida
    assert search.search("cuántica") == []


# --- mejoras -------------------------------------------------------------------------------------------------------------------


def test_board_columns_follow_the_stages(member, lead):
    imp = services.propose(member, "Plantillas comunes", "Unificar plantillas")
    services.move(imp, lead, stage="plan")
    columns = services.board()
    assert [c["stage"] for c in columns] == ["idea", "plan", "execution", "result"]
    assert [i.title for i in columns[1]["items"]] == ["Plantillas comunes"] and not columns[0][
        "items"
    ]


def test_only_leads_move_and_result_needs_an_outcome(member, lead):
    imp = services.propose(member, "Mejora", "Descripción")
    with pytest.raises(PermissionError):
        services.move(imp, member, stage="plan")
    with pytest.raises(ValueError, match="resultado"):
        services.move(imp, lead, stage="result")
    with pytest.raises(ValueError):
        services.move(imp, lead, stage="zzz")
    services.move(imp, lead, stage="result", owner=lead, outcome="Ahorramos 2 horas por semana")
    imp.refresh_from_db()
    assert imp.stage == "result" and imp.owner == lead and "2 horas" in imp.outcome


def test_owner_must_be_approved(member, lead, make_person):
    pending = make_person("nuevo@lev.cl", status="pending")
    imp = services.propose(member, "Mejora", "Descripción")
    with pytest.raises(ValueError, match="aprobada"):
        services.move(imp, lead, stage="plan", owner=pending)


def test_proposer_is_notified_once_per_stage_change(member, lead):
    imp = services.propose(member, "Mejora", "Descripción")
    services.move(imp, lead, stage="plan")
    services.move(imp, lead, stage="plan")  # sin cambio de etapa: no avisa
    services.move(imp, lead, stage="execution")
    notices = Notification.objects.filter(recipient=member, kind="improvement_stage")
    assert notices.count() == 2 and "Ejecución" in notices.first().title
    own = services.propose(lead, "Mía", "x")
    services.move(own, lead, stage="plan")
    assert not Notification.objects.filter(recipient=lead, kind="improvement_stage").exists()


def test_edit_and_delete_rules(member, lead, make_person):
    other = make_person("otra@lev.cl")
    imp = services.propose(member, "Mejora", "Descripción")
    services.update_improvement(imp, member, title="Editada", description="x")
    with pytest.raises(PermissionError):
        services.update_improvement(imp, other, title="no", description="x")
    services.move(imp, lead, stage="plan")
    with pytest.raises(PermissionError):  # ya no es una idea
        services.update_improvement(imp, member, title="no", description="x")
    with pytest.raises(PermissionError):
        services.delete_improvement(imp, member)
    services.delete_improvement(imp, lead)
    assert not Improvement.objects.exists()


@pytest.mark.parametrize(
    ("title", "description"), [("", "x"), ("t", ""), ("t" * 151, "x"), ("t", "x" * 2001)]
)
def test_proposal_validation(member, title, description):
    with pytest.raises(ValueError):
        services.propose(member, title, description)


def test_board_and_improvement_pages(client_for, member, lead):
    client = client_for(member.login)
    client.post(
        "/conocimiento/mejoras/",
        {"title": "Biblioteca común", "description": "Reunir las familias"},
    )
    imp = Improvement.objects.get()
    html = client.get("/conocimiento/mejoras/").content.decode()
    assert "Biblioteca común" in html and "stage-idea" in html
    page = client.get(f"/conocimiento/mejoras/{imp.pk}/").content.decode()
    assert "Mover de etapa" not in page and "Editar la propuesta" in page
    assert (
        "Mover de etapa"
        in client_for(lead.login).get(f"/conocimiento/mejoras/{imp.pk}/").content.decode()
    )
    client_for(lead.login).post(
        f"/conocimiento/mejoras/{imp.pk}/",
        {"action": "move", "stage": "execution", "owner": lead.pk},
    )
    imp.refresh_from_db()
    assert imp.stage == "execution" and imp.owner == lead
    client.post(
        f"/conocimiento/mejoras/{imp.pk}/", {"action": "move", "stage": "result", "outcome": "x"}
    )
    imp.refresh_from_db()
    assert imp.stage == "execution"  # un miembro no mueve


def test_improvement_text_is_escaped(client_for, member):
    imp = services.propose(member, "<script>x</script>", "<img src=x onerror=1>")
    html = client_for(member.login).get(f"/conocimiento/mejoras/{imp.pk}/").content.decode()
    assert (
        "<script>x</script>" not in html and "<img src=x" not in html and "&lt;script&gt;" in html
    )


def test_module_nav_and_pending_access(client_for, member, make_person):
    assert 'href="/conocimiento/"' in client_for(member.login).get("/").content.decode()
    pending = make_person("nuevo@lev.cl", status="pending")
    assert client_for(pending.login).get("/conocimiento/").status_code != 200
