import csv
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.test import Client
from django.test.utils import override_settings

from apps.accounts.models import Person
from apps.core import linkcheck


class Command(BaseCommand):
    help = (
        "Revisa los enlaces internos del sitio (recorrido como una persona admin, solo GET) y, con --externos, "
        "las URLs externas de los recursos y de seed/. Escribe un CSV en private/. No lo corre el CI."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--externos", action="store_true", help="Revisa también las URLs externas."
        )
        parser.add_argument(
            "--solo-externos", action="store_true", help="Omite el recorrido interno."
        )
        parser.add_argument(
            "--como",
            default="",
            help="Correo de la persona con la que se recorre (admin por defecto).",
        )
        parser.add_argument(
            "--limite", type=int, default=linkcheck.LIMIT, help="Máximo de páginas internas."
        )
        parser.add_argument("--salida", default="", help="Carpeta del CSV (por defecto private/).")

    def handle(self, *args, **options):
        out = Path(options["salida"] or settings.BASE_DIR / "private")
        out.mkdir(parents=True, exist_ok=True)
        stamp = date.today().isoformat()
        broken = []
        if not options["solo_externos"]:
            broken = self._internal(options)
            path = out / f"enlaces_internos_{stamp}.csv"
            self._write(path, ["codigo_url_origen"], [[b] for b in broken])
            self.stdout.write(f"Internos rotos: {len(broken)} (CSV: {path})")
            for line in broken[:50]:
                self.stdout.write(self.style.ERROR(f"  {line}"))
        if options["externos"] or options["solo_externos"]:
            urls = {**linkcheck.seed_urls(settings.BASE_DIR / "seed"), **linkcheck.resource_urls()}
            self.stdout.write(f"Revisando {len(urls)} URLs externas…")
            rows = linkcheck.check_external(urls)
            path = out / f"enlaces_externos_{stamp}.csv"
            self._write(path, ["url", "origen", "codigo", "clase"], rows)
            counts = {}
            for row in rows:
                counts[row[3]] = counts.get(row[3], 0) + 1
            self.stdout.write(f"Externos (CSV: {path}): {counts}")
            for url, origin, _code, kind in rows:
                if kind == "roto":
                    self.stdout.write(self.style.ERROR(f"  404 real: {url}  ({origin})"))
            self.stdout.write(
                "Los «bloqueado» (403/429, p. ej. Autodesk) y «sin_respuesta» (timeout) hay que confirmarlos en un navegador."
            )

    def _internal(self, options):
        people = Person.objects.filter(status="approved")
        person = (
            people.filter(login=options["como"].strip().lower()).first()
            if options["como"]
            else people.filter(is_superuser=True).first()
        )
        if person is None:
            raise CommandError(
                "No hay una persona aprobada (admin) con la que recorrer el sitio. Usa --como."
            )
        client = Client(
            HTTP_HOST="localhost",
            REMOTE_ADDR="127.0.0.1",
            HTTP_TAILSCALE_USER_LOGIN=person.login,
        )
        with override_settings(ALLOWED_HOSTS=["localhost", "testserver"], PUBLIC_DOOR=False):
            _, broken, _ = linkcheck.crawl(client, limit=options["limite"])
        return broken

    @staticmethod
    def _write(path, header, rows):
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
