"""Lectura local del documento de una credencial (D40).

El archivo se procesa **en memoria y en este servidor**: sin red, sin IA, sin OCR en la nube, sin guardar el texto ni
el archivo, sin registrar su contenido. Solo se devuelven los campos propuestos y banderas; el texto completo y el
nombre leído nunca salen de aquí.

Para sumar un emisor nuevo: escribir una función `analyze_<emisor>(text) -> dict | None` que devuelva solo lo que
encuentre con claridad y registrarla en `ANALYZERS` (antes del genérico, que va último). Claves posibles: `title`,
`issuer`, `platform_slug`, `kind`, `credential_id`, `verify_url`, `issued_on` (date), `expires_on` (date) y `holder`
(nombre de la persona, solo para verificar titularidad; no se devuelve).
"""

import io
import logging
import re
import unicodedata
from datetime import date
from difflib import SequenceMatcher

from apps.catalog.models import Platform, Resource

from . import files
from .models import Credential

MAX_PAGES = 3
MAX_TEXT = 20000

MSG_IMAGE = "Las imágenes no se pueden leer automáticamente; completa a mano."
MSG_UNREADABLE = "No pude leer este documento: completa a mano."
WARN_OWNER = "Este certificado parece estar a nombre de otra persona."
WARN_NO_MATCH = "No encontré este curso en el catálogo: elígelo a mano si corresponde."
WARN_AMBIGUOUS = "Hay varios cursos del catálogo parecidos: elige el correcto a mano."

FUZZY_THRESHOLD = 0.9
AMBIGUITY_GAP = 0.04


class UnreadableDocument(Exception):
    """El documento no se pudo leer (cifrado, dañado, sin texto, o una imagen)."""


class ImageDocument(UnreadableDocument):
    """PNG o JPG: no hay motor de OCR local."""


# --- extracción -----------------------------------------------------------------------------------------------------


def extract_text(upload) -> str:
    """Texto de las primeras páginas de un PDF. Cualquier fallo se traduce en `UnreadableDocument`."""
    upload.seek(0)
    data = upload.read(files.MAX_BYTES + 1)
    upload.seek(0)
    kind = files.detect_type(data[:16])
    if kind in {"png", "jpg"}:
        raise ImageDocument(MSG_IMAGE)
    if kind != "pdf":
        raise UnreadableDocument(MSG_UNREADABLE)
    # pypdf avisa por `logging` de PDF dañados: se silencia para que nada del documento llegue a los logs.
    logging.getLogger("pypdf").setLevel(logging.CRITICAL)
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        # Muchos certificados (TCPDF) vienen «cifrados» solo para restringir copiar o imprimir: la clave de apertura es
        # vacía. Si pide una contraseña real, no se intenta adivinar nada.
        if reader.is_encrypted and not reader.decrypt(""):
            raise UnreadableDocument(MSG_UNREADABLE)
        parts = [page.extract_text() or "" for page in reader.pages[:MAX_PAGES]]
    except UnreadableDocument:
        raise
    except Exception:
        raise UnreadableDocument(MSG_UNREADABLE) from None
    text = "\n".join(parts).strip()[:MAX_TEXT]
    if not text:
        raise UnreadableDocument(MSG_UNREADABLE)
    return text


# --- utilidades de texto ----------------------------------------------------------------------------------------------


def normalize(value: str) -> str:
    """Minúsculas, sin acentos ni puntuación, con espacios simples."""
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(c for c in value if not unicodedata.combining(c)).casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value).split())


def _flat(text: str) -> str:
    return " ".join(text.split())


def _safe_date(year: int, month: int, day: int):
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _us_date(month: str, day: str, year: str):
    m, d = int(month), int(day)
    if m > 12 >= d:  # el documento venía como día/mes
        m, d = d, m
    return _safe_date(int(year), m, d)


# --- analizadores -----------------------------------------------------------------------------------------------------

_BENTLEY_COURSE = re.compile(
    r"(?P<label>OnDemand Course|Learning Plan|Classroom Course|Virtual Course|Course)\s*:\s*"
    r"(?P<title>.+?)(?=\s*(?:CEU\(s\)|PDH|Certificate ID|Upon successful|$))",
    re.IGNORECASE,
)


