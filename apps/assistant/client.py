"""Cliente de NVIDIA NIM (compatible con OpenAI). Solo hace la llamada: lo que se envía lo decide `context.py`."""

import time

import httpx
from django.conf import settings

MODEL_GONE = {404, 410}  # el modelo ya no existe (p. ej. fin de vida): se prueba el siguiente
last_model = ""  # modelo que respondió la última vez (para el diagnóstico)
TRANSPORT = None  # las pruebas inyectan un httpx.MockTransport


class BotError(Exception):
    """Falla de la API. `code`: timeout | auth | rate | http | bad_response | network."""

    def __init__(self, code, status=None, detail=""):
        super().__init__(code)
        self.code = code
        self.status = status  # código HTTP de la API, si lo hubo
        self.detail = detail  # mensaje de error de la API (nunca incluye lo que se envió)


def _error_detail(response):
    """Mensaje corto de error de la API para diagnosticar (no se guarda en el log de Teo)."""
    try:
        data = response.json()
    except ValueError:
        return response.text[:200].strip()
    if isinstance(data, dict):
        error = data.get("error")
        for candidate in (
            data.get("detail"),
            data.get("message"),
            error.get("message") if isinstance(error, dict) else error,
            data.get("title"),
        ):
            if candidate:
                return str(candidate)[:200]
    return ""


def list_models():
    """Identificadores de modelos que ofrece la API (para elegir NIM_MODEL)."""
    headers = {"Authorization": f"Bearer {settings.NIM_API_KEY}"}
    try:
        with httpx.Client(timeout=settings.BOT_TIMEOUT_S, transport=TRANSPORT) as http:
            response = http.get(f"{settings.NIM_BASE_URL}/models", headers=headers)
    except httpx.TimeoutException as exc:
        raise BotError("timeout") from exc
    except httpx.HTTPError as exc:
        raise BotError("network") from exc
    if response.status_code in (401, 403):
        raise BotError("auth", response.status_code)
    if response.status_code >= 400:
        raise BotError("http", response.status_code, _error_detail(response))
    try:
        return sorted(m["id"] for m in response.json()["data"])
    except (ValueError, KeyError, TypeError) as exc:
        raise BotError("bad_response") from exc


def is_configured() -> bool:
    return bool(settings.BOT_ENABLED and settings.NIM_API_KEY)


def chat(messages, *, max_tokens=500):
    """Devuelve (texto, tokens, latencia_ms). Lanza BotError con un código, sin exponer la clave ni el contenido."""
    models = [
        settings.NIM_MODEL,
        *[m for m in settings.NIM_MODEL_FALLBACKS if m != settings.NIM_MODEL],
    ]
    tried = []
    for index, model in enumerate(models):
        try:
            return _chat_once(model, messages, max_tokens)
        except BotError as exc:
            gone = exc.code == "http" and exc.status in MODEL_GONE
            tried.append(f"{model} → HTTP {exc.status}" if exc.status else f"{model} → {exc.code}")
            if not gone or index == len(models) - 1:
                if len(tried) > 1:
                    exc.detail = f"{exc.detail} (probados: {'; '.join(tried)})"
                raise
    raise BotError("http")  # inalcanzable: el bucle siempre retorna o lanza


def chat_with(model, messages, *, max_tokens=500):
    """Una llamada a un modelo concreto, sin respaldos (para buscar modelos que respondan)."""
    return _chat_once(model, messages, max_tokens)


def _chat_once(model, messages, max_tokens):
    global last_model
    payload = {
        "model": model,
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
        raise BotError("http", response.status_code, _error_detail(response))
    try:
        data = response.json()
        text = data["choices"][0]["message"]["content"]
        tokens = int(data.get("usage", {}).get("total_tokens", 0))
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise BotError("bad_response") from exc
    if not isinstance(text, str) or not text.strip():
        raise BotError("bad_response")
    last_model = model
    return text.strip(), tokens, latency
