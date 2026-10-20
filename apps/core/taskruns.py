"""Registro de ejecuciones de tareas (D42). Los comandos de gestión lo usan así:

    with record_run("check_expirations") as run:
        ...                                   # el trabajo de siempre, sin cambios
        run.summary = f"{n} avisos"           # solo cifras: nada de nombres ni correos

Guardar el registro NUNCA hace fallar la tarea (un error al escribir se anota y se sigue), y si la tarea lanza una
excepción queda `ok=False` y la excepción se propaga igual: systemd sigue viendo el fallo y `avisar_fallo` sigue
avisando a los responsables.
"""

import logging
import re
from contextlib import contextmanager

from django.db import transaction
from django.utils import timezone

from .models import TaskRun

logger = logging.getLogger("apps.core")

SUMMARY_MAX = 200
_EMAIL = re.compile(r"\S+@\S+")


class Run:
    """Lo que la tarea puede dejar dicho al terminar."""

    summary = ""


def _clean(text: str) -> str:
    """Resumen de una línea, sin correos por si algún día se cuela uno, de 200 caracteres como máximo."""
    return _EMAIL.sub("…", " ".join((text or "").split()))[:SUMMARY_MAX]


def _write(name: str, **fields) -> None:
    try:
        with transaction.atomic():
            TaskRun.objects.update_or_create(name=name, defaults=fields)
    except Exception as exc:  # noqa: BLE001 - el registro es un extra: no puede romper la tarea
        logger.warning(
            "No se pudo guardar el registro de la tarea %s (%s)", name, type(exc).__name__
        )


@contextmanager
def record_run(name: str, *, enabled: bool = True):
    """Registra el inicio y el final de una tarea. `enabled=False` (p. ej. un --dry-run) no registra nada."""
    run = Run()
    if not enabled:
        yield run
        return
    _write(name, started_at=timezone.now(), finished_at=None, ok=None, summary="")
    try:
        yield run
    except BaseException as exc:
        failed = f"Falló ({type(exc).__name__})." + (f" {run.summary}" if run.summary else "")
        _write(name, finished_at=timezone.now(), ok=False, summary=_clean(failed))
        raise
    _write(name, finished_at=timezone.now(), ok=True, summary=_clean(run.summary))
