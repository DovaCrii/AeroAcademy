import hashlib
import os
from datetime import date, timedelta
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client

from apps.catalog.models import Resource
from apps.credentials import files, services
from apps.credentials.models import Credential
from apps.paths.models import ExternalCourse, LearningPath, Milestone
from apps.progress import services as progress
from apps.progress.models import MilestoneCheck

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF\n" + b"x" * 200
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
FORMA, BENTLEY = "forma-revit", "bentley-learn"
COURSE_90 = "Learn Forma Site Design in 90 minutes"


@pytest.fixture(autouse=True)
def private_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    call_command("seed_catalog", verbosity=0)


def upload(name="certificado.pdf", data=PDF):
    return SimpleUploadedFile(name, data, content_type="application/octet-stream")


def make(owner, **extra):
    data = {"title": "Curso de prueba", "kind": "completion", "visibility": "team", **extra}
    return services.create_credential(owner, data, upload())


def resource(title=COURSE_90):
    return Resource.objects.get(title=title)


def post_form(client, **extra):
    data = {
        "title": "Autodesk Certified User: Revit", "issuer": "Autodesk", "kind": "certification",
        "visibility": "team", "issued_on": "2026-06-14", "file": upload(),
    }  # fmt: skip
    return client.post("/certificados/nueva/", {**data, **extra})


# --- archivos ----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("head", "kind"),
    [
        (PDF, "pdf"),
        (PNG, "png"),
        (JPG, "jpg"),
        (b"MZ\x90\x00", None),
        (b"", None),
        (b"<html>", None),
    ],
)
def test_detect_type_uses_the_real_signature(head, kind):
    assert files.detect_type(head) == kind


def test_validate_accepts_pdf_png_and_jpg_and_returns_the_hash():
    for name, data, kind in (
        ("a.pdf", PDF, "pdf"),
        ("a.png", PNG, "png"),
        ("a.jpg", JPG, "jpg"),
        ("a.JPEG", JPG, "jpg"),
    ):
        got_kind, digest = files.validate_upload(upload(name, data))
        assert got_kind == kind and digest == hashlib.sha256(data).hexdigest()


def test_an_exe_renamed_to_pdf_is_rejected():
    with pytest.raises(ValidationError, match="no es un PDF"):
        files.validate_upload(upload("certificado.pdf", b"MZ\x90\x00\x03" + b"\x00" * 100))


@pytest.mark.parametrize(
    ("name", "data"), [("a.pdf", PNG), ("a.png", PDF), ("a.png", JPG), ("a.pdf", JPG)]
)
def test_extension_must_match_the_content(name, data):
    with pytest.raises(ValidationError, match="no coincide"):
        files.validate_upload(upload(name, data))


@pytest.mark.parametrize("name", ["a.exe", "a.svg", "a.html", "a", "a.pdf.exe", "a.gif"])
def test_other_extensions_are_rejected(name):
    with pytest.raises(ValidationError, match="Solo se aceptan"):
        files.validate_upload(upload(name, PDF))


def test_size_limits():
    with pytest.raises(ValidationError, match="10 MB"):
        files.validate_upload(upload("a.pdf", PDF + b"0" * (files.MAX_BYTES)))
    with pytest.raises(ValidationError, match="vacío"):
        files.validate_upload(upload("a.pdf", b""))


def test_stored_names_are_generated_never_the_users(member):
    cred = services.create_credential(
        member,
        {"title": "x", "kind": "completion", "visibility": "team"},
        upload("../../etc/passwd.pdf"),
    )
    name = cred.file.name
    assert name.startswith(f"credentials/{member.pk}/") and name.endswith(".pdf")
    assert "passwd" not in name and ".." not in name
    assert Path(cred.file.path).is_file()


def test_each_upload_gets_a_different_name(member):
    assert make(member).file.name != make(member).file.name


def test_files_have_no_public_url(member):
    with pytest.raises(ValueError, match="URL pública"):
        _ = make(member).file.url


def test_media_is_not_served_as_static(member_client, member):
    cred = make(member)
    assert member_client.get(f"/media/{cred.file.name}").status_code == 404
    assert member_client.get(f"/static/{cred.file.name}").status_code == 404


# --- modelo --------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("days", "soon", "expired"),
    [
        (None, False, False),
        (200, False, False),
        (61, False, False),
        (60, True, False),
        (0, True, False),
        (-1, False, True),
    ],
)
def test_expiry_properties(member, days, soon, expired):
    cred = make(member, expires_on=None if days is None else date.today() + timedelta(days=days))
    assert cred.expires_soon is soon and cred.is_expired is expired
    assert cred.days_to_expiry == days


def test_hash_kind_and_status_are_stored(member):
    cred = make(member)
    assert cred.file_sha256 == hashlib.sha256(PDF).hexdigest() and cred.file_kind == "pdf"
    assert cred.status == "pending" and cred.reviewed_by is None


