# AGENTS.md · AeroAcademy · Academia LEV Digital 101

Instrucciones para agentes de código (Codex, Claude Code u otros) que trabajen en este repositorio.
Leer completo antes de tocar código. Los documentos de `docs/` mandan sobre cualquier suposición.

## Qué es

**AeroAcademy** (repositorio y plataforma) aloja la **Academia LEV Digital 101**: plataforma interna de un equipo
pequeño para capacitarse por empresa de software (Autodesk, Bentley, Trimble, Esri, Microsoft, Oracle…), seguir el
avance de cada persona y del equipo, dejar notas, conversar en un foro y **guardar como repositorio los certificados
y credenciales obtenidos**, con vencimientos y exportación de evidencia.

Encima de todo hay una **capa de juego** (XP, niveles, títulos, insignias, clases por disciplina y hoja de personaje)
con estética 8-bit tipo D&D aplicada a la ingeniería, y un asistente llamado **Teo**.

Nace del prototipo `legacy/ruta-forma-revit/` (guía "Levantamiento Digital CC 410 · Ruta Forma + Revit").
Ese prototipo es la **referencia visual del mundo Arquitectura**; no se modifica, se migra.

## Documentos a leer, en orden

1. `docs/VISION.md`: identidad, disciplinas, módulos, estilo y mascota.
2. `docs/PRD.md`: alcance, roles e historias de usuario.
3. `docs/ARQUITECTURA.md`: stack, módulos, autenticación, bot y despliegue.
4. `docs/MODELO_DATOS.md`: entidades y reglas.
5. `docs/TAXONOMIA.md`: empresa → producto → ruta; etiquetas.
6. `docs/MUNDOS.md`: diseño único por especialidad y contrato común de los mundos.
7. `docs/GAMIFICACION.md`: XP, niveles, títulos, insignias.
8. `docs/BOT.md` y `docs/MODERACION.md`.
9. `docs/PLAN.md`: bloques de trabajo con criterios de aceptación. **Trabajar un bloque a la vez.**
10. `docs/FLUJO_GITHUB.md`: ramas, PR y qué hace (y qué no) el agente.
11. `docs/DECISIONES.md`: decisiones tomadas y abiertas. No resolver una decisión abierta por cuenta propia.

## Stack

- Python 3.12, gestionado con `uv`.
- Django (monolito modular), SQLite en modo WAL, plantillas de Django y mejora progresiva con `core/static/core/enhance.js` (D23: sin HTMX hasta decidir A11). Todo funciona sin JS. Sin framework JS ni build de frontend.
- CSS propio, en tres capas:
  - **Identidad general:** tomada de `design/academia/index.html`.
  - **Un CSS por mundo:** `core/static/worlds/<world>.css`, ver `docs/MUNDOS.md`. El mundo Arquitectura sale de `legacy/ruta-forma-revit/static/index.html`.
  - **Capa de juego:** `core/static/game.css`, con sprites SVG 8-bit.
- Tipografías locales (OFL): Archivo para todo el texto; Press Start 2P solo para niveles, insignias y títulos de juego.
- Pruebas con `pytest` + `pytest-django`. Lint con `ruff`.
- Producción: VM Linux, `gunicorn` en `127.0.0.1:8000`, publicado solo en la tailnet con `tailscale serve`.

## Comandos

```bash
uv sync                                   # dependencias
uv run python manage.py migrate
uv run python manage.py seed_catalog      # plataformas, vendors, rutas, insignias y títulos desde seed/
uv run python manage.py runserver         # desarrollo (usar DEV_REMOTE_USER, ver ARQUITECTURA)
uv run python manage.py check_expirations # avisos de vencimientos (tarea diaria)
uv run python manage.py reindex_assistant # índice de búsqueda de Teo
uv run python manage.py import_legacy --db ruta.db --dry-run   # datos del prototipo
uv run pytest                             # pruebas
uv run ruff check . && uv run ruff format --check .
```

## Reglas que salieron de las revisiones (aplican a todo bloque)

- **Autorización primero:** cada vista decide quién ve y quién edita; lo oculto, restringido o en borrador responde 404 (no revela que existe) y no sale en listados, búsquedas, avisos, tablero ni exportaciones.
- **Privacidad:** nada de `credentials` ni de logins hacia Teo, logs o el índice; lo que sale de credenciales se filtra con `credentials.services.visible_filter`.
- **Toda acción que cambia datos es POST con CSRF**, y todo `next` pasa por `url_has_allowed_host_and_scheme` (probar `//evil.com` y `/\evil.com`).
- **Texto de usuarios escapado;** el Markdown solo con `apps/core/markdown.py`. Probar `<script>` en cada campo nuevo.
- **XP, insignias y avisos son idempotentes** (`game.award/revoke/refresh`, `notify(key=...)`): marcar/desmarcar, verificar/rechazar y reintentar no duplican.
- **Archivos privados:** nombre generado, tipo real, tamaño máximo, sin URL pública, descarga como adjunto, borrado al confirmar la transacción.
- **Consultas acotadas:** cada listado nuevo lleva una prueba de que las consultas no crecen con los datos.

