from django.core.management.base import BaseCommand, CommandError

from apps.accounts import services
from apps.accounts.models import Person, PersonStatus


class Command(BaseCommand):
    help = (
        "Aprueba a una persona (y le da un rol) desde la consola de la VM. Sirve también antes de que entre por "
        "primera vez. Sin login, lista quién espera aprobación."
    )

    def add_arguments(self, parser):
        parser.add_argument("logins", nargs="*", help="Login de Tailscale (correo), uno o varios.")
        parser.add_argument(
            "--rol",
            default="member",
            choices=services.ROLES,
            help="Rol que queda (por defecto member).",
        )

    def handle(self, *args, logins, rol, **options):
        if not logins:
            pending = Person.objects.filter(status=PersonStatus.PENDING).order_by("created_at")
            if not pending:
                self.stdout.write("Nadie espera aprobación.")
            for person in pending:
                self.stdout.write(
                    f"  {person.login}  ({person.name}, desde {person.created_at:%d/%m %H:%M})"
                )
            self.stdout.write("Aprueba con:  manage.py aprobar <login> [--rol member|lead|admin]")
            return
        for login in logins:
            try:
                person, created = services.grant_access(login, rol)
            except ValueError as exc:
                raise CommandError(str(exc)) from exc
            state = "creada y aprobada (aún no entra)" if created else "aprobada"
            self.stdout.write(self.style.SUCCESS(f"{person.login}: {state} · rol {person.role}"))