# --- alta por formulario ---------------------------------------------------------------------------------------------


def test_member_creates_a_pending_credential(client_for, member):
    response = post_form(
        client_for(member.login), credential_id="ABC-1", verify_url="https://verify.test/x"
    )
    cred = Credential.objects.get(owner=member)
    assert response.status_code == 302 and response.url == f"/certificados/{cred.pk}/"
    assert (
        cred.status == "pending" and cred.credential_id == "ABC-1" and cred.kind == "certification"
    )
    assert Path(cred.file.path).is_file()


def test_form_rejects_a_bad_file_and_creates_nothing(client_for, member):
    response = post_form(
        client_for(member.login), file=upload("certificado.pdf", b"MZ\x90\x00" * 20)
    )
    assert response.status_code == 200 and "no es un PDF" in response.content.decode()
    assert not Credential.objects.exists()


def test_form_requires_a_file_and_a_title(client_for, member):
    response = client_for(member.login).post(
        "/certificados/nueva/", {"kind": "completion", "visibility": "team"}
    )
    html = response.content.decode()
    assert response.status_code == 200 and html.count("Este campo es obligatorio") >= 2
    assert not Credential.objects.exists()


def test_expiry_cannot_precede_issue_date(client_for, member):
    response = post_form(client_for(member.login), issued_on="2026-06-14", expires_on="2025-01-01")
    assert "no puede ser anterior" in response.content.decode()
    assert not Credential.objects.exists()


def test_my_credentials_page_counts_states(client_for, member, lead):
    make(member, title="A")
    verified = make(member, title="B")
    services.verify(verified, lead)
    rejected = make(member, title="C")
    services.reject(rejected, lead, "borroso")
    html = client_for(member.login).get("/certificados/").content.decode()
    for title in ("A", "B", "C"):
        assert f">{title}</a>" in html
    assert (
        "borroso" in html and "Verificada" in html and "En revisión" in html and "Rechazada" in html
    )


def test_csrf_is_enforced_on_upload(member):
    client = Client(
        enforce_csrf_checks=True, REMOTE_ADDR="127.0.0.1", HTTP_TAILSCALE_USER_LOGIN=member.login
    )
    assert client.post("/certificados/nueva/", {"title": "x", "file": upload()}).status_code == 403


# --- permisos de archivos y vistas ----------------------------------------------------------------------------------------


def test_member_cannot_download_someone_elses_file(client_for, member, make_person, lead):
    other = make_person("otra@lev.cl")
    cred = make(other)
    services.verify(cred, lead)  # verificada y del equipo: el listado es visible, el archivo no
    assert client_for(member.login).get(f"/certificados/{cred.pk}/archivo/").status_code == 403


def test_owner_lead_and_admin_can_download(client_for, member, lead, admin_person):
    cred = make(member)
    for person in (member, lead, admin_person):
        response = client_for(person.login).get(f"/certificados/{cred.pk}/archivo/")
        assert response.status_code == 200, person.login
        assert b"".join(response.streaming_content) == PDF


def test_download_headers(client_for, member):
    cred = make(member)
    response = client_for(member.login).get(f"/certificados/{cred.pk}/archivo/")
    assert response["Content-Type"] == "application/pdf"
    assert response["Content-Disposition"] == f'attachment; filename="credencial-{cred.pk}.pdf"'
    assert (
        response["X-Content-Type-Options"] == "nosniff" and "no-store" in response["Cache-Control"]
    )


def test_private_credentials_are_hidden_from_other_members(client_for, member, make_person, lead):
    owner = make_person("otra@lev.cl")
    cred = make(owner, visibility="private")
    services.verify(cred, lead)
    assert client_for(member.login).get(f"/certificados/{cred.pk}/").status_code == 404
    assert client_for(member.login).get(f"/certificados/{cred.pk}/archivo/").status_code == 404
    assert client_for(lead.login).get(f"/certificados/{cred.pk}/").status_code == 200


def test_pending_credentials_of_others_are_not_visible_to_members(client_for, member, make_person):
    cred = make(make_person("otra@lev.cl"))
    assert client_for(member.login).get(f"/certificados/{cred.pk}/").status_code == 404


def test_verified_team_credential_detail_is_visible_but_without_download(
    client_for, member, make_person, lead
):
    cred = make(make_person("otra@lev.cl"))
    services.verify(cred, lead)
    html = client_for(member.login).get(f"/certificados/{cred.pk}/").content.decode()
    assert (
        "Curso de prueba" in html and "Descargar archivo" not in html and "datos personales" in html
    )


def test_only_the_owner_can_edit_or_delete(client_for, member, make_person, lead):
    cred = make(member)
    other = make_person("otra@lev.cl")
    for person in (other, lead):
        client = client_for(person.login)
        assert client.get(f"/certificados/{cred.pk}/editar/").status_code in {403, 404}
        assert client.post(f"/certificados/{cred.pk}/eliminar/").status_code in {403, 404}
    assert Credential.objects.filter(pk=cred.pk).exists()


