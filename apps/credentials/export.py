"""Exportación de evidencia: ZIP con los archivos + `evidencia.xlsx` (Bloque 6).

El ZIP se arma al vuelo y no se guarda en disco: no queda nada que limpiar a las 24 h. Solo los responsables exportan,
y cada exportación queda en la bitácora. Los nombres dentro del ZIP se generan (nunca los del usuario).
"""

import io
import shutil
import tempfile
import zipfile
from datetime import date

from django.db.models import Q
from django.utils.text import slugify
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from apps.community.models import ModerationLog

from .models import Credential

MAX_CREDENTIALS = 500
MAX_BYTES = 200 * 1024 * 1024
COLUMNS = [
    ("Persona", 26), ("Credencial", 40), ("Tipo", 22), ("Emisor", 24), ("ID de la credencial", 24),
    ("Emisión", 12), ("Vencimiento", 12), ("URL de verificación", 36), ("Estado", 14),
    ("Plataforma", 22), ("Ruta", 24), ("Habilidades", 36), ("Archivo en el ZIP", 38), ("SHA-256", 30),
]  # fmt: skip
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def select(*, people=(), platforms=(), kinds=(), skills=(), only_verified=True):
    """Credenciales según la selección. Listas vacías = sin filtro en ese criterio."""
    qs = Credential.objects.select_related("owner", "platform", "path").prefetch_related("skills")
    if only_verified:
        qs = qs.filter(status=Credential.Status.VERIFIED)
    if people:
        qs = qs.filter(owner_id__in=list(people))
    if platforms:
        qs = qs.filter(platform__slug__in=list(platforms))
    if kinds:
        qs = qs.filter(kind__in=[k for k in kinds if k in Credential.Kind.values])
    if skills:
        qs = qs.filter(
            Q(skills__slug__in=list(skills)) | Q(resource__skills__slug__in=list(skills))
        )
    return qs.distinct().order_by("owner__display_name", "owner__login", "-issued_on", "id")


def _safe(value):
    """Texto seguro para una celda: neutraliza fórmulas (=, +, -, @) que Excel ejecutaría."""
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(_FORMULA_START) else text


def _zip_name(cred, used):
    base = f"{slugify(cred.owner.name) or 'persona'}/{slugify(cred.display_title)[:60] or 'credencial'}"
    ext = cred.file_kind or "bin"
    name, n = f"{base}.{ext}", 1
    while name in used:
        n += 1
        name = f"{base}-{n}.{ext}"
    used.add(name)
    return name


def _workbook(rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "Credenciales"
    ws.append([c for c, _ in COLUMNS])
    for i, (_, width) in enumerate(COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width
        ws.cell(row=1, column=i).font = Font(bold=True)
    ws.freeze_panes = "A2"
    for cred, zip_name in rows:
        skills = ", ".join(sorted(s.name for s in cred.skills.all()))
        ws.append(
            [
                _safe(cred.owner.name),
                _safe(cred.display_title),
                _safe(cred.get_kind_display()),
                _safe(cred.issuer),
                _safe(cred.credential_id),
                cred.issued_on,
                cred.expires_on,
                _safe(cred.verify_url),
                _safe(cred.get_status_display()),
                _safe(cred.platform.name if cred.platform else ""),
                _safe(cred.path.title if cred.path else ""),
                _safe(skills),
                _safe(zip_name),
                cred.file_sha256,
            ]
        )
    for col in (6, 7):  # fechas tipadas, no texto
        for cell in ws.iter_cols(min_col=col, max_col=col, min_row=2):
            for c in cell:
                c.number_format = "yyyy-mm-dd"
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def build_zip_file(by, creds):
    """Devuelve (bytes del ZIP, cantidad). Lanza ValueError si la selección es vacía o demasiado grande."""
    if not by.is_lead:
        raise PermissionError("Solo un responsable puede exportar credenciales.")
    creds = list(creds)
    if not creds:
        raise ValueError("No hay credenciales con esa selección.")
    if len(creds) > MAX_CREDENTIALS:
        raise ValueError(f"La selección supera {MAX_CREDENTIALS} credenciales: acótala.")
    # Archivo temporal (en disco pasados 16 MB): el ZIP nunca vive entero en memoria.
    buffer, used, rows, total = (
        tempfile.SpooledTemporaryFile(max_size=16 * 1024 * 1024),
        set(),
        [],
        0,
    )
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for cred in creds:
            name = ""
            try:
                handle = cred.file.open("rb")
            except (OSError, ValueError):
                handle = None
            if handle is not None:
                with handle:
                    total += cred.file_size_bytes()
                    if total > MAX_BYTES:
                        raise ValueError(
                            "Los archivos superan el tamaño máximo del ZIP: acota la selección."
                        )
                    name = _zip_name(cred, used)
                    with zf.open(name, "w") as dest:
                        shutil.copyfileobj(handle, dest, 1024 * 1024)
            rows.append((cred, name or "(archivo no disponible)"))
        zf.writestr("evidencia.xlsx", _workbook(rows))
    ModerationLog.objects.create(
        actor=by, action="export_credentials", object_type="credential", object_id=0,
        summary=f"{len(creds)} credenciales",
    )  # fmt: skip
    buffer.seek(0)
    return buffer, len(creds)


def build_zip(by, creds):
    """Igual que `build_zip_file`, pero devuelve los bytes (solo para pruebas y usos pequeños)."""
    handle, count = build_zip_file(by, creds)
    with handle:
        return handle.read(), count


def filename(today=None):
    return f"evidencia-{(today or date.today()).isoformat()}.zip"
