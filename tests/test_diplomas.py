"""Diploma interno (apps/diplomas): solo rutas nuestras, se emite una vez, lo ven la persona y quien lidera."""

from datetime import date
from pathlib import Path

import pytest
from django.core.management import call_command

from apps.catalog.models import Platform, Vendor
from apps.credentials.models import Credential
from apps.diplomas import services
from apps.gamification.models import XPEvent
from apps.notifications.models import Notification
from apps.paths.models import LearningPath, Level, Milestone, QuizQuestion
from apps.progress import services as progress

pytestmark = pytest.mark.django_db
FIXTURES = Path(__file__).parent / "fixtures" / "dgac"


def _catalog():
    """Catálogo mínimo: la prueba no depende de las semillas completas (otros agentes las editan)."""
    vendor, _ = Vendor.objects.get_or_create(slug="aeroacademy", defaults={"name": "AeroAcademy"})
    for slug, kind in (("interna", "vendor"), ("autodesk-learning", "learning")):
        Platform.objects.get_or_create(slug=slug, defaults={"name": slug, "kind": kind})
    return vendor


def make_route(slug="lev-prueba", platform="interna", title="Topografía de prueba"):
    vendor = _catalog()
    path = LearningPath.objects.create(
        slug=slug,
        title=title,
        platform=Platform.objects.get(slug=platform),
        vendor=vendor,
        kind=LearningPath.Kind.STRUCTURED,
        world="architecture",
    )
    level = Level.objects.create(
        path=path, code="n1", order=1, short="Uno", title="Nivel uno", estimated_hours="2 h"
    )
    level2 = Level.objects.create(
        path=path, code="n2", order=2, short="Dos", title="Nivel dos", estimated_hours="3 a 5 h"
    )
    for i, lv in enumerate((level, level2)):
        Milestone.objects.create(path=path, level=lv, key=f"m{i}a", order=0, text="Mide")
        Milestone.objects.create(path=path, level=lv, key=f"m{i}b", order=1, text="Dibuja")
    QuizQuestion.objects.create(
        path=path, level=level, key="q0", order=0, question="¿?", options=["a", "b"], answer_index=1
    )
    return path


def finish(person, path, *, leave_out=None):
    for m in Milestone.objects.filter(path=path):
        if m.key != leave_out:
            progress.set_milestone(person, m, True)
    for q in QuizQuestion.objects.filter(path=path):
        progress.answer_question(person, q, q.answer_index)


def diploma_creds(person):
    return Credential.objects.filter(owner=person, kind=Credential.Kind.INTERNAL)


# --- cuáles rutas son nuestras ----------------------------------------------------------------------------------------


def test_internal_rule_is_data_driven(settings):
    ours = make_route()
    theirs = make_route("autodesk-x", platform="autodesk-learning")
    assert services.is_internal(ours) and not services.is_internal(theirs)
    assert services.has_diploma(ours) and not services.has_diploma(theirs)
    settings.INTERNAL_PLATFORMS = {"autodesk-learning"}
    assert services.is_internal(theirs) and not services.is_internal(ours)


def test_unpublished_or_external_track_routes_have_no_diploma():
    path = make_route()
    path.is_published = False
    assert not services.has_diploma(path)
    path.is_published, path.kind = True, LearningPath.Kind.EXTERNAL_TRACK
    assert not services.has_diploma(path)
    assert not services.has_diploma(None)


def test_external_route_never_gets_a_diploma(member, member_client):
    path = make_route("autodesk-x", platform="autodesk-learning")
    finish(member, path)
    assert not diploma_creds(member).exists()
    assert member_client.get("/diplomas/autodesk-x/").status_code == 404
    assert member_client.get("/diplomas/forma-revit/").status_code == 404  # ruta real de Autodesk
    assert member_client.get("/diplomas/no-existe/").status_code == 404
    assert services.route_link(member, path) is None


# --- cuándo se gana ----------------------------------------------------------------------------------------------------


def test_incomplete_route_says_not_yet(member, member_client):
    path = make_route()
    finish(member, path, leave_out="m1b")
    resp = member_client.get("/diplomas/lev-prueba/")
    assert resp.status_code == 404 and "Aún no hay diploma" in resp.content.decode()
    assert not diploma_creds(member).exists()
    assert services.route_link(member, path) is None


def test_quiz_must_be_answered_correctly(member, member_client):
    path = make_route()
    for m in Milestone.objects.filter(path=path):
        progress.set_milestone(member, m, True)
    progress.answer_question(member, QuizQuestion.objects.get(path=path), 0)  # incorrecta
    assert not diploma_creds(member).exists()
    progress.answer_question(member, QuizQuestion.objects.get(path=path), 1)
    assert diploma_creds(member).count() == 1


