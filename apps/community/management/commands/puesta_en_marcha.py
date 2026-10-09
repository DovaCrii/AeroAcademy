from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts import services as accounts
from apps.accounts.models import Person, PersonStatus
from apps.assistant import client
from apps.community import forum, moderation
from apps.community.models import Category, Thread
from apps.paths.models import LearningPath

WELCOME_TITLE = "Bienvenida a la Academia LEV Digital 101: cómo empezar"
WELCOME_BODY = """¡Hola, gremio! Este es el punto de partida de la academia.

**Tus primeros pasos**

1. Completa tu **hoja de personaje** (Perfil → Editar): titular, disciplina y clase. Ganas tu primera insignia.
2. Elige una **ruta** y marca tu primera misión: Forma + Revit (Arquitectura) o la ruta Bentley (Civil).
3. ¿Ya tienes certificados? Súbelos en **Certificados**. Un responsable los verifica y ahí llega el XP grande.
4. Preséntate respondiendo este hilo: quién eres, en qué disciplina trabajas y qué te gustaría aprender.

**Cuando tengas dudas**

- Pregúntale a **Teo** (el teodolito de la esquina): conoce las rutas, las notas y el foro.
- Abre una **consulta** en la categoría que corresponda; la mejor respuesta se marca como aceptada.
- Los certificados son privados: solo los ven tú y los responsables, y nunca se envían a Teo.

¡Nos vemos en las rutas!"""


class Command(BaseCommand):
    help = (
        "Deja la academia lista para el primer día: hilo de bienvenida fijado en el foro (una sola vez) y una "
        "lista de lo que falta revisar. Se puede repetir sin duplicar nada."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--autor",
            default="",
            help="Login de quien firma la bienvenida (por defecto, el primero de BOOTSTRAP_ADMINS).",
        )

    def handle(self, *args, autor, **options):
        login = autor or (settings.BOOTSTRAP_ADMINS[0] if settings.BOOTSTRAP_ADMINS else "")
        if not login:
            raise CommandError(
                "Indica --autor <login> o define BOOTSTRAP_ADMINS en /etc/centro/env."
            )
        try:
            author, _ = accounts.grant_access(login, "admin")
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self._welcome(author)
        self._checklist()

    def _welcome(self, author):
        if Thread.objects.filter(title=WELCOME_TITLE).exists():
            self.stdout.write("Hilo de bienvenida: ya existe.")
            return
        category = Category.objects.filter(slug="general", retired=False).first()
        if category is None:
            raise CommandError(
                "Falta la categoría «general» del foro: corre antes  manage.py seed_catalog"
            )
        thread = forum.create_thread(
            author, category, Thread.Kind.DISCUSSION, WELCOME_TITLE, WELCOME_BODY
        )
        moderation.pin(thread, author)
        self.stdout.write(
            self.style.SUCCESS(f"Hilo de bienvenida creado y fijado: /foro/{thread.pk}/")
        )

    def _checklist(self):
        ok, warn = self.style.SUCCESS("✔"), self.style.WARNING("!")
        self.stdout.write("\nLista de puesta en marcha:")
        for login in settings.BOOTSTRAP_ADMINS:
            person = Person.objects.filter(login=login).first()
            entered = person is not None and person.last_login is not None
            mark = ok if entered else warn
            note = "ya entró" if entered else "aún no entra por Tailscale con ese correo"
            self.stdout.write(f"  {mark} admin {login}: {note}")
        pending = Person.objects.filter(status=PersonStatus.PENDING).count()
        mark = ok if not pending else warn
        self.stdout.write(f"  {mark} personas esperando aprobación: {pending}  (manage.py aprobar)")
        published = LearningPath.objects.filter(is_published=True).count()
        self.stdout.write(f"  {ok if published else warn} rutas publicadas: {published}")
        if client.is_configured():
            self.stdout.write(
                f"  {ok} Teo despierto con {settings.NIM_MODEL}  (prueba: manage.py teo_probar)"
            )
        else:
            self.stdout.write(f"  {warn} Teo dormido: falta NIM_API_KEY o BOT_ENABLED")
