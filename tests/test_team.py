import time

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.catalog.models import Skill
from apps.community import services as notes
from apps.credentials import services as creds
from apps.paths.models import ExternalCourse, LearningPath, Milestone, QuizQuestion, SharedItem
from apps.progress import external
from apps.progress import services as progress
from apps.team import services
from apps.team.models import SharedCheck

pytestmark = pytest.mark.django_db
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF\n" + b"x" * 200
FORMA, BENTLEY = "forma-revit", "bentley-learn"


@pytest.fixture(autouse=True)
def seeded(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    call_command("seed_catalog", verbosity=0)


def make_cred(owner, lead=None, *, verify=True, **extra):
    fields = {"title": "Curso", "kind": "completion", "visibility": "team", **extra}
    cred = creds.create_credential(owner, fields, SimpleUploadedFile("c.pdf", PDF))
    if verify:
        creds.verify(cred, lead)
    return cred


def path(slug):
    return LearningPath.objects.get(slug=slug)


# --- avance en lote = avance de cada mundo -------------------------------------------------------------------------


def test_bulk_percentages_match_each_worlds_own_calculation(member, lead, make_person):
    other = make_person("otra@lev.cl")
    forma, bentley = path(FORMA), path(BENTLEY)
    for m in list(Milestone.objects.filter(path=forma, retired=False))[:7]:
        progress.set_milestone(member, m, True)
    for q in list(QuizQuestion.objects.filter(path=forma, retired=False))[:3]:
        progress.answer_question(member, q, q.answer_index)
        progress.answer_question(other, q, (q.answer_index + 1) % len(q.options))
    for course in list(ExternalCourse.objects.filter(path=bentley, is_required=True))[:4]:
        make_cred(other, lead, resource=course.resource, path=bentley, title=course.key)
    people, paths = [member, other, lead], [forma, bentley]
    bulk = services.path_percentages(people, paths)
    for person in people:
        assert bulk[(person.pk, forma.pk)] == progress.world_context(person, forma)["stats"]["pct"]
        assert (
            bulk[(person.pk, bentley.pk)]
            == external.external_context(person, bentley)["stats"]["pct"]
        )
    assert bulk[(other.pk, bentley.pk)] > 0 and bulk[(member.pk, forma.pk)] > 0


def test_pending_and_rejected_credentials_do_not_count_in_bulk(member, lead):
    bentley = path(BENTLEY)
    course = ExternalCourse.objects.filter(path=bentley, is_required=True).first()
    make_cred(member, lead, verify=False, resource=course.resource, path=bentley)
    assert services.path_percentages([member], [bentley])[(member.pk, bentley.pk)] == 0


def test_unpublished_paths_only_for_leads(client_for, member, lead):
    LearningPath.objects.filter(slug=BENTLEY).update(is_published=False)
    assert (
        "Bentley"
        not in client_for(member.login)
        .get("/equipo/")
        .content.decode()
        .split("<table")[1]
        .split("</thead>")[0]
    )
    assert (
        "Bentley"
        in client_for(lead.login)
        .get("/equipo/")
        .content.decode()
        .split("<table")[1]
        .split("</thead>")[0]
    )


# --- tablero -----------------------------------------------------------------------------------------------------------


def test_board_shows_people_notes_credentials_and_expiry(client_for, member, lead):
    from datetime import timedelta

    from django.utils import timezone

    notes.create_note(member, path(FORMA), "Nota visible del tablero", "tip")
    make_cred(
        member, lead, title="Cred reciente", expires_on=timezone.localdate() + timedelta(days=10)
    )
    make_cred(member, lead, title="Cred vieja", expires_on=timezone.localdate() - timedelta(days=3))
    html = client_for(member.login).get("/equipo/").content.decode()
    assert member.name in html and "Nota visible del tablero" in html
    assert "Cred reciente" in html and "Cred vieja" in html and "Vencida" in html


def test_board_hides_private_credentials_from_members(client_for, member, lead, make_person):
    other = make_person("otra@lev.cl")
    make_cred(other, lead, title="Credencial privada", visibility="private")
    assert "Credencial privada" not in client_for(member.login).get("/equipo/").content.decode()
    assert "Credencial privada" in client_for(lead.login).get("/equipo/").content.decode()


def test_board_excludes_hidden_notes_and_pending_people(client_for, member, lead, make_person):
    from apps.community import moderation

    n = notes.create_note(member, path(FORMA), "Nota que se oculta", "tip")
    moderation.set_hidden(n, lead, True, "no")
    pending = make_person("nuevo@lev.cl", status="pending")
    html = client_for(member.login).get("/equipo/").content.decode()
    assert "Nota que se oculta" not in html and pending.name not in html


def test_board_requires_approval(client_for, make_person):
    pending = make_person("nuevo@lev.cl", status="pending")
    assert client_for(pending.login).get("/equipo/").status_code != 200


def test_board_is_fast_and_flat_with_30_people_and_300_credentials(
    client_for, member, lead, make_person
):
    people = [make_person(f"p{i}@lev.cl") for i in range(30)]
    skill = Skill.objects.first()
    for i in range(300):
        cred = make_cred(people[i % 30], lead, title=f"C{i}")
        if i % 3 == 0:
            cred.skills.add(skill)
    client = client_for(lead.login)
    for url in ("/equipo/", "/equipo/matriz/"):
        client.get(url)  # calienta
        started = time.perf_counter()
        with CaptureQueriesContext(connection) as ctx:
            assert client.get(url).status_code == 200
        elapsed = time.perf_counter() - started
        assert elapsed < 1.5, f"{url} tardó {elapsed:.2f}s"
        assert len(ctx) < 60, f"{url}: {len(ctx)} consultas"


# --- matriz -------------------------------------------------------------------------------------------------------------


def test_matrix_counts_verified_credentials_by_skill(member, lead):
    lidar, gnss = Skill.objects.get(slug="lidar"), Skill.objects.get(slug="gnss")
    a = make_cred(member, lead, title="A")
    a.skills.set([lidar, gnss])
    b = make_cred(member, lead, title="B")
    b.skills.set([lidar])
    make_cred(member, lead, verify=False, title="Pendiente").skills.set([gnss])
    m = services.matrix(lead)
    names = [s.slug for s in m["skills"]]
    row = next(r for r in m["rows"] if r["person"].pk == member.pk)
    assert row["cells"][names.index("lidar")] == 2 and row["cells"][names.index("gnss")] == 1
    assert m["totals"][names.index("lidar")] == 2


def test_matrix_filter_by_attribute_and_visibility(member, lead, make_person):
    other = make_person("otra@lev.cl")
    secret = make_cred(other, lead, title="Privada", visibility="private")
    secret.skills.set([Skill.objects.get(slug="lidar")])
    cap = services.matrix(member, "CAP")
    assert {s.attribute for s in cap["skills"]} == {"CAP"}
    row = next(r for r in cap["rows"] if r["person"].pk == other.pk)
    assert sum(row["cells"]) == 0  # el miembro no ve lo privado
    row = next(r for r in services.matrix(lead, "CAP")["rows"] if r["person"].pk == other.pk)
    assert sum(row["cells"]) == 1
    assert len(services.matrix(member, "XXX")["skills"]) == Skill.objects.count()


def test_matrix_page(client_for, member):
    html = client_for(member.login).get("/equipo/matriz/?atributo=CAP").content.decode()
    assert "Matriz de competencias" in html and "LiDAR" in html and "Modelado BIM" not in html


# --- kit y plan ----------------------------------------------------------------------------------------------------------


def test_kit_page_has_groups_phases_and_gantt(client_for, member):
    html = client_for(member.login).get(f"/equipo/kit/{FORMA}/").content.decode()
    assert "Accesos y licencias" in html and "Fase 1" in html and "gantt" in html
    assert "kit0-1" in html


def test_checks_are_shared_and_remember_who(client_for, member, lead):
    client_for(member.login).post(f"/equipo/kit/{FORMA}/kit0-1/", {"checked": "1"})
    check = SharedCheck.objects.get()
    assert check.item.key == "kit0-1" and check.checked_by == member
    client_for(lead.login).post(f"/equipo/kit/{FORMA}/kit0-1/", {"checked": "1"})  # idempotente
    assert SharedCheck.objects.count() == 1 and SharedCheck.objects.get().checked_by == member
    html = client_for(lead.login).get(f"/equipo/kit/{FORMA}/").content.decode()
    assert member.name in html
    client_for(lead.login).post(f"/equipo/kit/{FORMA}/kit0-1/", {"checked": "0"})
    assert not SharedCheck.objects.exists()


def test_phase_progress_follows_checks(member):
    phase_item = SharedItem.objects.filter(path=path(FORMA), key__startswith="ph1-").first()
    services.set_shared(phase_item, member, True)
    data = services.kit_and_plan(path(FORMA))
    phase = next(p for p in data["phases"] if p["title"] == phase_item.group_title)
    assert (
        phase["done"] == 1
        and phase["pct"] > 0
        and 0 <= phase["offset"] <= 100
        and phase["width"] > 0
    )


def test_unknown_item_or_path_is_404_and_pending_cannot_toggle(client_for, member, make_person):
    client = client_for(member.login)
    assert client.post(f"/equipo/kit/{FORMA}/zzz/", {"checked": "1"}).status_code == 404
    assert client.post("/equipo/kit/nope/kit0-1/", {"checked": "1"}).status_code == 404
    assert client.get("/equipo/kit/nope/").status_code == 404
    pending = make_person("nuevo@lev.cl", status="pending")
    assert (
        client_for(pending.login).post(f"/equipo/kit/{FORMA}/kit0-1/", {"checked": "1"}).status_code
        != 302
        or not SharedCheck.objects.exists()
    )
    assert not SharedCheck.objects.exists()


def test_toggle_requires_post(client_for, member):
    assert client_for(member.login).get(f"/equipo/kit/{FORMA}/kit0-1/").status_code == 405


def test_kit_text_is_escaped(client_for, member):
    item = SharedItem.objects.get(path=path(FORMA), key="kit0-0")
    item.text = "<script>alert(1)</script> y *Revit*"
    item.save()
    html = client_for(member.login).get(f"/equipo/kit/{FORMA}/").content.decode()
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html


def test_navigation_and_module(client_for, member):
    html = client_for(member.login).get("/").content.decode()
    assert 'href="/equipo/"' in html
