from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.notifications import services

# Unidad de systemd → nombre que entiende una persona
UNITS = {
    "centro-backup.service": "el respaldo diario",
    "centro-expiry.service": "la revisión de vencimientos",
    "centro-teo.service": "el seguimiento semanal de Teo",
    "centro.service": "el servicio web",
}


class Command(BaseCommand):
    help = "Avisa a los responsables (en la campana) que una tarea programada falló. Lo llama systemd (OnFailure=)."

    def add_arguments(self, parser):
        parser.add_argument(
            "unidad", help="Nombre de la unidad de systemd que falló, p. ej. centro-backup.service"
        )

    def handle(self, *args, unidad, **options):
        unit = unidad.strip()[:80]
        what = UNITS.get(unit, unit)
        today = timezone.localdate().isoformat()
        services.notify_leads(
            "task_failed",
            f"Falló {what}",
            f"Revisa en la VM:  journalctl -u {unit} -n 50",
            url="/moderacion/",
            key=f"fallo:{unit}:{today}",  # un aviso por tarea y día
        )
        self.stdout.write(self.style.WARNING(f"Aviso de fallo enviado: {unit}"))
