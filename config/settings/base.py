import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


SECRET_KEY = os.environ.get("SECRET_KEY", "")
DEBUG = False
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")

PROJECT_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.catalog",
    "apps.paths",
    "apps.progress",
    "apps.community",
    "apps.credentials",
    "apps.team",
    "apps.gamification",
    "apps.notifications",
    "apps.assistant",
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    *PROJECT_APPS,
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Sirve los estáticos (no los certificados). En dev usa los de cada app.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.TailscaleRemoteUserMiddleware",
    "apps.accounts.middleware.ApprovalMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.brand",
                "apps.gamification.context_processors.player",
                "apps.notifications.context_processors.bell",
            ],
        },
    },
]

# SQLite en modo WAL: una sola VM, varios lectores y un escritor (ver docs/ARQUITECTURA.md).
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DATABASE_PATH", str(BASE_DIR / "db.sqlite3")),
        "OPTIONS": {
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
            "transaction_mode": "IMMEDIATE",
        },
    }
}

# Identidad: Tailscale (D2). No hay contraseñas ni login propio.
AUTH_USER_MODEL = "accounts.Person"
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.TailscaleBackend"]
AUTH_PASSWORD_VALIDATORS = []

# Solo estas IP pueden presentar el encabezado Tailscale-User-Login (proxy de `tailscale serve`).
TRUSTED_PROXY_IPS = env_list("TRUSTED_PROXY_IPS", "127.0.0.1,::1")
# Quien figure aquí entra aprobada y como admin (el moderador del proyecto).
BOOTSTRAP_ADMINS = [e.lower() for e in env_list("BOOTSTRAP_ADMINS")]
# Solo para desarrollo: simula la identidad. Se ignora si DEBUG es False.
DEV_REMOTE_USER = os.environ.get("DEV_REMOTE_USER", "").strip().lower()

LANGUAGE_CODE = "es"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = Path(os.environ.get("STATIC_ROOT", str(BASE_DIR / "staticfiles")))
# Los certificados NO se sirven por MEDIA_URL: se entregan por una vista con permisos (AGENTS.md).
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", str(BASE_DIR / "media")))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Avisar de vencimientos con esta anticipación (docs/PRD.md: 60 días).
CREDENTIAL_WARNING_DAYS = int(os.environ.get("CREDENTIAL_WARNING_DAYS", "60"))

# Marca (docs/VISION.md)
BRAND_PLATFORM = "AeroAcademy"
BRAND_ACADEMY = "Academia LEV Digital 101"
