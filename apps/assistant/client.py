"""Cliente de NVIDIA NIM (compatible con OpenAI). Solo hace la llamada: lo que se envía lo decide `context.py`."""

import re
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


_THINK = re.compile(r"<think>.*?(</think>|$)", re.S | re.I)
_UP_TO_CLOSE = re.compile(r"^.*</think>", re.S | re.I)
# Razonamiento sin etiquetas (visto en p340 con Nemotron 3.5: «Here's a thinking process: 1. Analyze…»).
_LEAKED = re.compile(
    r"^\W*(here'?s (a|my) thinking process|thinking process|okay,? (so )?(the user|let me|i need)|let me think"
    r"|we need to|the user (is asking|wants|asks|said)|analy[sz]e the (user|request))",
    re.I,
)
NO_THINK = {
    "chat_template_kwargs": {"enable_thinking": False}
}  # apaga el razonamiento de Nemotron 3 y Qwen 3
_no_think_rejected = (
    set()
)  # modelos que respondieron 400/422 a NO_THINK: se les pregunta sin la opción


def strip_reasoning(text):
    """Los modelos de «razonamiento» (p. ej. Nemotron 3) pueden devolver su pensamiento entre <think>…</think>:
    a la persona solo le llega la respuesta final. Un <think> sin cerrar se descarta entero; un </think> suelto
    (la plantilla abrió el <think> en el prompt) descarta todo lo anterior; y un razonamiento sin etiquetas deja la
    respuesta vacía, para que `chat` pruebe el siguiente modelo."""
    text = _UP_TO_CLOSE.sub("", _THINK.sub("", text)).strip()
    return "" if _LEAKED.match(text) else text


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
            # Modelo retirado, o respuesta inservible (vacía o solo razonamiento): se prueba el siguiente.
            gone = (exc.code == "http" and exc.status in MODEL_GONE) or exc.code == "bad_response"
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
    with_option = model not in _no_think_rejected
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": max_tokens,
        **(NO_THINK if with_option else {}),
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
    if response.status_code in (400, 422) and with_option:
        _no_think_rejected.add(
            model
        )  # el modelo no acepta la opción: se repite la pregunta sin ella
        return _chat_once(model, messages, max_tokens)
    if response.status_code >= 400:
        raise BotError("http", response.status_code, _error_detail(response))
    try:
        data = response.json()
        text = data["choices"][0]["message"]["content"]
        tokens = int(data.get("usage", {}).get("total_tokens", 0))
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise BotError("bad_response") from exc
    if isinstance(text, str):
        text = strip_reasoning(text)
    if not isinstance(text, str) or not text.strip():
        raise BotError("bad_response")
    last_model = model
    return text.strip(), tokens, latency