def test_pending_people_cannot_use_credentials(client_for, make_person):
    pending = make_person("p@lev.cl", status="pending")
    assert client_for(pending.login).get("/certificados/").status_code == 302
    assert post_form(client_for(pending.login)).status_code == 302
    assert not Credential.objects.exists()


# --- lista del equipo --------------------------------------------------------------------------------------------------


def test_team_list_shows_only_verified_team_credentials(client_for, member, make_person, lead):
    ana = make_person("ana2@lev.cl")
    shown = make(ana, title="Visible")
    services.verify(shown, lead)
    services.verify(make(ana, title="Privada", visibility="private"), lead)
    make(ana, title="Pendiente")
    services.reject(make(ana, title="Rechazada"), lead, "no se lee")
    html = client_for(member.login).get("/certificados/equipo/").content.decode()
    assert "Visible" in html
    for hidden in ("Privada", "Pendiente", "Rechazada"):
        assert hidden not in html
    assert "/archivo/" not in html  # el listado no abre archivos


def test_team_list_filters(client_for, member, make_person, lead):
    ana, luis = make_person("ana2@lev.cl"), make_person("luis2@lev.cl")
    a = make(ana, title="Revit básico", kind="completion", issuer="Autodesk")
    b = make(
        luis,
        title="Habilitación RPA",
        kind="license",
        issuer="DGAC",
        expires_on=date.today() + timedelta(days=20),
    )
    for c in (a, b):
        services.verify(c, lead)
    client = client_for(member.login)
    assert (
        "Habilitación RPA"
        not in client.get("/certificados/equipo/?tipo=completion").content.decode()
    )
    assert "Revit básico" not in client.get("/certificados/equipo/?vencen=1").content.decode()
    assert "Habilitación RPA" in client.get("/certificados/equipo/?vencen=1").content.decode()
    assert "Revit básico" in client.get("/certificados/equipo/?q=autodesk").content.decode()


# --- revisión -----------------------------------------------------------------------------------------------------------


def test_review_queue_is_for_leads_and_oldest_first(client_for, member, lead, make_person):
    first = make(member, title="Primera")
    second = make(make_person("otra@lev.cl"), title="Segunda")
    assert client_for(member.login).get("/certificados/revisar/").status_code == 403
    html = client_for(lead.login).get("/certificados/revisar/").content.decode()
    assert html.index("Primera") < html.index("Segunda")
    services.verify(first, lead)
    assert "Primera" not in client_for(lead.login).get("/certificados/revisar/").content.decode()
    assert second.status == "pending"


def test_member_cannot_review(client_for, member):
    cred = make(member)
    response = client_for(member.login).post(
        f"/certificados/{cred.pk}/revisar/", {"action": "verify"}
    )
    assert response.status_code == 403
    cred.refresh_from_db()
    assert cred.status == "pending"


def test_lead_verifies_and_it_is_recorded(client_for, member, lead):
    cred = make(member)
    client_for(lead.login).post(
        f"/certificados/{cred.pk}/revisar/", {"action": "verify", "comment": "Todo en orden"}
    )
    cred.refresh_from_db()
    assert cred.status == "verified" and cred.reviewed_by == lead and cred.reviewed_at
    assert cred.review_comment == "Todo en orden"


def test_rejecting_requires_a_comment(client_for, member, lead):
    cred = make(member)
    response = client_for(lead.login).post(
        f"/certificados/{cred.pk}/revisar/", {"action": "reject", "comment": "  "}, follow=True
    )
    cred.refresh_from_db()
    assert cred.status == "pending" and "explicar el motivo" in response.content.decode()
    client_for(lead.login).post(
        f"/certificados/{cred.pk}/revisar/", {"action": "reject", "comment": "Está borroso"}
    )
    cred.refresh_from_db()
    assert cred.status == "rejected" and cred.review_comment == "Está borroso"


def test_service_level_permissions(member, lead):
    cred = make(member)
    with pytest.raises(PermissionError):
        services.verify(cred, member)
    with pytest.raises(PermissionError):
        services.reject(cred, member, "x")
    with pytest.raises(ValueError):
        services.reject(cred, lead, "")


# --- reglas de edición (vuelve a pending) ------------------------------------------------------------------------------------------


def edit(client, cred, **extra):
    data = {
        "title": cred.title,
        "issuer": cred.issuer,
        "kind": cred.kind,
        "visibility": cred.visibility,
        **extra,
    }
    return client.post(f"/certificados/{cred.pk}/editar/", data)