def clean_course_title(raw: str) -> str:
    """Quita `|Nivel|` y `CEU(s): x` del título que imprime Bentley Learn."""
    title = re.sub(r"\|[^|]{1,40}\|", " ", raw)
    title = re.sub(r"CEU\(s\)\s*:?\s*[\d.,]*", " ", title, flags=re.IGNORECASE)
    return " ".join(title.split()).strip(" |:-")


def _holder_before_date(text: str, match) -> str:
    """El nombre impreso en la línea anterior a «on MM/DD/YYYY»."""
    lines = [ln.strip() for ln in text[: match.start()].splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def analyze_bentley(text: str):
    flat = _flat(text)
    named = re.search(r"\bBentley\b", flat) and re.search(
        r"Certificate of Accomplishment", flat, re.I
    )
    # En los PDF reales el logo y el título van como imagen: solo queda el cuerpo del texto, que tiene esta forma.
    shaped = (
        re.search(
            r"Upon successful completion of\s+(?:OnDemand Course|Learning Plan)\s*:", flat, re.I
        )
        and re.search(r"Certificate ID\s*:", flat, re.I)
        and re.search(r"\bon\s+\d{1,2}/\d{1,2}/\d{4}\b", flat)
    )
    if not (named or shaped):
        return None
    found = {"issuer": "Bentley Systems", "platform_slug": "bentley-learn"}
    course = _BENTLEY_COURSE.search(flat)
    if course:
        title = clean_course_title(course["title"])
        if title:
            found["title"] = title
        # Un plan de aprendizaje sigue siendo una finalización; el catálogo puede afinarlo (examen → certificación).
        found["kind"] = Credential.Kind.COMPLETION
    cid = re.search(r"Certificate ID\s*:\s*([A-Za-z0-9][A-Za-z0-9\-_]{2,})", flat, re.I)
    if cid:
        found["credential_id"] = cid[1]
    on = re.search(r"(?m)^\s*on\s+(\d{1,2})/(\d{1,2})/(\d{4})\s*$", text, re.I)
    if on:
        issued = _us_date(on[1], on[2], on[3])
        if issued:
            found["issued_on"] = issued
        holder = _holder_before_date(text, on)
        if holder:
            found["holder"] = holder
    else:
        loose = re.search(r"\bon\s+(\d{1,2})/(\d{1,2})/(\d{4})\b", flat)
        if loose:
            issued = _us_date(loose[1], loose[2], loose[3])
            if issued:
                found["issued_on"] = issued
    return found


_ID_LABEL = re.compile(
    r"(?:certificate|credential|certification|license|licence)?\s*(?:id|number|no\.?|n[°º])\s*[:#]\s*"
    r"([A-Za-z0-9][A-Za-z0-9\-_/.]{3,})",
    re.IGNORECASE,
)
_ISO = r"(\d{4})-(\d{2})-(\d{2})"
_DMY = r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})"
_EXPIRES_LABEL = (
    r"(?:valid until|valid through|valid thru|expires?(?: on)?|expiry(?: date)?|expiration(?: date)?"
    r"|vence(?: el)?|vencimiento|v[aá]lido hasta)"
)
_ISSUED_LABEL = (
    r"(?:issued(?: on)?|issue date|date of issue|completed(?: on)?|completion date|fecha de emisi[oó]n"
    r"|emitido(?: el)?|emisi[oó]n|fecha de t[eé]rmino)"
)


def _labeled_date(flat: str, label: str):
    for pattern, order in ((_ISO, "ymd"), (_DMY, "dmy")):
        m = re.search(rf"{label}\s*[:\-]?\s*{pattern}", flat, re.IGNORECASE)
        if m:
            a, b, c = (int(x) for x in m.groups())
            found = _safe_date(a, b, c) if order == "ymd" else _safe_date(c, b, a)
            if found:
                return found
    return None


