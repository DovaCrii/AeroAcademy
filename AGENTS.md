# AGENTS.md · AeroAcademy · Academia LEV Digital 101

Instrucciones para agentes de código (Codex, Claude Code u otros) que trabajen en este repositorio.
Leer este archivo completo antes de tocar código. Los documentos de `docs/` mandan sobre cualquier suposición.
Para no cargar contexto de más: leer siempre la **lectura base** y solo los documentos que correspondan al bloque o módulo.

## Qué es

**AeroAcademy** (repositorio y plataforma) aloja la **Academia LEV Digital 101**: plataforma interna de un equipo
pequeño para capacitarse por empresa de software (Autodesk, Bentley, Trimble, Esri, Microsoft, Oracle…), seguir el
avance de cada persona y del equipo, dejar notas, conversar en un foro y **guardar como repositorio los certificados
y credenciales obtenidos**, con vencimientos y exportación de evidencia.

Encima de todo hay una **capa de juego** (XP, niveles, títulos, insignias, clases por disciplina y hoja de personaje)
con estética 8-bit tipo D&D aplicada a la ingeniería, y una asistente y mascota llamada **Nala** (D32; el código conserva el nombre `teo`).

Nace del prototipo `legacy/ruta-forma-revit/` (guía "Levantamiento Digital CC 410 · Ruta Forma + Revit").
Ese prototipo es la **referencia visual del mundo Arquitectura**; no se modifica, se migra.

## Documentos a leer

**Lectura base (siempre, antes de cualquier cambio):**

1. `docs/VISION.md`: identidad, disciplinas, módulos, estilo y mascota.
2. `docs/ARQUITECTURA.md`: stack, módulos, autenticación, bot y despliegue.
3. `docs/DECISIONES.md`: decisiones tomadas y abiertas. No resolver una decisión abierta por cuenta propia.
4. `docs/PLAN.md`: bloques de trabajo con criterios de aceptación. **Trabajar un bloque a la vez.**

**Según el bloque o módulo (leer solo lo que toque):**

| Si el cambio toca… | Leer |
|---|---|
| Alcance, roles, historias de usuario | `docs/PRD.md` |
| Modelos, entidades, migraciones | `docs/MODELO_DATOS.md` |
| Empresas, productos, rutas, etiquetas | `docs/TAXONOMIA.md`, `docs/CURSOS.md` (inventario, brechas, plantilla y checklist de autoría) |
| Mundos visuales por especialidad | `docs/MUNDOS.md` |
| XP, niveles, títulos, insignias | `docs/GAMIFICACION.md` |
| Nala (asistente; en el código `teo`), foro, moderación | `docs/BOT.md`, `docs/MODERACION.md` |
| Portada, iconos | `docs/HOME.md`, `docs/ICONOS.md` |
| Ramas, PR, fusiones | `docs/FLUJO_GITHUB.md`, `docs/FUSIONES.md` (**el agente fusiona con el CI en verde; la persona despliega**) |
| Despliegue y producción | `docs/PRODUCCION.md`, `docs/PENDIENTES.md` |
| Cómo trabajamos con Claude Code (ciclo, modelos, privacidad) | `docs/ESTANDAR_TRABAJO.md`; plantillas en `tools/kit/` |

## Stack

- Python 3.12, gestionado con `uv`.
- Django (monolito modular), SQLite en modo WAL, plantillas de Django y mejora progresiva con `apps/core/static/core/enhance.js` (D23: sin HTMX hasta decidir A11). Todo funciona sin JS. Sin framework JS ni build de frontend.
- CSS propio, en tres capas:
  - **Identidad general:** tomada de `design/academia/index.html`.
  - **Un CSS por mundo:** `apps/core/static/worlds/<world>.css`, ver `docs/MUNDOS.md`. El mundo Arquitectura sale de `legacy/ruta-forma-revit/static/index.html`.
  - **Capa de juego:** `apps/gamification/static/gamification/game.css`, con sprites SVG 8-bit.
