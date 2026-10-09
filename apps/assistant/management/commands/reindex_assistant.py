from django.core.management.base import BaseCommand

from apps.assistant import search


class Command(BaseCommand):
    help = "Reconstruye el índice de búsqueda de Nala (solo contenido visible para todo el equipo)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(f"Índice reconstruido: {search.reindex()} filas."))