## Skills del proyecto

Hay skills en `.claude/skills/`. Claude Code las carga solo; en Codex, leer el `SKILL.md` correspondiente antes de la tarea.

| Skill | Cuándo |
|---|---|
| `bloque` | Al trabajar cualquier bloque de `docs/PLAN.md` |
| `nueva-ruta` | Al crear o modificar un JSON en `seed/rutas/` |
| `nuevo-mundo` | Al crear el diseño de una especialidad nueva |
| `nueva-insignia` | Al agregar insignias o títulos |
| `sprite-8bit` | Al dibujar avatares, insignias o a Teo |

## Subagentes del proyecto

Definidos en `.claude/agents/` y alineados con las skills. Úsalos para paralelizar trabajo en **archivos distintos**:

| Subagente | Para qué | Skill con la que trabaja |
|---|---|---|
| `bloque-dev` | Implementar un bloque o sub-bloque acotado | `bloque` |
| `artista-pixel` | Dibujar piezas de avatar, insignias y sprites | `sprite-8bit`, `nuevo-mundo` |
| `curador-semillas` | Rutas, cursos, insignias y títulos (`seed/`) | `nueva-ruta`, `nueva-insignia` |
| `revisor-bloque` | Revisar un bloque o PR antes de entregarlo (solo lee) | `bloque` |

Reglas: cada subagente edita solo lo que se le asignó; no hace `git`, `push` ni PR (eso lo hace quien lo lanzó); y quien lo
lanza **verifica el resultado** (pruebas, ruff y revisión visual) antes de integrarlo.

## Flujo con GitHub (regla de trabajo)

**El agente construye, sube y deja el PR listo; la persona revisa y fusiona.** Detalle en `docs/FLUJO_GITHUB.md`.

- Una rama y un PR por bloque: `bloque-<n>-<tema>`, apilados sobre el bloque anterior mientras no se fusione.
- Al terminar un bloque: `git push -u origin <rama>` y `gh pr create` con la plantilla de `.github/`.
  Título `Bloque <n> · <tema>`; cuerpo con criterios de aceptación y cómo probarlo.
- Revisar el CI del PR (`gh pr checks`) y arreglarlo si falla. Un PR en rojo no está listo.
- **Nunca** fusionar PR, forzar `push` sobre `main`, subir secretos o datos reales, ni cambiar la
  visibilidad o los *settings* del repositorio sin que se pida explícitamente.
- Encadenar bloques solo si la persona lo pidió ("continúa hasta terminar"); si no, esperar su confirmación.

## Convenciones

- Código, nombres de modelos, campos y URLs en **inglés**. Interfaz y mensajes al usuario en **español**.
- Los términos y comandos de software en la interfaz se muestran **en inglés**, tal como aparecen en pantalla
  (ej.: *Send to Revit*, *Corridor Modeling*), destacados con el estilo `.term`.
- Una app de Django por módulo de `docs/ARQUITECTURA.md`. Nada de lógica de negocio en las vistas: usar `services.py`.
- La capa de juego se otorga **solo desde services** (`gamification.services.award/revoke`), nunca desde vistas ni signals ocultos.
- Migraciones pequeñas y revisables. Nunca editar una migración ya aplicada.
- Cada bloque del plan termina con pruebas que cubren sus criterios de aceptación.

## Reglas

- **Alcance:** implementar solo lo que pide el bloque activo. Si algo falta o es ambiguo, dejarlo anotado en
  `docs/DECISIONES.md` como pregunta abierta y seguir con lo demás.
- **Seguridad:**
  - La identidad viene del encabezado `Tailscale-User-Login`. Solo se confía en él cuando la petición llega
    desde `127.0.0.1` (proxy de `tailscale serve`). Ver ARQUITECTURA.
  - Las personas nuevas quedan `pending` hasta que un admin las aprueba. Ver MODERACION.
  - Los archivos de certificados no se sirven como estáticos públicos: siempre por una vista que valida permisos.
  - Validar tipo y tamaño de archivo (PDF, PNG, JPG; máx. 10 MB). Nombres de archivo generados, nunca los del usuario.
- **Datos personales:** los certificados contienen datos personales. No registrar su contenido en logs y
  **nunca enviarlos al bot ni a ninguna API externa** (ver BOT.md).
- **Secretos:** `NIM_API_KEY` y `SECRET_KEY` solo por variables de entorno; nunca en el repositorio ni en pruebas.
- **Sin dependencias nuevas** fuera de las listadas en ARQUITECTURA sin dejarlo justificado en DECISIONES.
- No tocar `legacy/` ni `design/` salvo para leerlos.

## Definición de terminado (por bloque)

- Criterios de aceptación del bloque cumplidos y cubiertos por pruebas.
- `pytest` y `ruff` en verde (el CI del PR también).
- Migraciones generadas y aplicables desde cero.
- `docs/PLAN.md` actualizado: bloque marcado como terminado, con notas de lo que quedó pendiente.
- Rama subida y **PR abierto** con resumen en español (qué cambia, cómo probarlo, qué queda pendiente).
