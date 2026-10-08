import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.seeding import SeedError, load_catalog
from apps.community.seeding import load_forum
from apps.gamification.seeding import load_game
from apps.paths.seeding import load_route


class _DryRun(Exception):
    """Para deshacer la transacción al final de un --dry-run."""


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        raise CommandError(f"{path.name}: JSON inválido ({exc})") from exc


class Command(BaseCommand):
    help = "Carga plataformas, vendors, habilidades y rutas desde seed/ (idempotente)."

    def add_arguments(self, parser):
        parser.add_argument("--seed-dir", default=str(settings.BASE_DIR / "seed"))
        parser.add_argument(
            "--dry-run", action="store_true", help="Valida y simula; no guarda nada."
        )

    def handle(self, *args, **options):
        seed_dir = Path(options["seed_dir"])
        if not seed_dir.is_dir():
            raise CommandError(f"No existe la carpeta de semillas: {seed_dir}")
        dry = options["dry_run"]

        try:
            with transaction.atomic():
                counts = load_catalog(
                    _read(seed_dir / "vendors.json"),
                    _read(seed_dir / "plataformas.json"),
                    _read(seed_dir / "skills.json"),
                )
                game = load_game(
                    _read(seed_dir / "insignias.json"), _read(seed_dir / "titulos.json")
                )
                forum = load_forum(_read(seed_dir / "foro.json"))
                paths = []
                for file in sorted((seed_dir / "rutas").glob("*.json")):
                    paths.append(load_route(_read(file), name=file.name).slug)
                if dry:
                    raise _DryRun
        except _DryRun:
            pass
        except SeedError as exc:
            for error in exc.errors:
                self.stderr.write(self.style.ERROR(f"✗ {error}"))
            raise CommandError(f"{len(exc.errors)} error(es) en las semillas.") from exc

        prefix = "[dry-run] " if dry else ""
        self.stdout.write(self.style.SUCCESS(f"{prefix}Catálogo: {counts}"))
        self.stdout.write(self.style.SUCCESS(f"{prefix}Rutas: {', '.join(paths) or '—'}"))
        self.stdout.write(self.style.SUCCESS(f"{prefix}Juego: {game}"))
        self.stdout.write(self.style.SUCCESS(f"{prefix}Foro: {forum}"))
