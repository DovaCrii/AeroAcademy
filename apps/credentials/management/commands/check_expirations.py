from django.core.management.base import BaseCommand

from apps.core.taskruns import record_run
from apps.credentials import expiry


class Command(BaseCommand):
    help = "Avisa de credenciales por vencer o vencidas y recalcula insignias que dependen de la vigencia (tarea diaria)."

    def handle(self, *args, **options):
        with record_run("check_expirations") as run:
            soon, gone, people = expiry.notify_all()
            run.summary = f"{soon} por vencer · {gone} vencidas · {people} personas recalculadas"
        self.stdout.write(
            self.style.SUCCESS(
                f"Por vencer: {soon} · vencidas: {gone} · personas recalculadas: {people}"
            )
        )
