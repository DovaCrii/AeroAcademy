import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .base import *

DEBUG = False

if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY es obligatoria en producción.")
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS es obligatoria en producción (nombre MagicDNS).")

# Detrás de `tailscale serve` (HTTPS terminado en el proxy local).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# Con un puerto HTTPS propio en la tailnet (VM compartida) el navegador envía el origen con ese puerto.
PUBLIC_HTTPS_PORT = int(os.environ.get("PUBLIC_HTTPS_PORT", "443"))
_PORT_SUFFIX = "" if PUBLIC_HTTPS_PORT == 443 else f":{PUBLIC_HTTPS_PORT}"
CSRF_TRUSTED_ORIGINS = [
    f"https://{host}{_PORT_SUFFIX}" for host in ALLOWED_HOSTS if not host.startswith(".")
]
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Los límites de intentos necesitan una caché que vean todos los workers: en producción siempre de archivos.
if not CACHE_DIR:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
            "LOCATION": str(Path(MEDIA_ROOT).parent / "cache"),
            "TIMEOUT": 3600,
        }
    }

# Puerta pública (D36): el Funnel siempre llega por el 443 del nodo. El origen de los formularios es ese, sin puerto.
if PUBLIC_DOOR:
    FUNNEL_HTTPS_PORT = int(os.environ.get("FUNNEL_HTTPS_PORT", "443"))
    _FUNNEL_SUFFIX = "" if FUNNEL_HTTPS_PORT == 443 else f":{FUNNEL_HTTPS_PORT}"
    CSRF_TRUSTED_ORIGINS = [
        f"https://{host}{_FUNNEL_SUFFIX}" for host in ALLOWED_HOSTS if not host.startswith(".")
    ]
    # Cookies propias: el nodo comparte el nombre de host con la puerta de la tailnet (las cookies no distinguen puertos).
    SESSION_COOKIE_NAME = "aa_public_sid"
    CSRF_COOKIE_NAME = "aa_public_csrf"
    SESSION_COOKIE_AGE = 60 * 60 * 24 * 7
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Defensa extra: nunca se acepta identidad simulada en producción.
DEV_REMOTE_USER = ""
