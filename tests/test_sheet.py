import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command

from apps.catalog.models import Resource, Skill
from apps.credentials import services as creds
from apps.gamification import game, sheet
from apps.gamification.models import Title

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF\n" + b"x" * 200


@pytest.fixture(autouse=True)
def seeded(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    call_command("seed_catalog", verbosity=0)


def make_cred(owner, **extra):
    data = {"title": "Curso", "kind": "completion", "visibility": "team", **extra}
    return creds.create_credential(owner, data, SimpleUploadedFile("c.pdf", PDF))


def verified(owner, lead, skills=(), **extra):
    cred = make_cred(owner, **extra)
    if skills:
        cred.skills.set(Skill.objects.filter(slug__in=skills))
    creds.verify(cred, lead)
    return cred


def form_data(**extra):
    return {
        "headline": "Modeladora BIM",
        "bio": "Me gusta modelar.",
        "character_class": "architect",
        "show_game_view": "on",
        **extra,
    }


# --- edición ----------------------------------------------------------------------------------------------------


def test_only_the_owner_edits_and_the_route_takes_no_id(client_for, member, lead):
    client_for(member.login).post("/perfil/editar/", form_data())
    member.refresh_from_db()
    lead.refresh_from_db()
    assert member.headline == "Modeladora BIM" and lead.headline == ""
    assert client_for(member.login).post("/perfil/5/editar/", form_data()).status_code == 404


def test_saving_stores_class_links_and_view(client_for, member):
    client_for(member.login).post(
        "/perfil/editar/",
        form_data(
            linkedin="https://www.linkedin.com/in/ana", credly="https://www.credly.com/users/ana"
        ),
    )
    member.refresh_from_db()
    assert member.character_class == "architect" and member.show_game_view is True
    assert member.links == {
        "linkedin": "https://www.linkedin.com/in/ana",
        "credly": "https://www.credly.com/users/ana",
    }


@pytest.mark.parametrize(
    "url",
    [
        "http://www.linkedin.com/in/x",
        "https://evil.com/linkedin.com",
        "javascript:alert(1)",
        "https://linkedin.com.evil.io/x",
    ],
)
def test_links_must_be_https_on_the_right_site(client_for, member, url):
    response = client_for(member.login).post("/perfil/editar/", form_data(linkedin=url))
    member.refresh_from_db()
    assert response.status_code == 200 and "linkedin" not in member.links


def test_cannot_choose_a_locked_title(client_for, member):
    locked = Title.objects.get(slug="leyenda-lev-101")
    response = client_for(member.login).post("/perfil/editar/", form_data(selected_title=locked.pk))
    member.refresh_from_db()
    assert response.status_code == 200 and member.selected_title is None
    ok = Title.objects.get(slug="aprendiz-de-cota")
    client_for(member.login).post("/perfil/editar/", form_data(selected_title=ok.pk))
    member.refresh_from_db()
    assert member.selected_title == ok


def test_a_chosen_title_shows_in_the_sheet(client_for, member):
    game.award(member, "x:1", "manual", 600)
    member.selected_title = Title.objects.get(slug="dibujante-de-grilla")
    member.save()
    assert "Dibujante de Grilla" in client_for(member.login).get("/perfil/").content.decode()


def test_class_change_updates_the_avatar_class(client_for, member):
    client = client_for(member.login)
    client.post("/perfil/avatar/", {"class": "pilot"})
    client.post("/perfil/editar/", form_data(character_class="cartographer"))
    member.refresh_from_db()
    assert member.avatar_config["class"] == "cartographer"


def test_completing_the_sheet_earns_hoja_completa_once(client_for, member):
    client = client_for(member.login)
    client.post("/perfil/avatar/", {"class": "architect"})
    assert "hoja-completa" not in game.unlocked_badges(member)
    client.post("/perfil/editar/", form_data())
    assert "hoja-completa" in game.unlocked_badges(member)
    client.post("/perfil/editar/", form_data(headline="Otra"))
    assert member.xp_events.filter(kind="profile_completed").count() == 1


# --- lectura ----------------------------------------------------------------------------------------------------


def test_sheet_views_and_default_view(client_for, member):
    client = client_for(member.login)
    game_html = client.get("/perfil/").content.decode()
    assert "Vitrina de insignias" in game_html and "NV 1" in game_html
    pro = client.get("/perfil/?vista=pro").content.decode()
    assert "Vitrina de insignias" not in pro and "Habilidades por vendor" in pro
    member.show_game_view = False
    member.save()
    assert "Vitrina de insignias" not in client.get("/perfil/").content.decode()


def test_anyone_approved_can_open_a_teammates_sheet_but_not_pending(
    client_for, member, make_person
):
    other = make_person("otra@lev.cl")
    assert client_for(member.login).get(f"/personas/{other.pk}/").status_code == 200
    pending = make_person("nuevo@lev.cl", status="pending")
    assert client_for(member.login).get(f"/personas/{pending.pk}/").status_code == 404
    assert client_for(member.login).get("/personas/99999/").status_code == 404


def test_other_people_cannot_edit_from_their_sheet(client_for, member, make_person):
    other = make_person("otra@lev.cl")
    html = client_for(member.login).get(f"/personas/{other.pk}/").content.decode()
    assert "Editar mi hoja" not in html


def test_attributes_match_verified_credentials_only(member, lead):
    assert all(a["value"] == 0 for a in sheet.attributes(member, member))
    pending = make_cred(member)
    pending.skills.set(Skill.objects.filter(slug="nubes-de-puntos"))
    assert next(a for a in sheet.attributes(member, member) if a["code"] == "CAP")["value"] == 0
    creds.verify(pending, lead)
    assert next(a for a in sheet.attributes(member, member) if a["code"] == "CAP")["value"] == 2
    verified(member, lead, skills=["lidar", "gnss"], title="Otro")
    assert next(a for a in sheet.attributes(member, member) if a["code"] == "CAP")["value"] == 4
    creds.reject(pending, lead, "no")
    assert next(a for a in sheet.attributes(member, member) if a["code"] == "CAP")["value"] == 2


def test_attributes_use_the_resource_skills_and_cap_at_20(member, lead):
    resource = Resource.objects.get(title="Learn Forma Site Design in 90 minutes")
    resource.skills.set(Skill.objects.filter(slug="modelado-bim"))
    verified(member, lead, resource=resource)
    assert next(a for a in sheet.attributes(member, member) if a["code"] == "MOD")["value"] == 2
    for i in range(11):
        verified(member, lead, skills=["familias"], title=f"c{i}")
    assert next(a for a in sheet.attributes(member, member) if a["code"] == "MOD")["value"] == 20


def test_accepted_answers_raise_collaboration(member):
    for i in range(7):
        game.award(member, f"answer:{i}", "accepted_answer")
    assert next(a for a in sheet.attributes(member, member) if a["code"] == "COL")["value"] == 2


def test_private_credentials_are_hidden_from_teammates(client_for, member, lead, make_person):
    other = make_person("otra@lev.cl")
    verified(other, lead, skills=["lidar"], title="Secreto", visibility="private")
    verified(other, lead, skills=["gnss"], title="Publico", visibility="team")
    html = client_for(member.login).get(f"/personas/{other.pk}/").content.decode()
    assert "Publico" in html and "Secreto" not in html
    assert "LiDAR" not in html and "GNSS" in html
    own = client_for(other.login).get("/perfil/").content.decode()
    assert "Secreto" in own
    assert "Secreto" in client_for(lead.login).get(f"/personas/{other.pk}/").content.decode()
    assert next(a for a in sheet.attributes(other, member) if a["code"] == "CAP")["value"] == 2
    assert next(a for a in sheet.attributes(other, other) if a["code"] == "CAP")["value"] == 4


def test_timeline_hides_private_credential_events(member, lead, make_person):
    other = make_person("otra@lev.cl")
    verified(other, lead, title="Secreto", visibility="private")
    assert not [e for e in sheet.timeline(other, member) if e["detail"] == "Secreto"]
    assert [e for e in sheet.timeline(other, other) if e["detail"] == "Secreto"]


def test_showcase_lists_earned_first_and_hints_for_locked(member, lead):
    verified(member, lead)
    rows = sheet.showcase(member)
    assert rows[0]["earned"] and rows[0]["badge"].slug == "primer-trofeo"
    assert any(not r["earned"] and r["badge"].description for r in rows)


def test_hexagon_uses_dot_decimals(member):
    geo = sheet.hexagon(sheet.attributes(member, member))
    assert "," in geo["values"] and all(
        part.replace(".", "").replace("-", "").isdigit()
        for pair in geo["values"].split()
        for part in pair.split(",")
    )
    assert len(geo["rings"]) == 4 and len(geo["labels"]) == 6


def test_directory_is_alphabetical_with_cards(client_for, member, make_person):
    make_person("zeta@lev.cl")
    html = client_for(member.login).get("/personas/").content.decode()
    assert "El gremio" in html and html.index("ana") < html.index("zeta")
    pending = make_person("nuevo@lev.cl", status="pending")
    assert pending.name not in html


def test_directory_query_count_does_not_grow_with_people(
    client_for, member, make_person, django_assert_num_queries
):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    client = client_for(member.login)

    def count():
        with CaptureQueriesContext(connection) as ctx:
            assert client.get("/personas/").status_code == 200
        return len(ctx)

    for i in range(2):
        make_person(f"a{i}@lev.cl")
    few = count()
    for i in range(12):
        make_person(f"b{i}@lev.cl")
    assert count() <= few


def test_header_links_to_my_sheet_and_gremio(member_client):
    html = member_client.get("/").content.decode()
    assert 'href="/perfil/"' in html and 'href="/personas/"' in html


def test_sheet_page_is_small_on_queries(client_for, member, lead, django_assert_max_num_queries):
    verified(member, lead, skills=["lidar"])
    with django_assert_max_num_queries(45):
        assert client_for(member.login).get("/perfil/").status_code == 200