@pytest.mark.parametrize(
    "change", [{"issuer": "Otro emisor"}, {"issued_on": "2026-01-01"}, {"expires_on": "2030-01-01"}]
)
def test_editing_review_fields_of_a_verified_credential_sends_it_back(
    client_for, member, lead, change
):
    cred = make(member, issuer="Autodesk", issued_on=date(2026, 5, 1))
    services.verify(cred, lead)
    edit(
        client_for(member.login),
        cred,
        **{"issuer": "Autodesk", "issued_on": "2026-05-01", **change},
    )
    cred.refresh_from_db()
    assert cred.status == "pending" and cred.reviewed_by is None and cred.review_comment == ""


def test_replacing_the_file_sends_it_back_and_removes_the_old_one(
    client_for, member, lead, django_capture_on_commit_callbacks
):
    cred = make(member)
    services.verify(cred, lead)
    old = Path(cred.file.path)
    with django_capture_on_commit_callbacks(execute=True):
        edit(client_for(member.login), cred, file=upload("nuevo.png", PNG))
    cred.refresh_from_db()
    assert cred.status == "pending" and cred.file_kind == "png" and cred.file.name.endswith(".png")
    assert Path(cred.file.path).is_file() and not old.exists()


def test_editing_other_fields_keeps_the_credential_verified(client_for, member, lead):
    cred = make(member, issuer="Autodesk")
    services.verify(cred, lead)
    edit(
        client_for(member.login),
        cred,
        title="Nuevo título",
        issuer="Autodesk",
        visibility="private",
    )
    cred.refresh_from_db()
    assert (
        cred.status == "verified" and cred.title == "Nuevo título" and cred.visibility == "private"
    )


def test_editing_a_rejected_credential_resubmits_it(client_for, member, lead):
    cred = make(member, issuer="Autodesk")
    services.reject(cred, lead, "borroso")
    edit(client_for(member.login), cred, issuer="Autodesk", file=upload("a.pdf", PDF))
    cred.refresh_from_db()
    assert cred.status == "pending" and cred.review_comment == ""


def test_edit_form_prefills_and_file_is_optional(client_for, member):
    cred = make(member, title="Mi título", issuer="Emisor")
    html = client_for(member.login).get(f"/certificados/{cred.pk}/editar/").content.decode()
    assert 'value="Mi título"' in html and "Reemplazar archivo (opcional)" in html


def test_deleting_removes_the_file_and_the_marks(
    client_for, member, lead, django_capture_on_commit_callbacks
):
    cred = make(member, resource=resource())
    services.verify(cred, lead)
    path = Path(cred.file.path)
    assert MilestoneCheck.objects.filter(person=member, source="credential").exists()
    with django_capture_on_commit_callbacks(execute=True):
        client_for(member.login).post(f"/certificados/{cred.pk}/eliminar/")
    assert not Credential.objects.exists() and not path.exists()
    assert not MilestoneCheck.objects.filter(person=member).exists()


# --- efecto sobre el avance --------------------------------------------------------------------------------------------------------


def checks(person):
    return set(
        MilestoneCheck.objects.filter(person=person, source="credential").values_list(
            "milestone__key", flat=True
        )
    )


def test_verifying_forma_site_design_marks_its_milestone(member, lead):
    cred = make(member, resource=resource(), path=LearningPath.objects.get(slug=FORMA))
    assert checks(member) == set()  # en revisión no cuenta
    services.verify(cred, lead)
    assert checks(member) == {"n2-t5"}
    check = MilestoneCheck.objects.get(person=member, milestone__key="n2-t5")
    assert check.credential == cred and check.source == "credential"


def test_the_marked_milestone_shows_in_the_path_and_changes_the_percentage(member, lead):
    path = LearningPath.objects.get(slug=FORMA)
    before = progress.world_context(member, path)["stats"]["pct"]
    services.verify(make(member, resource=resource()), lead)
    after = progress.world_context(member, path)
    n2 = next(c for c in after["chapters"] if c["level"].code == "n2")
    assert n2["done"] == 1 and after["stats"]["pct"] > before


def test_marks_disappear_when_the_credential_stops_being_verified(member, lead):
    cred = make(member, resource=resource())
    services.verify(cred, lead)
    services.reject(cred, lead, "se anuló")
    assert checks(member) == set()
    services.verify(cred, lead)
    assert checks(member) == {"n2-t5"}
    services.update_credential(cred, {"issuer": "Cambiado"})
    cred.refresh_from_db()
    assert cred.status == "pending" and checks(member) == set()


def test_a_credential_milestone_cannot_be_unchecked_by_hand(client_for, member, lead):
    services.verify(make(member, resource=resource()), lead)
    milestone = Milestone.objects.get(path__slug=FORMA, key="n2-t5")
    assert progress.set_milestone(member, milestone, False) is False
    client_for(member.login).post(f"/rutas/{FORMA}/hitos/n2-t5/", {"checked": "0"})
    assert MilestoneCheck.objects.filter(person=member, milestone=milestone).exists()


