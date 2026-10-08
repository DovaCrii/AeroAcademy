from django.core.management.base import BaseCommand

from apps.assistant import followup


class Command(BaseCommand):
    help = "Teo avisa (dentro de la app) a quien lleva una semana sin avanzar y resume la semana a los responsables. Tarea semanal."

    def handle(self, *args, **options):
        nudged, digests = followup.run()
        self.stdout.write(
            self.style.SUCCESS(f"Avisos de Teo: {nudged} · resúmenes a responsables: {digests}")
        )
