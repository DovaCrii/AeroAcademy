"""TOTP (RFC 6238) con la biblioteca estándar: sin dependencias nuevas (D36).

Solo SHA-1, 6 dígitos y paso de 30 s: es lo que entienden Google Authenticator, Microsoft Authenticator, Aegis,
1Password, etc. La comparación es en tiempo constante y `verify` devuelve el contador aceptado para que quien llama
pueda rechazar un código ya usado (repetición).
"""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote, urlencode

STEP_SECONDS = 30
DIGITS = 6
WINDOW = 1  # un paso hacia atrás y uno hacia adelante: tolera relojes algo desajustados


def new_secret() -> str:
    """Secreto de 160 bits en base32 (sin relleno), listo para escribir en la app."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _key(secret: str) -> bytes:
    cleaned = secret.replace(" ", "").upper()
    return base64.b32decode(cleaned + "=" * (-len(cleaned) % 8))


def hotp(secret: str, counter: int, digits: int = DIGITS) -> str:
    digest = hmac.new(_key(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(number % 10**digits).zfill(digits)


def counter_for(moment: float | None = None) -> int:
    return int((time.time() if moment is None else moment) // STEP_SECONDS)


def code_at(secret: str, moment: float | None = None, digits: int = DIGITS) -> str:
    return hotp(secret, counter_for(moment), digits)


def clean_code(raw: str) -> str:
    """Quita espacios y guiones («123 456» → «123456»). Cualquier otra cosa no es un código."""
    return "".join((raw or "").split()).replace("-", "")


def verify(
    secret: str, raw: str, *, moment: float | None = None, after_counter: int = 0
) -> int | None:
    """Contador del paso que coincide, o None. `after_counter` descarta pasos ya usados."""
    code = clean_code(raw)
    if len(code) != DIGITS or not code.isdigit():
        return None
    now = counter_for(moment)
    matched = None
    for counter in range(now - WINDOW, now + WINDOW + 1):  # sin cortar antes: tiempo constante
        if hmac.compare_digest(hotp(secret, counter), code) and counter > after_counter:
            matched = counter
    return matched


def otpauth_uri(secret: str, account: str, issuer: str = "AeroAcademy") -> str:
    label = quote(f"{issuer}:{account}", safe="")
    query = urlencode({"secret": secret, "issuer": issuer, "algorithm": "SHA1", "digits": DIGITS})
    return f"otpauth://totp/{label}?{query}"


def group(secret: str) -> str:
    """El secreto en grupos de 4 para leerlo y teclearlo."""
    return " ".join(secret[i : i + 4] for i in range(0, len(secret), 4))
