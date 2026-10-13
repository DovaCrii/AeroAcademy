"""Contador de intentos sobre la caché compartida (D36).

Con varios workers de gunicorn (y dos servicios) la caché tiene que vivir fuera del proceso: `CACHES` usa
`FileBasedCache` en producción. Las operaciones de archivo no son atómicas, así que dos intentos simultáneos pueden
contarse como uno; el límite real es «cerca de N», suficiente para frenar adivinación de contraseñas y códigos.
"""

import hashlib

from django.core.cache import cache


def _key(scope: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]
    return f"rl:{scope}:{digest}"


def blocked(scope: str, *parts: str, limit: int) -> bool:
    return cache.get(_key(scope, *parts), 0) >= limit


def hit(scope: str, *parts: str, window: int) -> None:
    key = _key(scope, *parts)
    if cache.add(key, 1, window):
        return
    try:
        cache.incr(key)
    except ValueError:  # venció entre add e incr
        cache.add(key, 1, window)


def clear(scope: str, *parts: str) -> None:
    cache.delete(_key(scope, *parts))
