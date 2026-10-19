"""Lectura local del documento de una credencial (D40). Todo el texto y los nombres son ficticios."""

import io
import json
import logging
import socket
from datetime import date

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from apps.accounts.models import Person
from apps.catalog.models import Platform, Resource, Skill
from apps.credentials import reader
from apps.credentials.models import Credential
from apps.paths.models import ExternalCourse

pytestmark = pytest.mark.django_db

HOLDER = "Marina Quispe Valdivia"  # nombre ficticio
COURSE = "Ch. 2: Controlling the Display of Designs for Civil Designers"
BENTLEY_TEXT = (
    f"{HOLDER}\non 10/19/2026\nUpon successful completion of\n"
    f"OnDemand Course: {COURSE} |Fundamental| CEU(s): 0.25\n"
    "Certificate ID: C000111\nPowered by TCPDF (www.tcpdf.org)\n"
)
URL = "/certificados/leer/"


def make_pdf(lines):
    """PDF de una página con texto estándar (Helvetica), armado a mano: sin librerías de escritura."""
    stream = "BT /F1 14 Tf 40 760 Td 18 TL\n" + "\n".join(
        "(" + ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ") '"
        for ln in lines
    )
    stream += "\nET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


BENTLEY_PDF = make_pdf(BENTLEY_TEXT.splitlines())
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def up(data, name="certificado.pdf"):
    return SimpleUploadedFile(name, data, content_type="application/octet-stream")


@pytest.fixture(autouse=True)
def seeded(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    cache.clear()  # el límite de lecturas vive en la caché y los ids se repiten entre pruebas
    call_command("seed_catalog", verbosity=0)


@pytest.fixture
def bentley_course(db):
    platform = Platform.objects.get(slug="bentley-learn")
    res = Resource.objects.create(
        platform=platform,
        title=COURSE,
        kind=Resource.Kind.COURSE,
        grants_completion_certificate=True,
    )
    res.skills.set(Skill.objects.all()[:2])
    return res


@pytest.fixture
def holder_person(member):
    member.display_name = "Marina Quispe"
    member.save(update_fields=["display_name"])
    return member


def read_as(person, data=BENTLEY_PDF):
    return reader.read_document(up(data), person)


# --- limpieza del título y fechas -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("Ch. 2: Display for Civil Designers |Fundamental| CEU(s): 0.25", "Ch. 2: Display for Civil Designers"),
        ("Bentley Accredited MicroStation User CEU(s): 9.5", "Bentley Accredited MicroStation User"),
        ("Intro to OpenRoads |Advanced|", "Intro to OpenRoads"),
        ("  Solo el título  ", "Solo el título"),
    ],
)  # fmt: skip
def test_clean_course_title(raw, clean):
    assert reader.clean_course_title(raw) == clean


def test_bentley_analyzer_reads_us_date_and_fields():
    found = reader.analyze_bentley(BENTLEY_TEXT)
    assert found["issued_on"] == date(2026, 10, 19)  # mes/día/año
    assert found["title"] == COURSE
    assert found["credential_id"] == "C000111"
    assert found["issuer"] == "Bentley Systems"
    assert found["platform_slug"] == "bentley-learn"
    assert found["kind"] == Credential.Kind.COMPLETION
    assert found["holder"] == HOLDER


def test_bentley_us_date_with_day_first_is_swapped_when_month_is_impossible():
    text = BENTLEY_TEXT.replace("10/19/2026", "25/12/2026")
    assert reader.analyze_bentley(text)["issued_on"] == date(2026, 12, 25)


def test_bentley_learning_plan_and_named_variant():
    text = (
        "Bentley Systems\nCertificate of Accomplishment\nAna Ejemplo\non 01/05/2027\n"
        "Learning Plan: Bentley Accredited MicroStation User\nCertificate ID: P-7788\n"
    )
    found = reader.analyze_bentley(text)
    assert found["title"] == "Bentley Accredited MicroStation User"
    assert found["issued_on"] == date(2027, 1, 5)


def test_bentley_analyzer_ignores_other_documents():
    assert reader.analyze_bentley("Curso de Excel\nCertificate ID: ZZ-1234\n") is None