def _all_dates(flat: str):
    found = []
    for m in re.finditer(_ISO, flat):
        d = _safe_date(int(m[1]), int(m[2]), int(m[3]))
        if d:
            found.append(d)
    for m in re.finditer(_DMY, flat):
        d = _safe_date(int(m[3]), int(m[2]), int(m[1]))
        if d:
            found.append(d)
    return found


def analyze_generic(text: str):
    flat = _flat(text)
    found = {}
    cid = _ID_LABEL.search(flat)
    if cid:
        found["credential_id"] = cid[1].rstrip(".")
    expires = _labeled_date(flat, _EXPIRES_LABEL)
    issued = _labeled_date(flat, _ISSUED_LABEL)
    if expires:
        found["expires_on"] = expires
    if issued:
        found["issued_on"] = issued
    elif not expires:
        dates = set(_all_dates(flat))
        if len(dates) == 1:  # una sola fecha sin etiqueta: la más probable es la de emisión
            found["issued_on"] = dates.pop()
    for url in re.findall(r"https?://[^\s<>\"']+", flat):
        url = url.rstrip(".,;)")
        if re.search(r"verif|valid|credential|badge|certificate|check|acclaim|credly", url, re.I):
            found["verify_url"] = url[:500]
            break
    return found or None


ANALYZERS = [("bentley", analyze_bentley), ("generic", analyze_generic)]


def analyze(text: str) -> dict:
    """Corre los analizadores en orden y se queda con el primero que reconoce el documento."""
    for _name, fn in ANALYZERS:
        found = fn(text)
        if found:
            return found
    return {}


# --- titularidad ------------------------------------------------------------------------------------------------------


def _tokens(name: str) -> set[str]:
    return {t for t in normalize(name).split() if len(t) > 1}


def holder_matches(holder: str, person) -> bool | None:
    """¿El nombre del documento es el de la persona? None si no hay con qué comparar. Todo local."""
    cert = _tokens(holder)
    if not cert:
        return None
    display = (getattr(person, "display_name", "") or "").strip()
    if display:
        mine = _tokens(display)
        initials = False
    else:
        local = (getattr(person, "login", "") or "").split("@")[0]
        mine = _tokens(re.sub(r"[._\-+]+", " ", local))
        initials = True
    if not mine:
        return None
    if mine <= cert or cert <= mine:
        return True
    if initials:  # «cmunoz» = inicial del nombre + apellido
        return all(
            tok in cert or any(tok == c[0] + o for c in cert for o in cert if o != c)
            for tok in mine
        )
    return False


# --- cruce con el catálogo -------------------------------------------------------------------------------------------


def _digits(norm: str) -> list[str]:
    return re.findall(r"\d+", norm)