def test_completion_issues_exactly_one_internal_credential(member):
    path = make_route()
    finish(member, path)
    cred = diploma_creds(member).get()
    assert cred.status == Credential.Status.VERIFIED and not cred.file
    assert cred.path == path and cred.credential_id == "DIPLOMA-lev-prueba"
    assert cred.reviewed_by is None and cred.platform.slug == "interna"
    assert XPEvent.objects.filter(person=member, source=f"credential:{cred.pk}").exists()
    assert Notification.objects.filter(recipient=member, kind="diploma").count() == 1

    # desmarcar y volver a marcar no duplica credencial, XP ni aviso
    m = Milestone.objects.filter(path=path).first()
    progress.set_milestone(member, m, False)
    progress.set_milestone(member, m, True)
    services.ensure_issued(member, path)
    assert diploma_creds(member).count() == 1
    assert XPEvent.objects.filter(person=member, source=f"credential:{cred.pk}").count() == 1
    assert Notification.objects.filter(recipient=member, kind="diploma").count() == 1


def test_diploma_survives_unchecking_a_mission(member, member_client):
    path = make_route()
    finish(member, path)
    progress.set_milestone(member, Milestone.objects.filter(path=path).first(), False)
    assert diploma_creds(member).count() == 1
    assert member_client.get("/diplomas/lev-prueba/").status_code == 200


def test_lazy_issue_for_routes_completed_before_this_feature(member, member_client):
    path = make_route()
    finish(member, path)
    diploma_creds(member).delete()
    assert member_client.get("/diplomas/lev-prueba/").status_code == 200
    assert diploma_creds(member).count() == 1


# --- quién lo ve --------------------------------------------------------------------------------------------------------


def test_owner_and_leads_can_view_others_get_404(client_for, member, lead, make_person):
    path = make_route()
    finish(member, path)
    other = make_person("pepe@lev.cl")
    url = f"/diplomas/lev-prueba/?persona={member.pk}"
    assert client_for(member.login).get("/diplomas/lev-prueba/").status_code == 200
    assert client_for(member.login).get(url).status_code == 200  # el suyo, indicado
    resp = client_for(lead.login).get(url)
    assert resp.status_code == 200 and member.name in resp.content.decode()
    assert client_for(other.login).get(url).status_code == 404
    assert client_for(other.login).get("/diplomas/lev-prueba/").status_code == 404  # no completó
    assert client_for(lead.login).get("/diplomas/lev-prueba/?persona=99999").status_code == 404
    assert client_for(lead.login).get("/diplomas/lev-prueba/?persona=abc").status_code == 404


def test_lead_does_not_see_a_diploma_that_was_not_earned(client_for, member, lead):
    make_route()
    resp = client_for(lead.login).get(f"/diplomas/lev-prueba/?persona={member.pk}")
    assert resp.status_code == 404 and "todavía no completa" in resp.content.decode()
    assert not diploma_creds(member).exists()


# --- el diploma ----------------------------------------------------------------------------------------------------------


def test_page_shows_name_never_the_email(client_for, make_person):
    person = make_person("camila.rojas@lev.cl")
    person.display_name = "Camila Rojas"
    person.save(update_fields=["display_name"])
    finish(person, make_route())
    html = client_for(person.login).get("/diplomas/lev-prueba/").content.decode()
    assert "Camila Rojas" in html
    assert "camila.rojas@lev.cl" not in html and "@lev.cl" not in html


def test_page_without_display_name_still_hides_the_email(client_for, member):
    finish(member, make_route())
    html = client_for(member.login).get("/diplomas/lev-prueba/").content.decode()
    assert (
        "ana@lev.cl" not in html
        and "@" not in html.split('class="dp-sheet"')[1].split("</article>")[0]
    )


def test_page_content_stamp_and_title_block(member_client, member):
    finish(member, make_route())
    resp = member_client.get("/diplomas/lev-prueba/")
    html = resp.content.decode()
    assert "Topografía de prueba" in html
    assert "AEROACADEMY" in html and "Levantamiento" in html and "<b>101</b>" in html
    assert (
        "APROBADO" in html and "teo-celebra.svg" in html and "REVISÓ NALA" in html
    )  # sello de Nala
    assert "Lámina" in html and "D-101" in html and "1:1" in html and "Revisó" in html
    assert "Aprobó" in html and "Sistema" in html
    assert "Imprimir / Guardar PDF" in html and "@page" not in html  # el CSS va en el archivo
    assert "http" not in resp.context["code"] and resp.context["code"].startswith("D101-")
    assert resp.context["code"] in html
    facts = dict(resp.context["facts"])
    assert (
        facts["Horas"] == "5–7 h" and facts["Niveles"] == "2 de 2" and int(facts["XP ganada"]) > 0
    )
    assert "UTM 19S" in html and "doodle" not in resp.context  # coordenadas de adorno