# --- analizador genérico ------------------------------------------------------------------------------------------------


def test_generic_analyzer_finds_id_dates_and_verify_url():
    text = (
        "Certified Professional\nCredential ID: ABC-12345\nIssued on 2026-03-04\n"
        "Valid until 2029-03-04\nVerify at https://verify.example.com/c/ABC-12345.\n"
    )
    found = reader.analyze_generic(text)
    assert found["credential_id"] == "ABC-12345"
    assert found["issued_on"] == date(2026, 3, 4)
    assert found["expires_on"] == date(2029, 3, 4)
    assert found["verify_url"] == "https://verify.example.com/c/ABC-12345"


def test_generic_dd_mm_yyyy_and_single_unlabeled_date():
    assert reader.analyze_generic("Fecha de emisión: 14/06/2026\nVence el 14/06/2028")[
        "issued_on"
    ] == date(2026, 6, 14)
    assert reader.analyze_generic("Diploma\nEmitido en la ciudad\n03/04/2026")["issued_on"] == date(
        2026, 4, 3
    )


def test_generic_proposes_nothing_when_unclear():
    assert reader.analyze_generic("Texto sin datos claros. 12 de enero y 3 de mayo.") is None
    # dos fechas sin etiqueta: no se adivina cuál es la de emisión
    assert "issued_on" not in (reader.analyze_generic("10/01/2026 y 11/02/2026 ID: X-9999") or {})


# --- titularidad ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("display", "holder", "expected"),
    [
        ("Marina Quispe", "Marina Quispe Valdivia", True),  # apellido materno extra
        ("Marina Isabel Quispe Valdivia", "MARINA QUISPE", True),  # segundo nombre
        ("María Quispe", "Maria Quispe", True),  # acentos
        ("Marina Quispe", "Tomás Herrera Rojas", False),
        ("", "Tomás Herrera", None),
        ("Marina Quispe", "", None),
    ],
)  # fmt: skip
def test_holder_matches(display, holder, expected):
    person = Person(login="x@example.com", display_name=display)
    if not display:
        person = Person(login="", display_name="")
    assert reader.holder_matches(holder, person) is expected


def test_holder_matches_login_derived_name():
    assert (
        reader.holder_matches("Marina Quispe Valdivia", Person(login="marina.quispe@example.com"))
        is True
    )
    assert (
        reader.holder_matches("Marina Quispe Valdivia", Person(login="mquispe@example.com")) is True
    )
    assert reader.holder_matches("Tomás Herrera", Person(login="mquispe@example.com")) is False


def test_owner_warning_without_revealing_the_name(member, holder_person):
    same = read_as(holder_person)
    assert reader.WARN_OWNER not in same["warnings"]
    member.display_name = "Otra Persona"
    other = read_as(member)
    assert reader.WARN_OWNER in other["warnings"]
    blob = json.dumps(other)
    assert "Quispe" not in blob and "Valdivia" not in blob


# --- cruce con el catálogo --------------------------------------------------------------------------------------------


def test_catalog_match_exact_proposes_resource_platform_and_skills(holder_person, bentley_course):
    result = read_as(holder_person)
    fields = result["fields"]
    assert fields["resource"] == bentley_course.pk
    assert fields["platform"] == bentley_course.platform_id
    assert set(fields["skills"]) == set(bentley_course.skills.values_list("pk", flat=True))
    assert fields["credential_id"] == "C000111" and fields["issued_on"] == "2026-10-19"
    assert result["ok"] and not result["unreadable"] and result["warnings"] == []
    assert set(result["filled"]) == set(fields)


def test_catalog_match_tolerates_small_differences(bentley_course):
    found = reader.match_catalog(COURSE.replace("Ch. 2:", "Ch. 2 -").lower(), "bentley-learn")
    assert found["status"] == "match" and found["resource"].pk == bentley_course.pk


def test_catalog_digits_are_never_confused(bentley_course):
    found = reader.match_catalog(COURSE.replace("Ch. 2", "Ch. 4"), "bentley-learn")
    assert found["status"] == "none"