- Tipografías locales (OFL): Archivo para todo el texto; Press Start 2P solo para niveles, insignias y títulos de juego.
- Pruebas con `pytest` + `pytest-django`. Lint con `ruff`.
- Producción: VM Linux, `gunicorn` en `127.0.0.1:8010` (el 8000 es de AeroControl en la misma VM), publicado desde un nodo Tailscale propio (`aeroacademy.<tailnet>.ts.net`): por defecto solo tailnet (`tailscale serve`); con `PUBLIC_FUNNEL=1` también una **puerta pública endurecida con Funnel** (D36: segundo gunicorn en `127.0.0.1:8011`, sin identidad de Tailscale, sin `/admin/`, TOTP para lead y admin). Funnel solo en el nodo propio, nunca en el de AeroControl.

## Comandos

```bash
uv sync                                   # dependencias
uv run python manage.py migrate
uv run python manage.py seed_catalog      # plataformas, vendors, rutas, insignias y títulos desde seed/
uv run python manage.py runserver         # desarrollo (usar DEV_REMOTE_USER, ver ARQUITECTURA)
uv run python manage.py check_expirations # avisos de vencimientos (tarea diaria)
uv run python manage.py reindex_assistant # índice de búsqueda de Nala
uv run python manage.py revisar_enlaces --externos  # enlaces internos y externos (CSV en private/)
uv run python manage.py import_legacy --db ruta.db --dry-run   # datos del prototipo
uv run pytest                             # pruebas
uv run ruff check . && uv run ruff format --check .
```

## Reglas que salieron de las revisiones (aplican a todo bloque)

- **Autorización primero:** cada vista decide quién ve y quién edita; lo oculto, restringido o en borrador responde 404 (no revela que existe) y no sale en listados, búsquedas, avisos, tablero ni exportaciones.
- **Privacidad:** nada de `credentials` ni de logins hacia Nala, logs o el índice; lo que sale de credenciales se filtra con `credentials.services.visible_filter`.
- **Toda acción que cambia datos es POST con CSRF**, y todo `next` pasa por `url_has_allowed_host_and_scheme` (probar `//evil.com` y `/\evil.com`).
- **Texto de usuarios escapado;** el Markdown solo con `apps/core/markdown.py`. Probar `<script>` en cada campo nuevo.
- **XP, insignias y avisos son idempotentes** (`game.award/revoke/refresh`, `notify(key=...)`): marcar/desmarcar, verificar/rechazar y reintentar no duplican.
- **Archivos privados:** nombre generado, tipo real, tamaño máximo, sin URL pública, descarga como adjunto, borrado al confirmar la transacción.
- **Consultas acotadas:** cada listado nuevo lleva una prueba de que las consultas no crecen con los datos.

## Método, skills y subagentes

**Método único: skill `orquestar`** (decisión del dueño, 2026-10-16). Fases: Entender → Diseñar (Opus) → Implementar
(Sonnet) → Verificar (Haiku) → Revisar (Opus) → Publicar y cerrar (`cerrar-pendientes`).

| Modelo (esfuerzo) | Rol | Subagentes |
|---|---|---|
| **Opus 5.5 medio** | Sesión principal: diseña, decide, reparte, **revisa diffs**, integra y fusiona | `disenador`, `revisor-bloque` |
| **Sonnet 5.5 medio** | Implementa | `bloque-dev`, `curador-semillas`, `artista-pixel` |
| **Haiku 5.5 medio** | Inventarios, comprobaciones del CI, enlaces, vigilar el CI | `verificador` |

Skills en `.claude/skills/` (Claude Code las carga solo; en Codex, leer el `SKILL.md` antes de la tarea):

