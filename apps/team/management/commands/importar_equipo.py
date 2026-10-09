import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.team import onboarding


class Command(BaseCommand):
    help = (
        "Pre-aprueba a todo el equipo desde un CSV (correo, nombre, rol, área/disciplina, cargo). Idempotente: "
        "repetirlo actualiza. Usa --dry-run para ver qué haría sin escribir nada."
    )

    def add_arguments(self, parser):
        parser.add_argument("archivo", help="Ruta del CSV, o - para leer de la entrada estándar.")
        parser.add_argument(
            "--dry-run", action="store_true", help="Valida y muestra, sin escribir."
        )

    def handle(self, *args, archivo, dry_run, **options):
        if archivo == "-":
            text = sys.stdin.read()
        else:
            path = Path(archivo)
            if not path.is_file():
                raise CommandError(f"No existe el archivo: {archivo}")
            text = path.read_text(encoding="utf-8-sig")
        report = onboarding.import_team(text, by=None, dry_run=dry_run)
        if report.fatal:
            raise CommandError(report.fatal)
        for r in report.rows:
            if r.errors:
                self.stdout.write(
                    self.style.ERROR(f"  línea {r.line} · {r.login or '?'}: " + " ".join(r.errors))
                )
            else:
                self.stdout.write(
                    f"  línea {r.line} · {r.login}: {r.action} ({', '.join(r.changes) or 'sin cambios'})"
                )
        head = "SIMULACIÓN (no se escribió nada) · " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{head}{report.count('created')} creadas, {report.count('updated')} actualizadas, "
                f"{report.count('unchanged')} sin cambios, {len(report.errors)} con errores."
            )
        )
        if report.errors and not dry_run:
            raise CommandError("Hubo filas con errores; las válidas sí se aplicaron.")
