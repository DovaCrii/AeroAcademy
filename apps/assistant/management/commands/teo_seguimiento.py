from django.core.management.base import BaseCommand

from apps.assistant import followup
from apps.core.taskruns import record_run


class Command(BaseCommand):
    help = "Nala avisa (dentro de la app) a quien lleva una semana sin avanzar y resume la semana a los responsables. Tarea semanal."

    def handle(self, *args, **options):
        with record_run("teo_seguimiento") as run:
            nudged, digests = followup.run()
            run.summary = f"{nudged} avisos · {digests} resúmenes a responsables"
        self.stdout.write(
            self.style.SUCCESS(f"Avisos de Nala: {nudged} · resúmenes a responsables: {digests}")
        )