def test_a_manual_check_is_not_taken_over_by_the_credential(member, lead):
    milestone = Milestone.objects.get(path__slug=FORMA, key="n2-t5")
    progress.set_milestone(member, milestone, True)
    cred = make(member, resource=resource())
    services.verify(cred, lead)
    services.reject(cred, lead, "x")
    assert MilestoneCheck.objects.filter(
        person=member, milestone=milestone, source="manual"
    ).exists()


def test_verifying_is_personal(member, lead, make_person):
    other = make_person("otra@lev.cl")
    services.verify(make(member, resource=resource()), lead)
    assert checks(other) == set()


def test_credentials_without_a_resource_do_not_mark_anything(member, lead):
    services.verify(make(member), lead)
    assert not MilestoneCheck.objects.exists()


# --- rutas externas: registrar curso + certificado ------------------------------------------------------------------------------


def test_register_course_form_lists_the_courses_of_the_path(client_for, member):
    html = (
        client_for(member.login).get(f"/rutas/{BENTLEY}/registrar/?curso=ord-c0").content.decode()
    )
    assert "Bentley Accredited Road Modeler: OpenRoads Modeling Core Skills" in html
    assert "Otro curso que no está en la lista" in html
    assert '<option value="ord-c0" selected>' in html


def test_register_a_listed_course(client_for, member):
    response = client_for(member.login).post(
        f"/rutas/{BENTLEY}/registrar/",
        {"course": "ord-c0", "completed_on": "2026-10-01", "visibility": "team", "file": upload()},
    )
    cred = Credential.objects.get(owner=member)
    assert response.status_code == 302
    assert (
        cred.status == "pending" and cred.kind == "certification"
    )  # una reliquia es una certificación
    assert cred.resource.title.startswith("Bentley Accredited Road Modeler")
    assert (
        cred.path.slug == BENTLEY
        and cred.platform.slug == "bentley-learn"
        and cred.issued_on == date(2026, 10, 1)
    )


def test_register_a_free_course(client_for, member):
    client_for(member.login).post(
        f"/rutas/{BENTLEY}/registrar/",
        {"course": "__free__", "course_name_free": "STAAD Advanced", "course_url_free": "https://learning.bentley.com/x",
         "visibility": "team", "file": upload()},
    )  # fmt: skip
    cred = Credential.objects.get(owner=member)
    assert (
        cred.resource is None
        and cred.course_name_free == "STAAD Advanced"
        and cred.title == "STAAD Advanced"
    )
    assert cred.kind == "completion"


def test_free_course_needs_a_name(client_for, member):
    response = client_for(member.login).post(
        f"/rutas/{BENTLEY}/registrar/",
        {"course": "__free__", "visibility": "team", "file": upload()},
    )
    assert (
        "Escribe el nombre del curso" in response.content.decode()
        and not Credential.objects.exists()
    )


def test_register_rejects_bad_files_and_unknown_courses(client_for, member):
    client = client_for(member.login)
    bad = client.post(
        f"/rutas/{BENTLEY}/registrar/",
        {"course": "ord-c0", "visibility": "team", "file": upload("a.pdf", b"MZ" * 40)},
    )
    unknown = client.post(
        f"/rutas/{BENTLEY}/registrar/",
        {"course": "no-existe", "visibility": "team", "file": upload()},
    )
    assert bad.status_code == 200 and unknown.status_code == 200 and not Credential.objects.exists()


def test_register_only_for_external_tracks(member_client):
    assert member_client.get(f"/rutas/{FORMA}/registrar/").status_code == 404
    assert member_client.get("/rutas/no-existe/registrar/").status_code == 404


def test_register_requires_free_courses_to_be_allowed(client_for, member):
    LearningPath.objects.filter(slug=BENTLEY).update(allow_free_courses=False)
    html = client_for(member.login).get(f"/rutas/{BENTLEY}/registrar/").content.decode()
    assert "Otro curso que no está en la lista" not in html


# --- promover un curso libre ---------------------------------------------------------------------------------------------------------


def free_credential(owner, name="STAAD Advanced"):
    path = LearningPath.objects.get(slug=BENTLEY)
    return services.create_credential(
        owner,
        {"title": name, "course_name_free": name, "course_url_free": "https://learning.bentley.com/staad",
         "kind": "completion", "visibility": "team", "path": path, "platform": path.platform},
        upload(),
    )  # fmt: skip


def verified_free(owner, lead, name="STAAD Advanced"):
    cred = free_credential(owner, name)
    services.verify(cred, lead)
    return cred


def test_lead_promotes_a_free_course_to_the_catalog(client_for, member, lead):
    cred = free_credential(member)
    services.verify(cred, lead)
    client_for(lead.login).post(f"/certificados/{cred.pk}/promover/")
    cred.refresh_from_db()
    course = ExternalCourse.objects.get(path__slug=BENTLEY, key="lib-c0")
    assert (
        cred.resource == course.resource and course.level.code == "lib" and not course.is_required
    )
    assert course.resource.title == "STAAD Advanced" and course.resource.proposed_by == member
    assert course.resource.grants_completion_certificate and course.reward == "trophy"