def test_catalog_ambiguous_does_not_choose(bentley_course):
    platform = bentley_course.platform
    Resource.objects.create(
        platform=platform,
        title=COURSE + "s",
        kind=Resource.Kind.COURSE,
        grants_completion_certificate=True,
    )
    found = reader.match_catalog(COURSE + " ", "bentley-learn")
    assert found["status"] == "match"  # el exacto gana
    found = reader.match_catalog(COURSE[:-1], "bentley-learn")
    assert found["status"] == "ambiguous" and found["resource"] is None


def test_catalog_none_keeps_title_and_leaves_course_unselected(holder_person):
    result = read_as(
        holder_person, make_pdf(BENTLEY_TEXT.replace(COURSE, "Curso Inexistente 9").splitlines())
    )
    assert "resource" not in result["fields"] and "skills" not in result["fields"]
    assert result["fields"]["title"] == "Curso Inexistente 9"
    assert reader.WARN_NO_MATCH in result["warnings"]


def test_chapter_of_a_plan_is_not_linked_to_the_plan(holder_person):
    plan = ExternalCourse.objects.filter(contains__icontains="Controlling the Display").first()
    assert plan is not None  # sale de la semilla de bentley-learn
    result = read_as(holder_person)
    assert "resource" not in result["fields"]
    assert any(plan.resource.title in n for n in result["notes"])
    assert reader.WARN_NO_MATCH not in result["warnings"]


def test_exam_match_proposes_certification(holder_person, bentley_course):
    bentley_course.kind = Resource.Kind.EXAM
    bentley_course.save()
    assert read_as(holder_person)["fields"]["kind"] == Credential.Kind.CERTIFICATION


def test_catalog_queries_do_not_grow_with_the_catalog(holder_person, bentley_course):
    def count():
        with CaptureQueriesContext(connection) as ctx:
            read_as(holder_person)
        return len(ctx)

    base = count()
    platform = bentley_course.platform
    Resource.objects.bulk_create(
        Resource(
            platform=platform,
            title=f"Otro curso {i}",
            kind=Resource.Kind.COURSE,
            grants_completion_certificate=True,
        )
        for i in range(60)
    )
    assert count() == base
    assert base <= 8


# --- extracción real ------------------------------------------------------------------------------------------------------


def test_extract_text_from_a_handmade_pdf():
    text = reader.extract_text(up(make_pdf(["Hola mundo", "Certificate ID: A1B2C3"])))
    assert "Hola mundo" in text and "Certificate ID: A1B2C3" in text


def test_blank_pages_have_no_text():
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(5):
        writer.add_blank_page(200, 200)
    buffer = io.BytesIO()
    writer.write(buffer)
    with pytest.raises(reader.UnreadableDocument):  # páginas en blanco: sin texto
        reader.extract_text(up(buffer.getvalue()))


@pytest.mark.parametrize(
    "data",
    [
        b"%PDF-1.4\nesto no es un pdf de verdad\n%%EOF\n",  # corrupto
        b"%PDF-1.4\n" + b"\x00" * 200,
        make_pdf([""]),  # sin texto
    ],
)
def test_corrupt_or_empty_pdf_is_unreadable_without_failing(member, data):
    result = read_as(member, data)
    assert result["unreadable"] is True and result["ok"] is False
    assert result["message"] == reader.MSG_UNREADABLE


def test_encrypted_pdf_with_a_real_password_is_unreadable(member):
    from pypdf import PdfReader, PdfWriter

    base = PdfReader(io.BytesIO(BENTLEY_PDF))
    writer = PdfWriter()
    writer.append_pages_from_reader(base)
    buffer = io.BytesIO()
    try:
        writer.encrypt("clave-real", algorithm="RC4-128")  # RC4 no pide `cryptography`
        writer.write(buffer)
    except Exception:
        pytest.skip("esta versión de pypdf no cifra con RC4")
    result = read_as(member, buffer.getvalue())
    assert result["unreadable"] is True


def test_pdf_locked_only_against_copying_is_readable(member):
    """Como los de TCPDF: «cifrados» con clave de apertura vacía, solo para restringir permisos."""
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    writer.append_pages_from_reader(PdfReader(io.BytesIO(BENTLEY_PDF)))
    buffer = io.BytesIO()
    try:
        writer.encrypt("", "dueno-del-pdf", algorithm="RC4-128")
        writer.write(buffer)
    except Exception:
        pytest.skip("esta versión de pypdf no cifra con RC4")
    result = read_as(member, buffer.getvalue())
    assert result["ok"] and result["fields"]["credential_id"] == "C000111"


