from django.core.management.base import BaseCommand

from apps.credentials import expiry


class Command(BaseCommand):
    help = "Avisa de credenciales por vencer o vencidas y recalcula insignias que dependen de la vigencia (tarea diaria)."

    def handle(self, *args, **options):
        soon, gone, people = expiry.notify_all()
        self.stdout.write(
            self.style.SUCCESS(
                f"Por vencer: {soon} · vencidas: {gone} · personas recalculadas: {people}"
            )
        )