def test_promoted_courses_get_consecutive_keys(member, lead, make_person):
    services.promote_free_course(verified_free(member, lead, "Curso A"), lead)
    services.promote_free_course(verified_free(make_person("otra@lev.cl"), lead, "Curso B"), lead)
    keys = ExternalCourse.objects.filter(path__slug=BENTLEY, key__startswith="lib-c").values_list(
        "key", flat=True
    )
    assert set(keys) == {"lib-c0", "lib-c1"}


def test_promoting_twice_or_a_listed_course_fails(member, lead):
    cred = verified_free(member, lead)
    services.promote_free_course(cred, lead)
    with pytest.raises(ValueError, match="no es un curso libre"):
        services.promote_free_course(cred, lead)
    with pytest.raises(ValueError):
        services.promote_free_course(make(member, resource=resource()), lead)


def test_members_cannot_promote(client_for, member):
    cred = free_credential(member)
    assert client_for(member.login).post(f"/certificados/{cred.pk}/promover/").status_code == 403
    with pytest.raises(PermissionError):
        services.promote_free_course(cred, member)


def test_promoting_needs_a_path_that_allows_it(member, lead):
    cred = verified_free(member, lead)
    LearningPath.objects.filter(slug=BENTLEY).update(allow_free_courses=False)
    cred.refresh_from_db()
    with pytest.raises(ValueError, match="no admite"):
        services.promote_free_course(cred, lead)


def test_a_verified_promoted_course_counts_for_the_person(member, lead):
    cred = free_credential(member)
    services.verify(cred, lead)
    services.promote_free_course(cred, lead)
    states = services.states_by_resource(member)
    assert states[cred.resource_id][0] == "verified"


# --- mundo Civil: la Ruta Bentley --------------------------------------------------------------------------------------------------------


def civil(client, query=""):
    response = client.get(f"/rutas/{BENTLEY}/{query}")
    assert response.status_code == 200
    return response.content.decode()


def verified_course(person, lead, title):
    cred = make(person, resource=resource(title), path=LearningPath.objects.get(slug=BENTLEY))
    services.verify(cred, lead)
    return cred


ROAD = "Bentley Accredited Road Modeler: OpenRoads Modeling Core Skills"
MS_USER = "Bentley Accredited MicroStation User"


def test_civil_world_renders_all_its_pieces(member_client):
    html = civil(member_client)
    assert "cv-cover" in html and 'data-scene="terrain"' in html and "civil.css" in html
    assert "PLANTA · eje del corredor" in html and "PERFIL LONGITUDINAL" in html
    assert html.count('class="cv-cor') == 5  # Explorer · Corridors
    assert html.count("cv-stake ") == 8 and html.count("cv-pier ") == 8
    assert "Explorer · Corridors" in html and "km 0+000" in html


def test_civil_cover_readouts_are_real_numbers(member_client):
    readouts = civil(member_client).split('class="lv-readouts"')[1].split("</div>")[0]
    for label, value in (
        ("Corredores", "5"),
        ("Cursos", "8"),
        ("Estacas verificadas", "0"),
        ("En revisión", "0"),
        ("Pilares", "0/8"),
    ):
        assert f"{label}<b>{value}</b>" in readouts


def test_unregistered_courses_offer_to_register_them(member_client):
    html = civil(member_client, "?nivel=ord")
    assert html.count("Registrar</a>") >= 2 and f"/rutas/{BENTLEY}/registrar/?curso=ord-c0" in html


def test_a_pending_course_shows_in_review_and_a_verified_one_shows_verified(
    client_for, member, lead
):
    make(member, resource=resource(ROAD), path=LearningPath.objects.get(slug=BENTLEY))
    client = client_for(member.login)
    assert "⧗ En revisión" in civil(client, "?nivel=ord")
    assert "En revisión<b>1</b>" in civil(client)
    services.verify(Credential.objects.get(owner=member), lead)
    html = civil(client, "?nivel=ord")
    assert (
        "✔ Verificado" in html
        and "Ver certificado" in html
        and "Estacas verificadas<b>1</b>" in html
    )


def test_the_road_is_paved_up_to_the_last_verified_stake(client_for, member, lead):
    client = client_for(member.login)
    assert 'class="cv-road"' not in civil(client)
    verified_course(member, lead, MS_USER)
    assert 'class="cv-road"' in civil(client)


def test_relics_raise_the_piers_of_the_bridge(client_for, member, lead):
    verified_course(member, lead, MS_USER)
    html = civil(client_for(member.login))
    assert html.count("cv-pier verified") == 1 and "Pilares<b>1/8</b>" in html


def test_a_rejected_course_can_be_registered_again(client_for, member, lead):
    cred = make(member, resource=resource(ROAD), path=LearningPath.objects.get(slug=BENTLEY))
    services.reject(cred, lead, "ilegible")
    html = civil(client_for(member.login), "?nivel=ord")
    assert "✖ Rechazado" in html and "Registrar de nuevo" in html and "Ver motivo" in html