def test_image_is_not_read_and_says_so(member):
    result = reader.read_document(up(PNG, "foto.png"), member)
    assert result["unreadable"] is True and result["message"] == reader.MSG_IMAGE
    assert result["fields"] == {}


# --- la vista -----------------------------------------------------------------------------------------------------------


def post(client, data=BENTLEY_PDF, name="certificado.pdf", **extra):
    return client.post(URL, {"file": up(data, name)}, **extra)


def test_view_requires_login_and_approval(client_for, make_person):
    assert post(client_for(None)).status_code in {302, 401, 403}
    pending = make_person("pend@example.com", status="pending")
    response = post(client_for(pending.login))
    assert response.status_code == 302 and "/espera" in response["Location"]


def test_view_get_is_405(member_client):
    assert member_client.get(URL).status_code == 405


def test_view_requires_csrf(member):
    client = Client(
        enforce_csrf_checks=True, REMOTE_ADDR="127.0.0.1", HTTP_TAILSCALE_USER_LOGIN=member.login
    )
    assert post(client).status_code == 403


def test_view_returns_only_proposed_fields_and_never_the_text_or_the_name(
    member, member_client, bentley_course
):
    member.display_name = "Marina Quispe"
    member.save(update_fields=["display_name"])
    response = post(member_client)
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    data = response.json()
    assert set(data) == {"ok", "fields", "filled", "warnings", "notes", "unreadable"}
    assert data["fields"]["resource"] == bentley_course.pk
    body = response.content.decode()
    for secret in ("Quispe", "Valdivia", "Upon successful", "TCPDF", "CEU"):
        assert secret not in body


def test_view_rejects_bad_files_with_a_clear_error(member_client):
    for data, name in ((b"MZ\x90\x00" + b"x" * 40, "malo.pdf"), (BENTLEY_PDF, "texto.txt")):
        response = post(member_client, data, name)
        assert response.status_code == 400 and response["Cache-Control"] == "no-store"
        assert response.json()["ok"] is False and response.json()["error"]
    assert member_client.post(URL, {}).status_code == 400


def test_view_has_no_side_effects(member_client, tmp_path):
    before = Credential.objects.count()
    assert post(member_client).status_code == 200
    assert Credential.objects.count() == before
    assert not [
        p for p in tmp_path.rglob("*") if p.is_file()
    ]  # ni en MEDIA_ROOT ni en ningún otro lado


def test_view_makes_no_network_calls(member_client, monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("la lectura no puede abrir conexiones de red")

    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(socket.socket, "connect", boom)
    assert post(member_client).status_code == 200


def test_view_does_not_log_the_document_content(member_client, caplog):
    with caplog.at_level(logging.DEBUG):
        post(member_client)
        post(member_client, b"%PDF-1.4\n" + HOLDER.encode() + b"\n%%EOF\n")
    for secret in ("Quispe", "C000111", "Controlling"):
        assert secret not in caplog.text


def test_view_image_returns_the_message(member_client):
    response = post(member_client, PNG, "foto.png")
    data = response.json()
    assert response.status_code == 200 and data["unreadable"] is True
    assert data["message"] == reader.MSG_IMAGE


def test_view_is_rate_limited_per_person(member_client, monkeypatch):
    from apps.credentials import views

    monkeypatch.setattr(views, "READ_LIMIT", 2)
    assert post(member_client).status_code == 200
    assert post(member_client).status_code == 200
    blocked = post(member_client)
    assert blocked.status_code == 429 and blocked["Cache-Control"] == "no-store"


def test_form_page_offers_the_reader_and_works_without_js(member_client):
    html = member_client.get("/certificados/nueva/").content.decode()
    assert 'data-read-url="/certificados/leer/"' in html
    assert 'id="read-status"' in html and 'aria-live="polite"' in html
    assert "credentials/reader.js" in html
    assert 'name="file"' in html  # el formulario sigue enviándose normal
