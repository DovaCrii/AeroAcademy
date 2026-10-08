import os
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command

from apps.catalog.models import Discipline
from apps.library import files, services
from apps.library.models import Document, DocumentVersion

pytestmark = pytest.mark.django_db
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF\n" + b"x" * 200
OLE = b"\xd0\xcf\x11\xe0" + b"\x00" * 64


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    call_command("seed_catalog", verbosity=0)


def up(name="manual.pdf", data=PDF):
    return SimpleUploadedFile(name, data)


def doc(owner, title="Manual de Revit", **kw):
    return services.create_document(owner, title=title, doc_type="manual", upload=up(), **kw)


# --- archivos -------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("a.pdf", PDF),
        ("a.rte", OLE),
        ("a.rfa", OLE),
        ("a.dxf", b"0\nSECTION"),
        ("a.docx", b"PK\x03\x04" + b"0" * 30),
        ("a.CSV", b"a,b"),
    ],
)
def test_allowed_files(name, data):
    ext, digest = files.validate_upload(up(name, data))
    assert ext == name.rsplit(".", 1)[1].lower() and len(digest) == 64


@pytest.mark.parametrize(
    "name", ["a.exe", "a.bat", "a.html", "a.svg", "a.zip", "a.js", "a", "a.pdf.exe", "a.php"]
)
def test_dangerous_extensions_are_rejected(name):
    with pytest.raises(ValidationError, match="no permitido"):
        files.validate_upload(up(name, PDF))


@pytest.mark.parametrize(
    ("name", "data"),
    [("a.pdf", b"MZ\x90\x00 programa"), ("a.rte", PDF), ("a.png", PDF), ("a.docx", b"%PDF-")],
)
def test_content_must_match_the_extension(name, data):
    with pytest.raises(ValidationError, match="no coincide"):
        files.validate_upload(up(name, data))


def test_empty_and_oversized(monkeypatch):
    with pytest.raises(ValidationError, match="vacío"):
        files.validate_upload(up("a.pdf", b""))
    monkeypatch.setattr(files, "MAX_BYTES", 100)
    with pytest.raises(ValidationError, match="50 MB"):
        files.validate_upload(up("a.pdf", PDF))


def test_stored_names_are_generated(member):
    d = services.create_document(
        member, title="x", doc_type="manual", upload=up("../../etc/passwd.pdf")
    )
    name = d.current.file.name
    assert (
        name.startswith(f"library/{d.pk}/")
        and name.endswith(".pdf")
        and "passwd" not in name
        and ".." not in name
    )
    assert Path(d.current.file.path).is_file()


def test_files_have_no_public_url(member):
    with pytest.raises(ValueError):
        _ = doc(member).current.file.url


# --- versiones ---------------------------------------------------------------------------------------------------------


def test_a_new_version_becomes_the_only_current_and_history_is_kept(member):
    d = doc(member)
    v2 = services.upload_version(
        d, member, up("b.pdf", PDF + b"2"), label="v2", notes="Corrige la sección 3"
    )
    versions = list(d.versions.order_by("id"))
    assert [v.is_current for v in versions] == [False, True] and v2.notes == "Corrige la sección 3"
    assert d.versions.filter(is_current=True).count() == 1 and len(versions) == 2
    assert all(Path(v.file.path).is_file() for v in versions)


def test_auto_labels_and_duplicate_labels(member):
    d = doc(member)
    assert d.current.version_label == "v1"
    assert services.upload_version(d, member, up()).version_label == "v2"
    with pytest.raises(ValueError, match="Ya existe"):
        services.upload_version(d, member, up(), label="v1")


def test_invalid_version_upload_changes_nothing(member):
    d = doc(member)
    with pytest.raises(ValidationError):
        services.upload_version(d, member, up("x.exe", b"MZ"))
    assert d.versions.count() == 1 and d.current.version_label == "v1"


def test_make_an_old_version_current(member):
    d = doc(member)
    first = d.current
    services.upload_version(d, member, up("b.pdf", PDF + b"2"))
    services.make_current(first, member)
    assert list(d.versions.filter(is_current=True)) == [first]


def test_database_allows_only_one_current(member):
    d = doc(member)
    from django.db import IntegrityError, transaction

    with pytest.raises(IntegrityError), transaction.atomic():
        DocumentVersion.objects.create(
            document=d, version_label="x", file_ext="pdf", file_sha256="0" * 64, is_current=True
        )