def test_chapter_percentages_follow_the_required_courses(member, lead):
    from apps.progress import external

    path = LearningPath.objects.get(slug=BENTLEY)
    ctx = external.external_context(member, path)
    ms = next(c for c in ctx["chapters"] if c["level"].code == "ms")
    assert (ms["done"], ms["total"], ms["pct"]) == (
        0,
        1,
        0,
    )  # solo MicroStation User es obligatorio
    verified_course(member, lead, MS_USER)
    ctx = external.external_context(member, path)
    ms = next(c for c in ctx["chapters"] if c["level"].code == "ms")
    assert ms["pct"] == 100 and ms["complete"] and ctx["stats"]["pct"] > 0


def test_any_one_rule_completes_the_chapter_with_a_single_accreditation(member, lead):
    from apps.progress import external

    path = LearningPath.objects.get(slug=BENTLEY)
    verified_course(
        member, lead, "Bentley Accredited BIM Modeler: Basic Mechanical Modeling with OpenBuildings"
    )
    obd = next(
        c for c in external.external_context(member, path)["chapters"] if c["level"].code == "obd"
    )
    assert obd["complete"] and obd["pct"] == 100 and obd["total"] == 1


def test_the_free_courses_chapter_does_not_count_for_the_percentage(member):
    from apps.progress import external

    ctx = external.external_context(member, LearningPath.objects.get(slug=BENTLEY))
    lib = next(c for c in ctx["chapters"] if c["level"].code == "lib")
    assert lib["total"] == 0 and not lib["complete"]


def test_my_free_courses_appear_in_the_free_chapter_and_the_button_is_offered(client_for, member):
    free_credential(member)
    html = civil(client_for(member.login), "?nivel=lib")
    assert "STAAD Advanced" in html and "Registrar un curso libre" in html


def test_free_courses_of_others_are_not_listed_to_me(client_for, member, make_person):
    free_credential(make_person("otra@lev.cl"))
    assert "STAAD Advanced" not in civil(client_for(member.login), "?nivel=lib")


def test_a_promoted_course_appears_for_everyone_in_the_free_chapter(
    client_for, member, lead, make_person
):
    services.promote_free_course(verified_free(make_person("otra@lev.cl"), lead), lead)
    html = civil(client_for(member.login), "?nivel=lib")
    assert "STAAD Advanced" in html and "Trofeo" in html


def test_unverified_urls_are_flagged_and_text_is_escaped(client_for, member):
    html = civil(client_for(member.login), "?nivel=obr")
    assert "Confirmar enlace" in html
    Resource.objects.filter(title="Navigating Bentley Learn").update(
        description="<script>alert(1)</script>"
    )
    assert "<script>alert(1)</script>" not in civil(client_for(member.login), "?nivel=ms")


def test_participants_count_people_with_verified_credentials(client_for, member, lead, make_person):
    verified_course(make_person("ana3@lev.cl"), lead, MS_USER)
    verified_course(make_person("luis3@lev.cl"), lead, ROAD)
    assert "Equipo<b>2</b>" in civil(client_for(member.login))


def test_the_civil_page_is_hidden_when_unpublished(client_for, member, lead):
    LearningPath.objects.filter(slug=BENTLEY).update(is_published=False)
    assert client_for(member.login).get(f"/rutas/{BENTLEY}/").status_code == 404
    assert client_for(lead.login).get(f"/rutas/{BENTLEY}/").status_code == 200


def test_navigation_and_welcome_link_to_certificates(member_client):
    html = member_client.get("/").content.decode()
    assert 'href="/certificados/"' in html and "Certificados</a>" in html
    assert "En construcción · Bloques 5 y 6" not in html


def test_geometry_helpers_are_deterministic_and_inside_the_canvas():
    from apps.progress import external

    for x in range(40, 961, 20):
        assert 60 < external.axis_y(x) < 160 and 270 < external.ground_y(x) < 400
    assert external.ground_y(750) > external.ground_y(300) + 40  # el valle bajo el puente


def test_svg_coordinates_never_use_a_decimal_comma(client_for, member, lead):
    """Regresión: con el idioma en español, Django escribe 12,5 y rompe el SVG."""
    import re

    verified_course(member, lead, MS_USER)
    verified_course(member, lead, ROAD)
    client = client_for(member.login)
    for url in (f"/rutas/{BENTLEY}/", f"/rutas/{FORMA}/"):
        html = client.get(url).content.decode()
        svg = html[
            html.index('<svg class="cv-svg"')
            if "cv-svg" in html
            else html.index('<svg class="ar-section"') :
        ]
        svg = svg[: svg.index("</svg>")]
        assert not re.findall(r'(?:x|y|cx|cy|width|height|transform)="[^"]*\d,\d', svg), url


