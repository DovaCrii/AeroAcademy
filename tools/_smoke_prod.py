"""Humo de producción: arranca Django con config.settings.prod (variables ya puestas por preflight.py) y recorre lo esencial."""

import os
import sys

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.prod"
sys.path.insert(0, os.getcwd())

import django  # noqa: E402

django.setup()

from django.core.management import call_command  # noqa: E402
from django.test import Client  # noqa: E402

HOST = os.environ["ALLOWED_HOSTS"].split(",")[0]
ADMIN = os.environ["BOOTSTRAP_ADMINS"].split(",")[0]
errors = []


def check(name, condition, detail=""):
    print(
        ("  ✔ " if condition else "  ✘ ")
        + name
        + (f" ({detail})" if detail and not condition else "")
    )
    if not condition:
        errors.append(name)


call_command("migrate", verbosity=0)
call_command("seed_catalog", verbosity=0)
call_command("reindex_assistant", verbosity=0)

proxy = Client(REMOTE_ADDR="127.0.0.1", HTTP_HOST=HOST, HTTP_X_FORWARDED_PROTO="https")
header = {"HTTP_TAILSCALE_USER_LOGIN": ADMIN, "HTTP_TAILSCALE_USER_NAME": "Admin de prueba"}

r = proxy.get("/healthz", HTTP_HOST=HOST)
check(
    "/healthz responde desde el proxy local con el host permitido",
    r.status_code == 200,
    r.status_code,
)
check("sin identidad, la portada pide Tailscale (401)", proxy.get("/").status_code == 401)
outsider = Client(REMOTE_ADDR="10.9.8.7", HTTP_HOST=HOST, HTTP_X_FORWARDED_PROTO="https")
check(
    "desde fuera del proxy: 403, aunque traiga encabezado",
    outsider.get("/", **header).status_code == 403,
)
check("/healthz tampoco responde desde fuera", outsider.get("/healthz").status_code == 403)
check(
    "un Host no permitido se rechaza (400)",
    proxy.get("/healthz", HTTP_HOST="otro.example").status_code == 400,
)

home = proxy.get("/", **header)
check(
    "la administradora de BOOTSTRAP_ADMINS entra y ve la portada",
    home.status_code == 200,
    home.status_code,
)
for url in (
    "/rutas/",
    "/rutas/forma-revit/",
    "/rutas/bentley-learn/",
    "/catalogo/",
    "/certificados/",
    "/foro/",
    "/documentos/",
    "/conocimiento/",
    "/equipo/",
    "/personas/",
    "/perfil/",
    "/perfil/avatar/",
    "/moderacion/",
    "/avisos/",
    "/teo/",
    "/ayuda/",
    "/certificados/exportar/",
    "/certificados/vencimientos/",
    "/equipo/matriz/",
    "/conocimiento/mejoras/",
):
    code = proxy.get(url, **header).status_code
    check(f"GET {url}", code == 200, code)
check(
    "el admin de Django exige ser administradora",
    proxy.get("/admin/", **header).status_code in (200, 302),
)
check(
    "las cookies de sesión son seguras",
    django.conf.settings.SESSION_COOKIE_SECURE and django.conf.settings.CSRF_COOKIE_SECURE,
)
check("DEBUG apagado", not django.conf.settings.DEBUG)
check("sin identidad simulada", django.conf.settings.DEV_REMOTE_USER == "")
page = home.content.decode()
check("sale el auspicio de Suite Aero", "Suite Aero" in page)
check("los estáticos salen con nombre con hash (WhiteNoise)", "/static/" in page)

print()
if errors:
    print(f"{len(errors)} comprobación(es) fallaron.")
    sys.exit(1)
print("Humo de producción: todo en verde.")