def test_only_owner_or_lead_edit_and_upload(member, lead, make_person):
    d = doc(member)
    other = make_person("otra@lev.cl")
    for call in (
        lambda: services.upload_version(d, other, up()),
        lambda: services.update_document(d, other, title="x", doc_type="manual"),
        lambda: services.make_current(d.current, other),
        lambda: services.delete_document(d, other),
    ):
        with pytest.raises(PermissionError):
            call()
    services.upload_version(d, lead, up("c.pdf", PDF + b"3"))
    assert d.versions.count() == 2


# --- visibilidad ---------------------------------------------------------------------------------------------------------


def test_restricted_documents_are_403_style_hidden_to_members(
    client_for, member, lead, make_person
):
    other = make_person("otra@lev.cl")
    secret = doc(other, "Confidencial", restricted=True)
    open_doc = doc(other, "Abierto")
    client = client_for(member.login)
    assert client.get(f"/documentos/{secret.pk}/").status_code == 404
    assert client.get(f"/documentos/{secret.pk}/archivo/").status_code == 404
    assert client.post(f"/documentos/{secret.pk}/subir/", {"file": up()}).status_code == 404
    listing = client.get("/documentos/").content.decode()
    assert "Abierto" in listing and "Confidencial" not in listing
    assert client.get(f"/documentos/{open_doc.pk}/archivo/").status_code == 200
    assert client_for(lead.login).get(f"/documentos/{secret.pk}/archivo/").status_code == 200
    assert client_for(other.login).get(f"/documentos/{secret.pk}/archivo/").status_code == 200


def test_restricted_filter_in_services(member, lead):
    doc(lead, "De lead", restricted=True)
    assert services.listing(member).count() == 0 and services.listing(lead).count() == 1


def test_download_is_an_attachment_with_safe_headers(client_for, member):
    d = doc(member, "Manual: ¡Revit! 2026")
    response = client_for(member.login).get(f"/documentos/{d.pk}/archivo/")
    assert response["Content-Type"] == "application/octet-stream"
    assert (
        "attachment" in response["Content-Disposition"]
        and "manual-revit-2026-v1.pdf" in response["Content-Disposition"]
    )
    assert (
        response["X-Content-Type-Options"] == "nosniff" and "no-store" in response["Cache-Control"]
    )
    assert b"".join(response.streaming_content).startswith(b"%PDF")


def test_download_specific_version_and_missing_file(client_for, member):
    d = doc(member)
    first = d.current
    services.upload_version(d, member, up("b.pdf", PDF + b"2"))
    body = b"".join(
        client_for(member.login).get(f"/documentos/{d.pk}/archivo/{first.pk}/").streaming_content
    )
    assert body == PDF
    os.remove(first.file.path)
    assert (
        client_for(member.login).get(f"/documentos/{d.pk}/archivo/{first.pk}/").status_code == 404
    )
    other = doc(member, "Otro")
    assert (
        client_for(member.login).get(f"/documentos/{d.pk}/archivo/{other.current.pk}/").status_code
        == 404
    )


def test_no_static_or_media_url_exposes_files(client, member):
    d = doc(member)
    assert client.get("/media/" + d.current.file.name).status_code in (401, 403, 404)


# --- borrado -----------------------------------------------------------------------------------------------------------------


def test_deleting_removes_every_file(member, django_capture_on_commit_callbacks):
    d = doc(member)
    services.upload_version(d, member, up("b.pdf", PDF + b"2"))
    paths = [Path(v.file.path) for v in d.versions.all()]
    with django_capture_on_commit_callbacks(execute=True):
        services.delete_document(d, member)
    assert not Document.objects.exists() and not any(p.exists() for p in paths)


def test_deleting_the_owner_removes_files(member, django_capture_on_commit_callbacks):
    path = Path(doc(member).current.file.path)
    with django_capture_on_commit_callbacks(execute=True):
        member.delete()
    assert not path.exists()


# --- listado y filtros ------------------------------------------------------------------------------------------------


def test_filters_and_tags(member):
    arq = Discipline.objects.get(slug="arquitectura")
    a = services.create_document(
        member,
        title="Plantilla muro",
        doc_type="template_rte",
        upload=up("p.rte", OLE),
        tags="Muros, muros,  RTE ",
        disciplines=[arq],
    )
    b = doc(member, "Guía de láminas", tags=["laminas"])
    assert a.tags == ["muros", "rte"]
    titles = lambda **kw: {d.title for d in services.listing(member, **kw)}  # noqa: E731
    assert titles(doc_type="template_rte") == {"Plantilla muro"}
    assert titles(discipline=arq) == {"Plantilla muro"}
    assert titles(tag="muros") == {"Plantilla muro"} and titles(tag="mur") == set()
    assert titles(q="LÁMINAS") == {"Guía de láminas"} or titles(q="láminas") == {"Guía de láminas"}
    assert titles(q="rte") == {"Plantilla muro"}
    assert services.all_tags(member) == ["laminas", "muros", "rte"] and b


