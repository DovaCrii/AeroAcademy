from django.core.management.base import BaseCommand

from apps.assistant import search
from apps.core.taskruns import record_run


class Command(BaseCommand):
    help = "Reconstruye el índice de búsqueda de Nala (solo contenido visible para todo el equipo)."

    def handle(self, *args, **options):
        with record_run("reindex_assistant") as run:
            rows = search.reindex()
            run.summary = f"{rows} filas"
        self.stdout.write(self.style.SUCCESS(f"Índice reconstruido: {rows} filas."))
