import copy
import json
import shutil
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts import services as account_services
from apps.catalog.models import Discipline, Platform, Product, Resource, Skill, Vendor
from apps.paths.models import (
    ExternalCourse,
    LearningPath,
    Level,
    Milestone,
    PathExtra,
    QuizQuestion,
    SharedItem,
)

pytestmark = pytest.mark.django_db

SEED = Path(settings.BASE_DIR) / "seed"


def seed(*args):
    call_command("seed_catalog", *args, verbosity=0)


def counts():
    return {
        model.__name__: model.objects.count()
        for model in (
            Discipline, Vendor, Product, Platform, Skill, Resource, LearningPath, Level,
            Milestone, QuizQuestion, ExternalCourse, PathExtra, SharedItem,
        )
    }  # fmt: skip


@pytest.fixture
def seeded():
    seed()


@pytest.fixture
def seed_copy(tmp_path):
    target = tmp_path / "seed"
    shutil.copytree(SEED, target)
    return target


def edit_json(path, fn):
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# --- seed_catalog -----------------------------------------------------------------------------


def test_seed_twice_does_not_duplicate():
    seed()
    first = counts()
    seed()
    assert counts() == first


def test_forma_revit_has_7_levels_and_all_keys(seeded):
    data = json.loads((SEED / "rutas/forma-revit.json").read_text(encoding="utf-8"))
    path = LearningPath.objects.get(slug="forma-revit")
    assert path.levels.count() == 7
    assert path.kind == "structured" and path.world == "architecture"
    assert set(path.milestones.values_list("key", flat=True)) == {
        m["key"] for level in data["levels"] for m in level["milestones"]
    }
    assert set(path.quiz_questions.values_list("key", flat=True)) == {
        q["key"] for level in data["levels"] for q in level["quiz"]
    }
    assert path.milestones.count() == 34 and path.quiz_questions.count() == 10


def test_bentley_route_is_external_with_courses(seeded):
    path = LearningPath.objects.get(slug="bentley-learn")
    assert path.is_external and path.world == "civil" and path.allow_free_courses
    assert path.levels.count() == 5
    keys = set(path.external_courses.values_list("key", flat=True))
    assert {"ms-c0", "ord-c0", "obr-c0", "obd-c2"} <= keys
    assert path.levels.get(code="lib").is_free_courses
    assert path.levels.get(code="obd").completion_rule == "any_one"
    course = path.external_courses.get(key="ord-c0")
    assert course.resource.grants_completion_certificate and course.reward == "relic"
    assert {s.slug for s in course.resource.skills.all()} >= {"corredores-viales", "earthwork"}


def test_milestones_link_to_certificate_resources(seeded):
    milestone = Milestone.objects.get(path__slug="forma-revit", key="n2-t5")
    assert milestone.completed_by_resource.title == "Learn Forma Site Design in 90 minutes"
    assert milestone.completed_by_resource.grants_completion_certificate


def test_extras_and_shared_items_loaded(seeded):
    forma = LearningPath.objects.get(slug="forma-revit")
    kinds = set(forma.extras.values_list("kind", flat=True))
    assert {"capability", "glossary", "team_kit", "rollout_phase", "certification_goal"} <= kinds
    assert forma.shared_items.filter(key="kit0-1").exists()
    assert (
        LearningPath.objects.get(slug="bentley-learn")
        .extras.filter(kind="certification_step")
        .exists()
    )


def test_dry_run_saves_nothing():
    seed("--dry-run")
    assert LearningPath.objects.count() == 0 and Vendor.objects.count() == 0


def test_dry_run_detects_duplicate_key(seed_copy):
    def duplicate(data):
        level = data["levels"][0]
        level["milestones"].append(copy.deepcopy(level["milestones"][0]))

    edit_json(seed_copy / "rutas/forma-revit.json", duplicate)
    with pytest.raises(CommandError, match="error"):
        seed("--seed-dir", str(seed_copy), "--dry-run")
    assert LearningPath.objects.count() == 0


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(world="marte"),
        lambda d: d.update(vendor="nadie"),
        lambda d: d.update(products=["no-existe"]),
        lambda d: d["levels"][0]["quiz"][0].update(answer=99),
        lambda d: d["levels"][1]["milestones"][0].update(completed_by_resource="Curso inexistente"),
    ],
    ids=["mundo", "vendor", "producto", "respuesta", "recurso-de-hito"],
)
def test_invalid_routes_are_rejected_without_partial_writes(seed_copy, mutate):
    edit_json(seed_copy / "rutas/forma-revit.json", mutate)
    with pytest.raises(CommandError):
        seed("--seed-dir", str(seed_copy))
    assert LearningPath.objects.count() == 0 and Vendor.objects.count() == 0