def test_clean_tags_limits():
    assert len(services.clean_tags(",".join(str(i) for i in range(30)))) == services.TAGS_LIMIT
    assert services.clean_tags("a" * 100) == ["a" * services.TAG_MAX]
    assert services.clean_tags(None) == []


def test_title_validation(member):
    with pytest.raises(ValueError):
        services.create_document(member, title="  ", doc_type="manual", upload=up())
    with pytest.raises(ValueError):
        services.create_document(member, title="x" * 201, doc_type="manual", upload=up())
    assert not Document.objects.exists() and not DocumentVersion.objects.exists()


def test_unknown_type_falls_back_to_other(member):
    assert (
        services.create_document(member, title="x", doc_type="zzz", upload=up()).doc_type == "other"
    )


# --- vistas --------------------------------------------------------------------------------------------------------------------


def test_upload_flow_over_http(client_for, member):
    client = client_for(member.login)
    assert client.get("/documentos/nuevo/").status_code == 200
    response = client.post(
        "/documentos/nuevo/",
        {
            "title": "Guía BIM",
            "doc_type": "guide",
            "description": "Para empezar",
            "tags": "bim",
            "disciplines": ["arquitectura"],
            "file": up(),
        },
    )
    d = Document.objects.get()
    assert response["Location"] == f"/documentos/{d.pk}/" and d.disciplines.count() == 1
    html = client.get(f"/documentos/{d.pk}/").content.decode()
    assert "Guía BIM" in html and "Vigente" in html and "Subir versión nueva" in html
    client.post(
        f"/documentos/{d.pk}/subir/", {"file": up("b.pdf", PDF + b"2"), "version_label": "v2"}
    )
    assert d.versions.count() == 2 and d.current.version_label == "v2"


def test_invalid_upload_shows_the_error_and_creates_nothing(client_for, member):
    response = client_for(member.login).post(
        "/documentos/nuevo/", {"title": "Malo", "doc_type": "guide", "file": up("virus.exe", b"MZ")}
    )
    assert (
        response.status_code == 200
        and "no permitido" in response.content.decode()
        and not Document.objects.exists()
    )
    missing = client_for(member.login).post(
        "/documentos/nuevo/", {"title": "Sin archivo", "doc_type": "guide"}
    )
    assert "Elige el archivo" in missing.content.decode()


def test_edit_and_permissions_over_http(client_for, member, lead, make_person):
    d = doc(member)
    other = make_person("otra@lev.cl")
    assert client_for(other.login).get(f"/documentos/{d.pk}/editar/").status_code == 404
    client_for(member.login).post(
        f"/documentos/{d.pk}/editar/", {"title": "Nuevo título", "doc_type": "guide", "tags": "x"}
    )
    d.refresh_from_db()
    assert d.title == "Nuevo título" and d.doc_type == "guide"
    assert client_for(lead.login).get(f"/documentos/{d.pk}/editar/").status_code == 200
    client_for(other.login).post(f"/documentos/{d.pk}/eliminar/")
    assert Document.objects.exists()
    client_for(member.login).post(f"/documentos/{d.pk}/eliminar/")
    assert not Document.objects.exists()


def test_text_is_escaped(client_for, member):
    d = services.create_document(
        member,
        title="<script>alert(1)</script>",
        doc_type="guide",
        description="<img src=x onerror=1>",
        tags="<b>",
        upload=up(),
    )
    html = client_for(member.login).get(f"/documentos/{d.pk}/").content.decode()
    assert "<script>alert(1)</script>" not in html and "<img src=x" not in html
    assert "&lt;script&gt;" in html and "#&lt;b&gt;" in html


def test_pagination_and_query_count(client_for, member, django_assert_max_num_queries):
    for i in range(45):
        doc(member, f"Documento {i}")
    client = client_for(member.login)
    with django_assert_max_num_queries(30):
        first = client.get("/documentos/").content.decode()
    assert "Página 1 de 3" in first and first.count('<li class="doc">') == 20


def test_pending_people_cannot_open_documents(client_for, member, make_person):
    d = doc(member)
    pending = make_person("nuevo@lev.cl", status="pending")
    assert client_for(pending.login).get(f"/documentos/{d.pk}/archivo/").status_code != 200


def test_module_and_nav(client_for, member):
    html = client_for(member.login).get("/").content.decode()
    assert 'href="/documentos/"' in html