def _score(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if _digits(a) != _digits(b):  # «Ch. 2» no es «Ch. 4»
        return 0.0
    short, long_ = sorted((a, b), key=len)
    ratio = SequenceMatcher(None, a, b)
    if (
        ratio.real_quick_ratio() < FUZZY_THRESHOLD - 0.1
        or ratio.quick_ratio() < FUZZY_THRESHOLD - 0.1
    ):
        score = 0.0
    else:
        score = ratio.ratio()
    if len(short) >= 15 and short in long_ and len(short) / len(long_) >= 0.8:
        score = max(score, 0.95)
    return score


def match_catalog(title: str, platform_slug: str | None = None) -> dict:
    """Busca el recurso del catálogo que corresponde al título leído.

    Devuelve `{"status": "match"|"ambiguous"|"none", "resource": Resource|None}`. Con varias o ninguna
    coincidencia clara no elige. Consultas fijas (una por el catálogo candidato), sin importar su tamaño.
    """
    from .forms import CredentialForm

    wanted = normalize(title)
    if not wanted:
        return {"status": "none", "resource": None}
    candidates = CredentialForm.base_fields["resource"].queryset.order_by()
    if platform_slug:
        candidates = candidates.filter(platform__slug=platform_slug)
    rows = [(pk, normalize(t)) for pk, t in candidates.values_list("pk", "title")]
    exact = [pk for pk, norm in rows if norm == wanted]
    if len(exact) == 1:
        best = exact[0]
    elif len(exact) > 1:
        return {"status": "ambiguous", "resource": None}
    else:
        scored = sorted(((_score(wanted, norm), pk) for pk, norm in rows), reverse=True)
        scored = [s for s in scored if s[0] >= FUZZY_THRESHOLD]
        if not scored:
            return {"status": "none", "resource": None}
        if len(scored) > 1 and scored[0][0] - scored[1][0] < AMBIGUITY_GAP:
            return {"status": "ambiguous", "resource": None}
        best = scored[0][1]
    resource = Resource.objects.select_related("platform").get(pk=best)
    return {"status": "match", "resource": resource}


def find_parent_plan(title: str, platform_slug: str | None = None) -> str | None:
    """Título del plan de aprendizaje del catálogo que incluye este curso como capítulo (`contains`).

    Solo informa: el certificado es del capítulo, no del plan, así que nunca se vincula el plan a la credencial.
    Una sola consulta, sin importar el tamaño del catálogo.
    """
    from apps.paths.models import ExternalCourse

    wanted = normalize(title)
    if not wanted:
        return None
    rows = ExternalCourse.objects.filter(retired=False)
    if platform_slug:
        rows = rows.filter(resource__platform__slug=platform_slug)
    for plan_title, contains in rows.order_by("pk").values_list("resource__title", "contains"):
        if any(normalize(str(item)) == wanted for item in contains or []):
            return plan_title
    return None


def _kind_for(resource) -> str:
    if resource.kind == Resource.Kind.EXAM:
        return Credential.Kind.CERTIFICATION
    from apps.paths.models import ExternalCourse

    relic = ExternalCourse.objects.filter(resource=resource, reward=ExternalCourse.Reward.RELIC)
    return Credential.Kind.CERTIFICATION if relic.exists() else Credential.Kind.COMPLETION


# --- punto de entrada ---------------------------------------------------------------------------------------------------


def _iso(value):
    return value.isoformat() if value else None


def read_document(upload, person) -> dict:
    """Lee el documento y propone campos. Sin efectos secundarios; nunca devuelve el texto ni el nombre leído."""
    result = {
        "ok": False,
        "fields": {},
        "filled": [],
        "warnings": [],
        "notes": [],
        "unreadable": False,
    }
    try:
        text = extract_text(upload)
    except UnreadableDocument as exc:
        result["unreadable"] = True
        result["message"] = str(exc) or MSG_UNREADABLE
        return result

    found = analyze(text)
    holder = found.pop("holder", "")
    fields = {}
    if holder and holder_matches(holder, person) is False:
        result["warnings"].append(WARN_OWNER)

    for key in ("title", "issuer", "kind", "credential_id", "verify_url"):
        if found.get(key):
            fields[key] = found[key]
    for key in ("issued_on", "expires_on"):
        if found.get(key):
            fields[key] = _iso(found[key])

    platform = None
    if found.get("platform_slug"):
        platform = Platform.objects.filter(slug=found["platform_slug"]).first()
    if fields.get("title"):
        matched = match_catalog(fields["title"], found.get("platform_slug"))
        if matched["status"] == "match":
            resource = matched["resource"]
            fields["resource"] = resource.pk
            fields["title"] = resource.title
            fields["kind"] = _kind_for(resource)
            platform = resource.platform
            skills = list(resource.skills.values_list("pk", flat=True))
            if skills:
                fields["skills"] = skills
        elif matched["status"] == "ambiguous":
            result["warnings"].append(WARN_AMBIGUOUS)
        else:
            plan = find_parent_plan(fields["title"], found.get("platform_slug"))
            if plan:
                result["notes"].append(
                    f"Este certificado es de un capítulo del plan «{plan}»: no lo vinculé al plan completo."
                )
            elif found.get("platform_slug"):
                result["warnings"].append(WARN_NO_MATCH)
    if platform:
        fields["platform"] = platform.pk

    result["fields"] = fields
    result["filled"] = list(fields)
    result["ok"] = bool(fields)
    if not fields:
        result["unreadable"] = True
        result["message"] = MSG_UNREADABLE
    return result
