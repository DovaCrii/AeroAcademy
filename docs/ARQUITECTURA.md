# Arquitectura · Academia LEV Digital 101 (MVP)

## Vista general

```
navegador (tailnet) ─HTTPS─> tailscale serve ─> 127.0.0.1:8000 gunicorn ─> Django ─┬─> SQLite (WAL)
                              └ Tailscale-User-Login / -Name / -Profile-Pic        └─> /var/lib/centro/media (certificados)
```

Monolito modular en Django, sin frontend separado. HTMX para interacciones (marcar hitos, quiz, notas,
filtros) sin recargar la página.

## Módulos (apps de Django)

| App | Responsabilidad |
|---|---|
| `accounts` | Persona, rol, autenticación por encabezado de Tailscale |
| `catalog` | Plataformas, recursos (cursos, módulos, tutoriales, exámenes), habilidades, **disciplinas** |
| `paths` | Rutas de aprendizaje, niveles, hitos, preguntas de quiz; importación desde JSON |
| `progress` | Avance por persona: hitos marcados, respuestas de quiz, meta de certificación |
| `community` | Notas sobre rutas, foro (hilos) y consultas (preguntas con respuesta aceptada) |
| `library` | Biblioteca de documentos con versiones, por disciplina y tipo |
| `knowledge` | Artículos de conocimiento, lecciones aprendidas y propuestas de mejora |
| `credentials` | Repositorio de certificados: archivo, metadatos, validación, vencimientos, exportación |
| `team` | Tablero, tabla de avance, matriz de competencias, kit y plan compartidos, tablón del gremio, expediciones |
| `gamification` | XP, niveles, títulos, insignias, avatar 8-bit, hoja de personaje |
| `notifications` | Campana de notificaciones dentro de la app y anuncios del moderador; `notify()` con gancho para correo |
| `assistant` | Teo: widget, índice FTS5, cliente NIM, límites y filtro de privacidad (ver BOT.md) |
| `core` | Plantillas base, CSS, **mundos** (`core/static/worlds/`, `core/templates/worlds/`), capa de juego (`game.css`, sprites), utilidades |

Regla: las apps se comunican por `services.py`, no importando vistas entre sí.

## Autenticación

- Middleware propio `TailscaleRemoteUserMiddleware` (subclase de `RemoteUserMiddleware`):
  - Lee `Tailscale-User-Login`. Crea o actualiza la persona con `Tailscale-User-Name` y `-Profile-Pic`.
  - **Solo confía en el encabezado si `REMOTE_ADDR` está en `TRUSTED_PROXY_IPS` (por defecto `127.0.0.1`, `::1`).**
    En cualquier otro caso responde 403.
- Desarrollo: variable `DEV_REMOTE_USER=correo@dominio` simula la identidad. Prohibido en producción
  (`DEBUG=False` la ignora).
- Roles con grupos de Django: `member`, `lead`, `admin`. Quien figure en `BOOTSTRAP_ADMINS` queda admin y aprobada (se reaplica en cada petición).

## Archivos privados (certificados y documentos)

Los documentos de `library` siguen la misma regla de descarga por vista con permiso; visibles para todo miembro salvo que se marquen restringidos.

### Certificados

- Guardados en `MEDIA_ROOT=/var/lib/centro/media/credentials/<persona_id>/<uuid>.<ext>`.
- Nunca servidos por `MEDIA_URL` público. Vista `credentials:download` valida permiso (dueño, lead, admin)
  y entrega con `FileResponse` y `Content-Disposition: attachment`.
- Validación: extensión y tipo real (firma del archivo) PDF/PNG/JPG, máx. 10 MB.
- Miniatura opcional fuera del MVP.

## Interfaz

- Identidad general (cabecera, portada, tarjetas de módulos, paleta marino/azul) desde `design/academia/index.html`.
- Componentes de rutas desde el prototipo `legacy/ruta-forma-revit/static/index.html`:
  - Paleta de alto contraste (claro) y *blueprint* (oscuro), variables CSS en `core/static/core/tokens.css`.
  - Componentes: portada con nube de puntos, corte de edificio por niveles, Project Browser de niveles,
    tablas tipo *schedule*, nubes de revisión para notas, escalera de certificación, Gantt.
- Cada componente como `{% include %}` o *template tag* reutilizable.
- Responsive a 390 px sin desborde horizontal; foco visible; respeta `prefers-reduced-motion`.

## Dependencias permitidas

`django`, `gunicorn`, `whitenoise` (solo estáticos, no media), `openpyxl` (exportación XLSX),
`python-magic` o verificación manual de firmas, `httpx` (solo `assistant`, D16), `pytest`, `pytest-django`, `ruff`, `factory-boy`.
Markdown sanitizado (artículos, anuncios, respuestas de Teo): `markdown` + `nh3`, a justificar en DECISIONES en el bloque que lo use.

## Flujo de aprobación

Además de la identidad, el middleware revisa `Person.status`:
- `pending`: redirige a `/espera/`;
- `suspended`: responde 403;
- `approved`: acceso normal.

Las rutas `/espera/` y los estáticos quedan exentos.

## Bot (Teo)

`assistant` llama a `NIM_BASE_URL` (por defecto `https://integrate.api.nvidia.com/v1`) con `httpx`, *timeout* `BOT_TIMEOUT_S`.
Es la **única** salida a internet de la aplicación. El contexto se arma con una lista blanca de campos (BOT.md). Si falla, la app sigue funcionando.
Cualquier otra requiere una entrada en `DECISIONES.md`.

## Despliegue

- `deploy/install.sh` idempotente (patrón del prototipo): usuario de sistema, `uv sync`, `collectstatic`,
  `migrate`, servicio systemd `centro.service`, `tailscale serve --bg 8000`.
- Variables en `/etc/centro/env`: `SECRET_KEY`, `ALLOWED_HOSTS` (nombre MagicDNS), `MEDIA_ROOT`,
  `DATABASE_PATH`, `BOOTSTRAP_ADMINS`, `TRUSTED_PROXY_IPS`, `NIM_API_KEY`, `NIM_BASE_URL`, `NIM_MODEL`, `BOT_ENABLED`, `BOT_DAILY_LIMIT`.
- Respaldo diario: `sqlite3 .backup` + `tar` de `media/`, retención 30 días.
- No usar `tailscale funnel`.

## Migración desde el prototipo

Comando `import_legacy --db /var/lib/forma-ruta/ruta.db`:
- `people` → personas (login de Tailscale como identificador).
- `progress.data` → hitos y quiz (claves `n0-t0`, `n0-q0` → hito/pregunta por `key` de la ruta forma-revit).
- `notes` → notas con autor, nivel, recurso, tipo, texto, padre y fecha.
- `shared` (`kitX-Y`, `phX-Y`) → casillas de equipo.
Idempotente: correrlo dos veces no duplica.
