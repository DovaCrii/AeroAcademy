# Flujo con GitHub

Repositorio: **https://github.com/DovaCrii/AeroAcademy** (público).
Regla de fondo: **el agente construye, sube y deja el PR listo; la persona revisa y fusiona.**

## Ramas y PR

| Rama | Contenido | Base del PR |
|---|---|---|
| `main` | Lo ya revisado y fusionado | — |
| `bloque-<n>-<tema>` | Un bloque de `docs/PLAN.md` (ej. `bloque-3-mundo-arquitectura`) | La rama del bloque anterior si aún no se fusionó; si no, `main` |
| `fix-<tema>` / `docs-<tema>` | Arreglos y documentación sueltos | `main` |

- **Un PR por bloque.** Si un bloque es muy grande, se divide en sub-bloques (`12a`, `12b`) con su propio PR.
- Los PR se **apilan**: el PR del bloque 4 apunta a la rama del 3. Al fusionar el 3, GitHub reapunta el 4 a `main`.
- El agente **nunca fusiona**, nunca hace `push --force` a `main` ni reescribe ramas ya compartidas.

## Qué hace el agente en cada bloque

1. Crea la rama desde la anterior: `git switch -c bloque-<n>-<tema>`.
2. Implementa el bloque con la skill `bloque` (plan corto → pruebas → código → `ruff` → migraciones).
3. Commits pequeños y en español, en imperativo: `Agrega el motor de XP idempotente`.
4. Actualiza `docs/PLAN.md` (marca `[x]` y escribe las notas del bloque).
5. `git push -u origin <rama>` y abre el PR con `gh pr create` usando la plantilla de `.github/pull_request_template.md`:
   - título: `Bloque <n> · <tema>`;
   - cuerpo: qué cambia, criterios de aceptación con su prueba, cómo probarlo y lo pendiente;
   - sin etiquetas ni revisores automáticos que no se hayan pedido.
6. Comprueba el CI del PR (`gh pr checks`) y corrige si falla.
7. Informa en el chat: enlace del PR, resultado del CI y qué decide la persona (fusionar, pedir cambios).

## Fusiones

La regla completa está en **`docs/FUSIONES.md`**: fusiona la persona (o el agente, si ella se lo pide en el chat), de abajo hacia arriba, solo con *merge commit* (nunca squash ni rebase) y con `tools/fusionar_cadena.py`. Después, `python tools/preflight.py` y `docs/PRODUCCION.md`.

## Qué NO hace sin que se lo pidan

- Fusionar PR, cerrar issues, borrar ramas remotas o publicar *releases*.
- Subir secretos (`NIM_API_KEY`, `SECRET_KEY`, `.env`), bases de datos ni certificados reales.
- Cambiar la visibilidad del repositorio, sus *settings* o las reglas de protección de `main`.

## CI

`.github/workflows/ci.yml` corre en cada PR y en `main`: `ruff`, `manage.py check`, `makemigrations --check`,
`seed_catalog --dry-run` y `pytest`. Un PR con el CI en rojo no está listo.

## Convención de mensajes

- Commits: primera línea ≤ 72 caracteres, en español, en imperativo; el detalle en el cuerpo si hace falta.
- Cuando un cambio responde a una decisión, citar su código (`D13`, `A7`) de `docs/DECISIONES.md`.