def test_verification_code_is_stable_and_personal(member, lead):
    path = make_route()
    finish(member, path)
    cred = diploma_creds(member).get()
    when = date(2026, 10, 9)
    a = services.verification_code(cred, member, when)
    assert a == services.verification_code(cred, member, when)
    assert a != services.verification_code(cred, lead, when)
    assert a != services.verification_code(cred, member, date(2026, 10, 10))


def test_hours_parsing():
    class L:
        def __init__(self, h):
            self.estimated_hours = h

    assert services._hours([L("1 h"), L("2 h")]) == "3 h"
    assert services._hours([L("15 a 25 h"), L("6 a 8 h")]) == "21–33 h"
    assert services._hours([L(""), L("2,5 h")]) == "2,5 h"
    assert services._hours([L("")]) == ""


# --- enlaces -------------------------------------------------------------------------------------------------------------


def test_route_page_links_to_diploma_only_when_earned(member_client, member):
    path = make_route()
    assert "Ver mi diploma" not in member_client.get("/rutas/lev-prueba/").content.decode()
    finish(member, path)
    html = member_client.get("/rutas/lev-prueba/").content.decode()
    assert "Ver mi diploma" in html and "/diplomas/lev-prueba/" in html


def test_external_route_page_has_no_diploma_link(member_client, member):
    path = make_route("autodesk-x", platform="autodesk-learning")
    finish(member, path)
    assert "Ver mi diploma" not in member_client.get("/rutas/autodesk-x/").content.decode()


def test_credential_detail_links_to_the_diploma(client_for, member, lead):
    path = make_route()
    finish(member, path)
    cred = diploma_creds(member).get()
    own = client_for(member.login).get(f"/certificados/{cred.pk}/").content.decode()
    assert "Ver diploma" in own and "/diplomas/lev-prueba/" in own
    boss = client_for(lead.login).get(f"/certificados/{cred.pk}/").content.decode()
    assert f"/diplomas/lev-prueba/?persona={member.pk}" in boss


def test_uploaded_credentials_have_no_diploma_link(member, member_client):
    cred = Credential.objects.create(
        owner=member,
        title="Curso",
        kind=Credential.Kind.COMPLETION,
        status=Credential.Status.VERIFIED,
        path=make_route(),
    )
    assert "Ver diploma" not in member_client.get(f"/certificados/{cred.pk}/").content.decode()


# --- DGAC: su propia regla, el mismo diseño ----------------------------------------------------------------------------


@pytest.fixture
def dgac(settings):
    settings.DGAC_DATA_DIR = FIXTURES
    call_command("seed_catalog", verbosity=0)
    call_command("cargar_dgac", verbosity=0)


def test_dgac_diploma_uses_the_shared_design(dgac, member, member_client):
    from tests.test_dgac import attempt_with

    assert member_client.get("/diplomas/dgac-rpas/").status_code == 404  # aún sin la prueba
    # completar misiones NO emite el diploma DGAC: lo gana la prueba
    finish(member, LearningPath.objects.get(slug="dgac-rpas"))
    assert not Credential.objects.filter(owner=member, credential_id="DGAC-RPAS-INTERNO").exists()
    attempt = attempt_with(member, 25)
    assert attempt.passed
    html = member_client.get(f"/dgac/diploma/{attempt.pk}/").content.decode()
    assert member.name in html and "Diploma de prueba" in html
    assert "APROBADO" in html and "teo-celebra.svg" in html and "D-101" in html and "D101-" in html
    assert "Puntaje" in html and "Vigente hasta" in html
    assert member_client.get("/diplomas/dgac-rpas/").status_code == 200
    assert Notification.objects.filter(recipient=member, kind="diploma").count() == 1


def test_dgac_credential_links_to_diploma(dgac, member, member_client):
    from tests.test_dgac import attempt_with

    attempt = attempt_with(member, 25)
    html = member_client.get(f"/certificados/{attempt.credential.pk}/").content.decode()
    assert "Ver diploma" in html and "/diplomas/dgac-rpas/" in html


def test_dgac_failed_attempt_has_no_diploma(dgac, member, member_client):
    from tests.test_dgac import attempt_with

    attempt = attempt_with(member, 1)
    assert member_client.get(f"/dgac/diploma/{attempt.pk}/").status_code == 404
    assert member_client.get("/diplomas/dgac-rpas/").status_code == 404
