from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.seeding import SeedError
from apps.dgac import constants, data
from apps.paths.seeding import load_route


class _DryRun(Exception):
    """Para deshacer la transacción al final de un --dry-run."""


class Command(BaseCommand):
    help = (
        "Carga la ruta «Diploma interno RPAS» desde DGAC_DATA_DIR/ruta.json (contenido privado de JEJ). "
        "Requiere haber corrido seed_catalog. Es idempotente."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Valida y simula; no guarda.")

    def handle(self, *args, **options):
        folder = data.data_dir()
        try:
            route = data.read_json(constants.FILE_ROUTE)
        except data.DataError as exc:
            raise CommandError(str(exc)) from exc
        if route is None:
            self.stdout.write(
                self.style.WARNING(
                    f"No hay {constants.FILE_ROUTE} en {folder}: el contenido DGAC no está instalado. "
                    "Copia la carpeta privada (ver DGAC_DATA_DIR) y vuelve a correr el comando."
                )
            )
            return
        if route.get("slug") != constants.ROUTE_SLUG:
            raise CommandError(
                f"{constants.FILE_ROUTE}: el slug debe ser «{constants.ROUTE_SLUG}»."
            )
        try:
            with transaction.atomic():
                path = load_route(route, name=constants.FILE_ROUTE)
                if options["dry_run"]:
                    raise _DryRun
        except _DryRun:
            path = None
        except SeedError as exc:
            for error in exc.errors:
                self.stderr.write(self.style.ERROR(f"✗ {error}"))
            raise CommandError(f"{len(exc.errors)} error(es) en {constants.FILE_ROUTE}.") from exc
        levels = len(route["levels"])
        missions = sum(len(lv.get("milestones", [])) for lv in route["levels"])
        quiz = sum(len(lv.get("quiz", [])) for lv in route["levels"])
        prefix = "[dry-run] " if path is None else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Ruta {route['slug']}: {levels} niveles, {missions} misiones, {quiz} preguntas."
            )
        )
        bank = len(data.load_bank())
        self.stdout.write(f"Banco de preguntas: {bank or 'no instalado'}.")
