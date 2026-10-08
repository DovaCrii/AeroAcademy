from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.assistant import client

HINTS = {
    "auth": "La clave fue rechazada (401/403): revisa NIM_API_KEY en /etc/centro/env.",
    "rate": "Límite de la API alcanzado (429): espera un momento o revisa tu plan en build.nvidia.com.",
    "timeout": "La API no respondió a tiempo: sube BOT_TIMEOUT_S o revisa la red de la VM.",
    "network": "No hay conexión con la API: revisa la salida a internet de la VM y NIM_BASE_URL.",
    "http": "La API respondió con error: casi siempre es el nombre de NIM_MODEL. Mira los modelos con --modelos.",
    "bad_response": "La respuesta no tiene el formato esperado: ¿el modelo es de tipo «instruct»?",
}


class Command(BaseCommand):
    help = "Prueba la conexión de Teo con NVIDIA NIM (una llamada corta). Nunca muestra la clave."

    def add_arguments(self, parser):
        parser.add_argument(
            "--modelos",
            action="store_true",
            help="Lista los modelos que ofrece la API, para elegir NIM_MODEL (los «instruct» primero).",
        )

    def handle(self, *args, **options):
        if not settings.BOT_ENABLED:
            raise CommandError("BOT_ENABLED está apagado.")
        if not settings.NIM_API_KEY:
            raise CommandError("Falta NIM_API_KEY (ver deploy/centro.env.plantilla).")
        self.stdout.write(f"Modelo: {settings.NIM_MODEL} · {settings.NIM_BASE_URL}")
        if options["modelos"]:
            return self._models()
        messages = [
            {"role": "system", "content": "Responde en español, en una frase corta."},
            {
                "role": "user",
                "content": "Preséntate como Teo, el asistente de una academia de ingeniería.",
            },
        ]
        try:
            text, tokens, latency = client.chat(messages, max_tokens=80)
        except client.BotError as exc:
            extra = f" HTTP {exc.status}: {exc.detail}." if exc.status else ""
            raise CommandError(f"Falló ({exc.code}).{extra} {HINTS.get(exc.code, '')}") from exc
        self.stdout.write(self.style.SUCCESS(f"OK en {latency} ms · {tokens} tokens"))
        self.stdout.write(f"Respuesta de prueba: {text}")

    def _models(self):
        try:
            models = client.list_models()
        except client.BotError as exc:
            extra = f" HTTP {exc.status}: {exc.detail}." if exc.status else ""
            raise CommandError(
                f"No se pudo listar ({exc.code}).{extra} {HINTS.get(exc.code, '')}"
            ) from exc
        instruct = [m for m in models if "instruct" in m.lower() or "chat" in m.lower()]
        self.stdout.write(f"{len(models)} modelos; {len(instruct)} de tipo instruct/chat:")
        for model in instruct[:60]:
            mark = "  ← el configurado" if model == settings.NIM_MODEL else ""
            self.stdout.write(f"  {model}{mark}")
        if settings.NIM_MODEL not in models:
            self.stdout.write(
                self.style.WARNING(f"NIM_MODEL «{settings.NIM_MODEL}» NO está en la lista.")
            )
            self.stdout.write(
                "Cambia NIM_MODEL en deploy/centro.env (o en /etc/centro/env) y reinicia: sudo systemctl restart centro"
            )
