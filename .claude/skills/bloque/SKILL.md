---
name: bloque
description: Ejecuta un bloque de docs/PLAN.md de AeroAcademy de punta a punta - plan, rama, pruebas, código, ruff, migraciones y PLAN actualizado - y lo entrega a cerrar-pendientes para publicarlo y fusionarlo con el CI en verde. Usar al pedir "continúa con el bloque N", "siguiente bloque" o al trabajar cualquier bloque o mejora del plan.
---

# Trabajar un bloque del plan

Reparto según la skill `orquestar`: **Opus 5.5 medio** planifica y revisa; **Sonnet 5.5 medio** (`bloque-dev`)
implementa; **Haiku 5.5 medio** (`verificador`) corre las comprobaciones. Publicar y fusionar es la skill `cerrar-pendientes`.

## Pasos

1. **Ubicar (Opus).** Sin número: el primer `[ ]` según el **Orden** de `docs/PLAN.md` (o el plan `docs/MEJORAS_*.md`
   indicado). Márcalo `[~]`.
2. **Rama.** `git switch -c bloque-<n>-<tema>` (o `fix-`/`docs-`) desde `main`, o desde el bloque anterior si aún no se fusionó.
3. **Leer lo mínimo.** `AGENTS.md`, la sección del bloque, sus entidades en `docs/MODELO_DATOS.md`, los docs que cita y
   `docs/DECISIONES.md`.
4. **Plan corto (Opus, ≤ 10 líneas).** Archivos y la prueba de **cada** «Acepta si». Ambigüedad: pregunta abierta `A<n>`
   en DECISIONES y propuesta por defecto; si toca seguridad, privacidad o producto, se pregunta a la persona.
5. **Pruebas primero (Sonnet)** para los criterios y para «Reglas que salieron de las revisiones» de `AGENTS.md`.
6. **Implementar (Sonnet).** Lógica en `services.py`; juego solo con `gamification.game` (`award`, `revoke`, `refresh`,
   `evaluate`); avisos con `notify(..., key=...)`; archivos privados por vista con permiso; nada de `credentials` hacia
   el asistente; todo funciona **sin JS** (`enhance.js` solo mejora); modelo nuevo con su migración.
7. **Comprobar (Haiku), lo mismo que el CI** (`.github/workflows/ci.yml`), sobre una base nueva (`DATABASE_PATH` temporal):
   ```bash
   uv run ruff check . && uv run ruff format --check .
   uv run python manage.py check
   uv run python manage.py makemigrations --check --dry-run
   uv run python manage.py migrate --noinput && uv run python manage.py seed_catalog --dry-run
   uv run pytest -q
   python tools/kit/privacy_scan.py
   ```
   Si falla algo que parece de Django o de una dependencia, leer su código fuente antes de adivinar.
8. **Interfaz.** `runserver` con `DEV_REMOTE_USER`; escritorio y 375 px, claro y oscuro, sin desborde, y con JS
   desactivado. Si tocó rutas, catálogo o plantillas: `uv run python manage.py revisar_enlaces`.
9. **Revisar (Opus · `revisor-bloque`)** el diff completo; lo bloqueante vuelve al paso 6.
10. **Cerrar.** `[x]` en `docs/PLAN.md` con notas de lo pendiente; commits chicos en español e imperativo (≤ 72
    caracteres, sin Conventional Commits). Luego skill `cerrar-pendientes`: PR `Bloque <n> · <tema>` con la plantilla,
    CI en verde, merge commit. La persona despliega.

**Encadenar bloques** solo si la persona pidió «continúa hasta terminar»: cada bloque en su rama y PR apilado.

## Trampas conocidas (Windows + PowerShell)

- Parchear: script Python en el scratchpad con `python -I` y `assert old in texto`; nada de `-replace` con `` `n ``.
  Nunca `Write` sobre un archivo sin leerlo antes.
- Texto largo (cuerpos de PR, scripts): escribirlo a un archivo; `gh pr create --body-file … --base …`.
- `;` sigue aunque fallen las pruebas: condiciona el commit al resultado.
- Pruebas de «no aparece»: la campana y el widget de Nala salen en toda página; acota con `html.split("<main")[1]`.
- Módulo nuevo: `url_name` en `core/modules.py`, enlace en `base.html`, `INSTALLED_APPS`, `config/urls.py`, migración y
  `tests/test_welcome.py`.
- Capturas en blanco con scroll suave: desplazar con `behavior:'instant'`. `.claude/launch.json` vive en la carpeta padre.
- Porcentajes: `int(x + 0.5)`, no `round()`. Claves solo en `.env`; antes de subir, `git grep -n "nvapi-"`.
