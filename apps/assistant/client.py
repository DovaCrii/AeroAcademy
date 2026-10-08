"""Cliente de NVIDIA NIM (compatible con OpenAI). Solo hace la llamada: lo que se envía lo decide `context.py`."""

import time

import httpx
from django.conf import settings

TRANSPORT = None  # las pruebas inyectan un httpx.MockTransport


class BotError(Exception):
    """Falla de la API. `code`: timeout | auth | rate | http | bad_response | network."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def is_configured() -> bool:
    return bool(settings.BOT_ENABLED and settings.NIM_API_KEY)


def chat(messages, *, max_tokens=500):
    """Devuelve (texto, tokens, latencia_ms). Lanza BotError con un código, sin exponer la clave ni el contenido."""
    payload = {
        "model": settings.NIM_MODEL,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {settings.NIM_API_KEY}",
        "Content-Type": "application/json",
    }
    started = time.monotonic()
    try:
        with httpx.Client(timeout=settings.BOT_TIMEOUT_S, transport=TRANSPORT) as http:
            response = http.post(
                f"{settings.NIM_BASE_URL}/chat/completions", json=payload, headers=headers
            )
    except httpx.TimeoutException as exc:
        raise BotError("timeout") from exc
    except httpx.HTTPError as exc:
        raise BotError("network") from exc
    latency = int((time.monotonic() - started) * 1000)
    if response.status_code in (401, 403):
        raise BotError("auth")
    if response.status_code == 429:
        raise BotError("rate")
    if response.status_code >= 400:
        raise BotError("http")
    try:
        data = response.json()
        text = data["choices"][0]["message"]["content"]
        tokens = int(data.get("usage", {}).get("total_tokens", 0))
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise BotError("bad_response") from exc
    if not isinstance(text, str) or not text.strip():
        raise BotError("bad_response")
    return text.strip(), tokens, latency