def test_unknown_skill_in_external_course_is_rejected(seed_copy):
    def mutate(data):
        data["levels"][0]["external_courses"][0]["skills"] = ["inventada"]

    edit_json(seed_copy / "rutas/bentley-learn.json", mutate)
    with pytest.raises(CommandError):
        seed("--seed-dir", str(seed_copy), "--dry-run")


def test_removed_items_are_retired_not_deleted_and_come_back(seed_copy):
    seed("--seed-dir", str(seed_copy))
    path_file = seed_copy / "rutas/forma-revit.json"

    edit_json(path_file, lambda d: d["levels"][0]["milestones"].pop(0))
    seed("--seed-dir", str(seed_copy))
    gone = Milestone.objects.get(path__slug="forma-revit", key="n0-t0")
    assert gone.retired
    assert Milestone.objects.filter(path__slug="forma-revit").count() == 34

    edit_json(
        path_file,
        lambda d: d["levels"][0]["milestones"].insert(0, {"key": "n0-t0", "text": "de vuelta"}),
    )
    seed("--seed-dir", str(seed_copy))
    gone.refresh_from_db()
    assert not gone.retired and gone.text == "de vuelta"


def test_seed_updates_text_by_key_without_changing_ids(seed_copy):
    seed("--seed-dir", str(seed_copy))
    before = Milestone.objects.get(path__slug="forma-revit", key="n1-t1").pk
    edit_json(
        seed_copy / "rutas/forma-revit.json",
        lambda d: d["levels"][1]["milestones"][1].update(text="Texto nuevo con *Levels*"),
    )
    seed("--seed-dir", str(seed_copy))
    milestone = Milestone.objects.get(path__slug="forma-revit", key="n1-t1")
    assert milestone.pk == before and milestone.text == "Texto nuevo con *Levels*"


def test_missing_seed_dir_is_an_error(tmp_path):
    with pytest.raises(CommandError):
        seed("--seed-dir", str(tmp_path / "no-existe"))


def test_unique_keys_per_path_are_enforced_by_the_database(seeded):
    from django.db import IntegrityError, transaction

    level = Level.objects.filter(path__slug="forma-revit").first()
    with pytest.raises(IntegrityError), transaction.atomic():
        Milestone.objects.create(path=level.path, level=level, key="n0-t0", text="duplicada")


# --- Person.disciplines -------------------------------------------------------------------------


def test_person_can_have_disciplines(seeded, member):
    member.disciplines.set(Discipline.objects.filter(slug__in=["civil-estructural", "topografia"]))
    assert member.disciplines.count() == 2
    assert Discipline.objects.get(slug="civil-estructural").people.count() == 1


# --- vistas -------------------------------------------------------------------------------------


def test_paths_index_lists_vendor_tabs_and_paths(seeded, member_client):
    html = member_client.get("/rutas/").content.decode()
    assert "Autodesk" in html and "Bentley Systems" in html
    assert "Ruta Forma + Revit" in html  # primer vendor por orden


def test_paths_index_vendor_tab_switches(seeded, member_client):
    html = member_client.get("/rutas/?vendor=bentley").content.decode()
    assert "Ruta Bentley" in html and "Ruta Forma + Revit" not in html


def test_paths_index_filters_by_product_and_discipline(seeded, member_client):
    assert (
        "Ruta Bentley"
        in member_client.get("/rutas/?vendor=bentley&product=openbridge").content.decode()
    )
    assert (
        "No hay rutas" in member_client.get("/rutas/?vendor=bentley&product=staad").content.decode()
    )
    assert (
        "Ruta Bentley"
        in member_client.get("/rutas/?vendor=bentley&discipline=mecanica").content.decode()
    )
    assert (
        "No hay rutas"
        in member_client.get("/rutas/?vendor=bentley&discipline=captura-rpa").content.decode()
    )


