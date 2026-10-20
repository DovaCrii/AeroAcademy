import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.seeding import SeedError
from apps.core.taskruns import record_run
from apps.paths.seeding import load_route


class _DryRun(Exception):
    """Para deshacer la transacción al final de un --dry-run."""


class Command(BaseCommand):
    help = (
        "Carga las rutas privadas de JEJ desde PRIVATE_COURSES_DIR/<slug>/ruta.json (carpeta fuera de git). "
        "Requiere haber corrido seed_catalog. Es idempotente."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Valida y simula; no guarda.")

    def handle(self, *args, **options):
        with record_run("cargar_cursos_privados", enabled=not options["dry_run"]) as run:
            self._load(options, run)

    def _load(self, options, run):
        root = settings.PRIVATE_COURSES_DIR
        run.summary = "Carpeta no instalada"
        if not root.is_dir():
            self.stdout.write(
                self.style.WARNING(
                    f"No existe la carpeta {root}: no hay cursos privados instalados. "
                    "Copia la carpeta privada (ver PRIVATE_COURSES_DIR) y vuelve a correr el comando."
                )
            )
            return
        dry = options["dry_run"]
        prefix = "[dry-run] " if dry else ""
        loaded, errors = 0, 0
        for folder in sorted(p for p in root.iterdir() if p.is_dir()):
            file = folder / "ruta.json"
            if not file.is_file():
                continue  # carpeta sin ruta (por ejemplo, solo fotos/): se ignora
            label = f"{folder.name}/ruta.json"
            try:
                route = json.loads(file.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                self.stderr.write(self.style.ERROR(f"✗ {label}: no se pudo leer el JSON ({exc})."))
                errors += 1
                continue
            if not isinstance(route, dict) or route.get("slug") != folder.name:
                self.stderr.write(
                    self.style.ERROR(
                        f"✗ {label}: el slug debe ser igual al nombre de la carpeta «{folder.name}»."
                    )
                )
                errors += 1
                continue
            try:
                with transaction.atomic():
                    load_route(route, name=label)
                    if dry:
                        raise _DryRun
            except _DryRun:
                pass
            except SeedError as exc:
                for error in exc.errors:
                    self.stderr.write(self.style.ERROR(f"✗ {error}"))
                errors += 1
                continue
            levels = route["levels"]
            self.stdout.write(
                self.style.SUCCESS(
                    f"{prefix}Ruta {route['slug']}: {len(levels)} niveles, "
                    f"{sum(len(lv.get('milestones', [])) for lv in levels)} misiones, "
                    f"{sum(len(lv.get('quiz', [])) for lv in levels)} preguntas."
                )
            )
            loaded += 1
        run.summary = f"{loaded} rutas cargadas · {errors} con errores"
        if errors:
            raise CommandError(f"{errors} ruta(s) privada(s) con errores; {loaded} sin errores.")
        if not loaded:
            self.stdout.write(self.style.WARNING(f"No hay rutas privadas (ruta.json) en {root}."))
