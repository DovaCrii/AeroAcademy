from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.assistant import client

HINTS = {
    "auth": "La clave fue rechazada (401/403): revisa NIM_API_KEY en /etc/centro/env.",
    "rate": "Límite de la API alcanzado (429): espera un momento o revisa tu plan en build.nvidia.com.",
    "timeout": "La API no respondió a tiempo: sube BOT_TIMEOUT_S o revisa la red de la VM.",
    "network": "No hay conexión con la API: revisa la salida a internet de la VM y NIM_BASE_URL.",
    "http": "La API respondió con error: revisa que NIM_MODEL exista en el catálogo de NIM.",
    "bad_response": "La respuesta no tiene el formato esperado: ¿el modelo es de tipo «instruct»?",
}


class Command(BaseCommand):
    help = "Prueba la conexión de Teo con NVIDIA NIM (una llamada corta). Nunca muestra la clave."

    def handle(self, *args, **options):
        if not settings.BOT_ENABLED:
            raise CommandError("BOT_ENABLED está apagado.")
        if not settings.NIM_API_KEY:
            raise CommandError("Falta NIM_API_KEY (ver deploy/centro.env.plantilla).")
        self.stdout.write(f"Modelo: {settings.NIM_MODEL} · {settings.NIM_BASE_URL}")
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
            raise CommandError(f"Falló ({exc.code}). {HINTS.get(exc.code, '')}") from exc
        self.stdout.write(self.style.SUCCESS(f"OK en {latency} ms · {tokens} tokens"))
        self.stdout.write(f"Respuesta de prueba: {text}")