# --- endurecimiento tras la revisión del bloque ------------------------------------------------------------------------------------


@pytest.mark.parametrize("target", ["//evil.com", "https://evil.com/x", "javascript:alert(1)", ""])
def test_review_never_redirects_outside_the_site(client_for, member, lead, target):
    cred = make(member)
    response = client_for(lead.login).post(
        f"/certificados/{cred.pk}/revisar/", {"action": "verify", "next": target}
    )
    assert response.status_code == 302 and response["Location"].startswith("/")
    assert not response["Location"].startswith("//")


def test_review_goes_back_to_a_local_next(client_for, member, lead):
    cred = make(member)
    response = client_for(lead.login).post(
        f"/certificados/{cred.pk}/revisar/", {"action": "verify", "next": "/certificados/equipo/"}
    )
    assert response["Location"] == "/certificados/equipo/"


def test_rejecting_one_of_two_verified_credentials_keeps_the_mark(member, lead):
    path = LearningPath.objects.get(slug=FORMA)
    first = make(member, resource=resource(), path=path)
    second = make(member, resource=resource(), path=path)
    services.verify(first, lead)
    services.verify(second, lead)
    services.reject(first, lead, "duplicada")
    assert checks(member) == {"n2-t5"}
    services.reject(second, lead, "tampoco")
    assert checks(member) == set()


def test_a_stale_review_is_refused(member, lead):
    cred = make(member)
    seen = services.version_of(cred)
    services.update_credential(cred, {"issuer": "Otro emisor"})
    with pytest.raises(ValueError, match="cambió"):
        services.verify(cred, lead, version=seen)
    cred.refresh_from_db()
    assert cred.status == "pending"


def test_double_verify_and_double_reject_fail(member, lead):
    cred = make(member)
    services.verify(cred, lead)
    with pytest.raises(ValueError, match="ya está verificada"):
        services.verify(cred, lead)
    services.reject(cred, lead, "motivo")
    with pytest.raises(ValueError, match="ya está rechazada"):
        services.reject(cred, lead, "motivo")


def test_promoting_an_unverified_course_fails(member, lead):
    with pytest.raises(ValueError, match="verificado"):
        services.promote_free_course(free_credential(member), lead)


def test_a_lead_cannot_review_their_own_credential_but_an_admin_can(lead, admin_person):
    mine = make(lead)
    with pytest.raises(PermissionError, match="propias"):
        services.verify(mine, lead)
    admins = make(admin_person)
    services.verify(admins, admin_person)
    assert admins.status == "verified"


def test_deleting_a_person_removes_their_files(member, django_capture_on_commit_callbacks):
    cred = make(member)
    path = Path(cred.file.path)
    assert path.is_file()
    with django_capture_on_commit_callbacks(execute=True):
        member.delete()
    assert not Credential.objects.exists() and not path.exists()


def test_download_with_a_missing_file_is_404(client_for, member):
    cred = make(member)
    os.remove(cred.file.path)
    assert client_for(member.login).get(f"/certificados/{cred.pk}/archivo/").status_code == 404


def test_the_review_comment_is_truncated(client_for, member, lead):
    cred = make(member)
    client_for(lead.login).post(
        f"/certificados/{cred.pk}/revisar/", {"action": "verify", "comment": "x" * 5000}
    )
    cred.refresh_from_db()
    assert len(cred.review_comment) <= 1000


def test_registering_the_same_course_twice_is_blocked(client_for, member):
    data = {"course": "ord-c0", "completed_on": "2026-10-01", "visibility": "team"}
    client_for(member.login).post(f"/rutas/{BENTLEY}/registrar/", {**data, "file": upload()})
    response = client_for(member.login).post(
        f"/rutas/{BENTLEY}/registrar/", {**data, "file": upload()}
    )
    assert response.status_code == 200 and Credential.objects.filter(owner=member).count() == 1


def test_the_form_can_link_a_resource_and_the_review_marks_the_milestone(client_for, member, lead):
    client = client_for(member.login)
    response = post_form(
        client, title="Forma Site Design", resource=resource().pk,
        path=LearningPath.objects.get(slug=FORMA).pk,
    )  # fmt: skip
    assert response.status_code == 302
    cred = Credential.objects.get(owner=member)
    assert cred.resource == resource()
    client_for(lead.login).post(f"/certificados/{cred.pk}/revisar/", {"action": "verify"})
    assert checks(member) == {"n2-t5"}


def test_query_counts_stay_flat(
    client_for, member, lead, make_person, django_assert_max_num_queries
):
    for i in range(6):
        make(make_person(f"p{i}@lev.cl"), title=f"Curso {i}")
    with django_assert_max_num_queries(25):
        assert client_for(lead.login).get("/certificados/equipo/").status_code == 200
    from apps.progress import external

    path = LearningPath.objects.get(slug=BENTLEY)
    with django_assert_max_num_queries(40):
        external.external_context(member, path)
