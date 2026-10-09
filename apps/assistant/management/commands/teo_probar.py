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
            "--buscar",
            action="store_true",
            help="Prueba de verdad los modelos instruct (una llamada corta a cada uno) hasta encontrar los que responden con esta cuenta.",
        )
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
        if options["buscar"]:
            return self._search()
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
        self.stdout.write(
            self.style.SUCCESS(f"OK en {latency} ms · {tokens} tokens · modelo {client.last_model}")
        )
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

    def _search(self, wanted=3):
        """La lista de NIM trae modelos que la cuenta no puede usar («Function not found for account»): se prueban."""
        try:
            models = client.list_models()
        except client.BotError as exc:
            raise CommandError(
                f"No se pudo listar ({exc.code}). {HINTS.get(exc.code, '')}"
            ) from exc
        # Los modelos vigentes de NIM ya no siempre dicen «instruct» (p. ej. nemotron-3-super, qwen3.5, gemma-4-it):
        # se prueban todos menos los que claramente no conversan.
        candidates = [m for m in models if not any(skip in m.lower() for skip in SKIP)]
        ranked = sorted(
            candidates,
            key=lambda m: (
                min((i for i, p in enumerate(PREFERRED) if p in m.lower()), default=len(PREFERRED)),
                m,
            ),
        )[:MAX_PROBES]
        self.stdout.write(f"Probando hasta {len(ranked)} modelos de conversación…")
        probe = [{"role": "user", "content": "Responde solo: hola"}]
        working = []
        for model in ranked:
            try:
                _, _, latency = client.chat_with(model, probe, max_tokens=5)
            except client.BotError as exc:
                self.stdout.write(f"  ✘ {model}  ({exc.status or exc.code})")
                continue
            self.stdout.write(self.style.SUCCESS(f"  ✔ {model}  ({latency} ms)"))
            working.append(model)
            if len(working) >= wanted:
                break
        if not working:
            raise CommandError(
                "Ningún modelo de conversación respondió con esta cuenta. Revisa en build.nvidia.com que la clave sea de la API y que tengas créditos o modelos con «Free Endpoint»; crea una clave nueva si hace falta."
            )
        self.stdout.write(
            "\nPon esto en deploy/centro.env (o en /etc/centro/env) y reinicia con  sudo systemctl restart centro :"
        )
        self.stdout.write(f"NIM_MODEL={working[0]}")
        self.stdout.write(f"NIM_MODEL_FALLBACKS={','.join(working[1:])}")


# Orden de preferencia (buen español y tamaño) y modelos que no sirven para conversar.
PREFERRED = [
    "nemotron-3-super",
    "nemotron-3.5",
    "nemotron-3-ultra",
    "qwen3.5",
    "kimi-k2",
    "gemma-4",
    "qwen3",
    "llama-3.3",
    "llama-3.1-70b",
    "mistral-large",
    "nemotron-70b",
    "nemotron",
    "deepseek",
    "gpt-oss",
    "mixtral",
    "mistral",
    "llama",
]
SKIP = [
    "vision", "code", "coder", "translate", "guard", "safety", "reward", "embed", "rerank", "retriever", "parakeet",
    "riva", "canary", "whisper", "tts", "asr", "clip", "flux", "sdxl", "stable-diffusion", "cosmos", "esm", "msa",
    "bge", "nv-embed", "detector", "pii", "ocr", "paligemma", "vila", "neva", "deplot", "kosmos", "fuyu", "audio",
]  # fmt: skip
MAX_PROBES = 40