def test_paths_index_filters_by_skill(seeded, member_client):
    html = member_client.get("/rutas/?vendor=bentley&skill=corredores-viales").content.decode()
    assert "Ruta Bentley" in html
    html = member_client.get("/rutas/?vendor=bentley&skill=gnss").content.decode()
    assert "No hay rutas" in html


def test_paths_index_empty_without_seed(member_client):
    assert "seed_catalog" in member_client.get("/rutas/").content.decode()


def test_path_detail_structured_uses_its_world(seeded, member_client):
    response = member_client.get("/rutas/forma-revit/?nivel=n3")
    html = response.content.decode()
    assert response.status_code == 200
    assert "Levantamiento Digital" in html and "CC 410" in html
    assert 'aria-label="Nivel N3' in html
    assert '<em class="term">Send to Revit</em>' in html
    assert (
        "Learn Forma Site Design in 90 minutes"
        in member_client.get("/rutas/forma-revit/?nivel=n2").content.decode()
    )


def test_path_detail_generic_for_worlds_not_built_yet(seeded, member_client):
    LearningPath.objects.filter(slug="forma-revit").update(world="mechanical")
    html = member_client.get("/rutas/forma-revit/").content.decode()
    assert 'id="n3"' in html and '<em class="term">Send to Revit</em>' in html


def test_path_detail_external(seeded, member_client):
    html = member_client.get("/rutas/bentley-learn/").content.decode()
    assert "Bentley Accredited Road Modeler" in html
    assert "Reliquia" in html and "Qué incluye" in html
    assert "Confirmar enlace" in html  # cursos con verify_url


def test_path_detail_404(seeded, member_client):
    assert member_client.get("/rutas/no-existe/").status_code == 404


def test_unpublished_path_hidden_from_members_visible_to_leads(
    seeded, member_client, client_for, lead
):
    LearningPath.objects.filter(slug="bentley-learn").update(is_published=False)
    assert member_client.get("/rutas/bentley-learn/").status_code == 404
    assert "Ruta Bentley" not in member_client.get("/rutas/?vendor=bentley").content.decode()
    assert client_for(lead.login).get("/rutas/bentley-learn/").status_code == 200


def test_terms_filter_escapes_html():
    from apps.core.templatetags.core_extras import terms

    out = terms("<script>alert(1)</script> usa *Send to Revit* & <b>x</b>")
    assert "<script>" not in out and "&lt;script&gt;" in out
    assert '<em class="term">Send to Revit</em>' in out
    assert "&amp;" in out and "<b>" not in out


def test_catalog_lists_and_filters(seeded, member_client):
    html = member_client.get("/catalogo/?q=hub").content.decode()
    assert "Forma Learning Hub" in html

    only_bentley = member_client.get("/catalogo/?platform=bentley-learn").content.decode()
    assert "Navigating Bentley Learn" in only_bentley and "Forma Learning Hub" not in only_bentley

    exams = member_client.get("/catalogo/?kind=exam").content.decode()
    assert "Autodesk Certified User: Revit" in exams and "Forma Learning Hub" not in exams

    certs = member_client.get("/catalogo/?cert=1").content.decode()
    assert "Learn Forma Site Design in 90 minutes" in certs and "Forma Learning Hub" not in certs

    free = member_client.get("/catalogo/?free=1").content.decode()
    assert "Autodesk Certified User: Revit" not in free  # los exámenes no son gratuitos


def test_catalog_search_and_invalid_kind(seeded, member_client):
    assert "OpenRoads" in member_client.get("/catalogo/?q=openroads").content.decode()
    assert member_client.get("/catalogo/?kind=<script>").status_code == 200


def test_catalog_paginates(seeded, member_client):
    html = member_client.get("/catalogo/").content.decode()
    assert "Página 1 de 2" in html
    assert member_client.get("/catalogo/?page=2").status_code == 200


def test_pending_person_cannot_see_paths(client_for, make_person):
    pending = make_person("p@lev.cl", status="pending")
    assert client_for(pending.login).get("/rutas/").status_code == 302


def test_set_role_lead_sees_unpublished_via_service(seeded, member):
    account_services.set_role(member, "lead")
    assert member.is_lead
