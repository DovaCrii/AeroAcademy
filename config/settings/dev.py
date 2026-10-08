from .base import *

DEBUG = True
SECRET_KEY = SECRET_KEY or "dev-only-insecure-key-do-not-use-in-production"
ALLOWED_HOSTS = ALLOWED_HOSTS or ["localhost", "127.0.0.1", "[::1]", "testserver"]

# En desarrollo `runserver` sirve los estáticos de cada app; WhiteNoise solo se usa en producción.
MIDDLEWARE = [m for m in MIDDLEWARE if not m.startswith("whitenoise.")]
