from django.core.management.base import BaseCommand, CommandError

from apps.accounts import services
from apps.accounts.models import Person


class Command(BaseCommand):
    help = (
        "Imprime un enlace de registro (de un solo uso, 7 días) para una persona ya aprobada. Sirve también para "
        "restablecer una contraseña: el enlace nuevo invalida el anterior. Se ejecuta en la VM; no manda nada."
    )

    def add_arguments(self, parser):
        parser.add_argument("email", help="Correo (login) de la persona, ya aprobada.")

    def handle(self, *args, email, **options):
        login = services.normalize_login(email)
        person = Person.objects.filter(login=login).first() if "@" in login else None
        if person is None:
            raise CommandError(
                "No hay una persona con ese correo. Créala con `manage.py aprobar <correo>`."
            )
        try:
            url = services.signup_url(person)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"Enlace de registro para {person.login} (un solo uso, vence en 7 días):")
        self.stdout.write(url)
        self.stdout.write("Mándaselo por un canal privado; generar otro invalida este.")
