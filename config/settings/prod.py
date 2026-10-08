import os

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

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Defensa extra: nunca se acepta identidad simulada en producción.
DEV_REMOTE_USER = ""