| Skill | Cuándo |
|---|---|
| `orquestar` | En toda ronda con más de un paso o agente: fases, modelos y cuándo preguntar |
| `bloque` | Al trabajar un bloque de `docs/PLAN.md` o una mejora de `docs/MEJORAS_*.md` |
| `cerrar-pendientes` | Al publicar: push, PR, CI en verde, fusión con merge commit, limpieza |
| `revision-privacidad` | Antes de cada push o PR, y al agregar archivos, imágenes o datos de prueba |
| `nueva-ruta` | Al crear o cambiar `seed/rutas/*.json` (slides, `diagram`, `priv:`, icono, foro) |
| `nuevo-mundo` | Al crear o rediseñar un mundo o una figura temática |
| `nueva-insignia` | Al agregar insignias, títulos o desbloqueables |
| `sprite-8bit` | Al dibujar insignias, a Nala, iconos o encargar piezas de avatar |

Subagentes en `.claude/agents/`, para trabajar en paralelo en **archivos distintos**:

| Subagente | Modelo | Para qué | Skills |
|---|---|---|---|
| `disenador` | opus | Plan, UX y decisiones antes de construir (escribe en `docs/`) | `orquestar` |
| `revisor-bloque` | opus | Revisar el diff de un bloque o PR (solo lee) | `bloque` |
| `bloque-dev` | sonnet | Implementar un bloque o sub-bloque acotado | `bloque` |
| `curador-semillas` | sonnet | Rutas, cursos, insignias, títulos y foro (`seed/`) | `nueva-ruta`, `nueva-insignia` |
| `artista-pixel` | sonnet | Avatar, insignias, Nala, iconos y figuras | `sprite-8bit` |
| `verificador` | haiku | Inventarios, CI local, `revisar_enlaces`, vigilar el CI (solo reporta) | — |

Reglas: al lanzar un subagente se pasa `model` explícito; cada uno edita solo lo asignado y no hace `push` ni PR; quien
lo lanza verifica y revisa el resultado antes de integrarlo.

## Flujo con GitHub (regla de trabajo)

**El agente construye, sube, abre el PR, espera el CI en verde y fusiona con merge commit; la persona despliega.** Detalle en `docs/FLUJO_GITHUB.md`.

- **Dos fases separadas.** (1) *Implementar en local:* código, pruebas, ruff y migraciones en la rama, con commits locales.
  (2) *Publicar:* solo cuando la fase 1 está completa y verificada, `git push -u origin <rama>` y `gh pr create`.
  Si algo de la fase 1 queda dudoso, no se publica.
- Una rama y un PR por bloque: `bloque-<n>-<tema>`, apilados sobre el bloque anterior mientras no se fusione.
- Al publicar un bloque: PR con la plantilla de `.github/`. Título `Bloque <n> · <tema>`; cuerpo con criterios de aceptación y cómo probarlo.
- Commits pequeños, en español y en imperativo (`Agrega el motor de XP idempotente`); primera línea ≤ 72 caracteres.
  Esta es la convención del repositorio: no se usa Conventional Commits.
- Publicar y fusionar con la skill `cerrar-pendientes`: esperar la corrida real del CI, arreglar lo rojo y fusionar
  con merge commit. Un PR en rojo no está listo.
- **Nunca** fusionar con el CI en rojo o saltado, forzar `push` sobre `main`, subir secretos o datos reales, ni cambiar la
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
  `docs/DECISIONES.md` como pregunta abierta y seguir con lo demás. **Excepción:** si la duda afecta la
  seguridad, la privacidad o una decisión de producto, se detiene esa parte y se consulta a la persona antes
  de seguir; no se resuelve por cuenta propia.
- **Seguridad:**
  - La identidad viene del encabezado `Tailscale-User-Login`. Solo se confía en él cuando la petición llega
    desde `127.0.0.1` (proxy de `tailscale serve`). Ver ARQUITECTURA.
  - En la puerta pública (`settings.PUBLIC_DOOR`, la fija el proceso) ese encabezado se descarta y no existe `/admin/`.
    Toda herramienta de lead/admin nueva que no deba salir a internet va en `PUBLIC_BLOCKED_PREFIXES`.
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
- Diff revisado (`revisor-bloque`) y privacidad en verde (`revision-privacidad`).
- PR con resumen en español (qué cambia, cómo probarlo, qué queda pendiente), CI en verde y fusionado con merge
  commit; la persona despliega.
