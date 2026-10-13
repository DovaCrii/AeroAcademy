from django.core.management.base import BaseCommand, CommandError

from apps.accounts import team_link


class Command(BaseCommand):
    help = (
        "Genera el enlace de inscripción del equipo (uno para todos; el nuevo revoca el anterior) o lo revoca. "
        "Se ejecuta en la VM; no manda nada. El enlace se imprime una sola vez: la base guarda solo su huella."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dias",
            type=int,
            default=team_link.DEFAULT_DAYS,
            help="Vigencia: 7, 14 o 30 días (por defecto 14).",
        )
        parser.add_argument(
            "--revocar", action="store_true", help="Revoca el enlace vigente, sin generar otro."
        )

    def handle(self, *args, dias, revocar, **options):
        if revocar:
            count = team_link.revoke_active()
            self.stdout.write(
                "Enlace del equipo revocado." if count else "No hay un enlace del equipo vigente."
            )
            return
        try:
            record, token = team_link.create_link(None, dias)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            f"Enlace de inscripción del equipo (vence el {record.expires_at:%d/%m/%Y}, sirve para varias personas):"
        )
        self.stdout.write(team_link.link_url(token))
        self.stdout.write("Mándalo por un canal privado; generar otro revoca este.")
