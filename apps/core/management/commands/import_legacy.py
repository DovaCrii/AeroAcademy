from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core import legacy


class _DryRun(Exception):
    pass


class Command(BaseCommand):
    help = "Importa personas, avance, notas y casillas compartidas desde el ruta.db del prototipo (idempotente)."

    def add_arguments(self, parser):
        parser.add_argument("--db", required=True, help="Ruta al ruta.db del prototipo.")
        parser.add_argument(
            "--path", default="forma-revit", help="Slug de la ruta que recibe los datos."
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Simula y deshace todo al final."
        )

    def handle(self, *args, **options):
        summary = {}
        try:
            with transaction.atomic():
                summary = legacy.import_legacy(options["db"], path_slug=options["path"])
                if options["dry_run"]:
                    raise _DryRun
        except _DryRun:
            pass
        except legacy.LegacyError as exc:
            raise CommandError(str(exc)) from exc
        prefix = "[dry-run] " if options["dry_run"] else ""
        skipped = summary.pop("skipped")
        self.stdout.write(self.style.SUCCESS(f"{prefix}Importado: {summary}"))
        for line in skipped[:50]:
            self.stdout.write(self.style.WARNING(f"  omitido: {line}"))
        if len(skipped) > 50:
            self.stdout.write(self.style.WARNING(f"  … y {len(skipped) - 50} omitidos más"))
