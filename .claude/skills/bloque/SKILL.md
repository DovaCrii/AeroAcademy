---
name: bloque
description: Ejecuta un bloque de docs/PLAN.md de AeroAcademy de punta a punta - rama, pruebas, código, ruff, migraciones, PLAN actualizado, push y PR listo en GitHub. Usar al pedir "continúa con el bloque N", "siguiente bloque" o al trabajar cualquier bloque del plan.
---

# Trabajar un bloque del plan

Regla de fondo (`docs/FLUJO_GITHUB.md`): **el agente construye, sube y deja el PR listo; la persona fusiona.**

1. **Ubicar el bloque.** Si no se indica un número, toma el primero `[ ]` según el **Orden** de `docs/PLAN.md`.
   Márcalo `[~]`.
2. **Rama.** `git switch -c bloque-<n>-<tema>` desde la rama del bloque anterior (o `main` si ya se fusionó).
3. **Leer lo mínimo:**
   - `AGENTS.md`;
   - la sección del bloque;
   - las entidades del bloque en `docs/MODELO_DATOS.md`;
   - los documentos que el bloque cita (MUNDOS, GAMIFICACION, BOT, MODERACION);
   - `docs/DECISIONES.md`.
4. **Plan corto** (máximo 10 líneas): archivos que se crean o modifican y las pruebas que cubren **cada**
   criterio "Acepta si". Si hay una ambigüedad, anótala como pregunta abierta `A<n>` en DECISIONES y elige
   la propuesta por defecto.
5. **Implementar** respetando las convenciones:
   - lógica en `services.py`;
   - XP solo con `gamification.services.award/revoke`;
   - archivos privados por una vista con permiso;
   - nada de `credentials` hacia `assistant`;
   - cambios de modelo con su migración, y las semillas nuevas con `seed_catalog --dry-run` en verde.
6. **Pruebas primero** para los criterios de aceptación. Luego correr, desde la carpeta del proyecto,
   **lo mismo que corre el CI** (`.github/workflows/ci.yml`):
   ```bash
   uv run ruff check . && uv run ruff format --check .
   uv run python manage.py check
   uv run python manage.py makemigrations --check --dry-run
   uv run python manage.py migrate --noinput && uv run python manage.py seed_catalog --dry-run   # base nueva
   uv run pytest
   ```
   La validación de semillas se prueba contra una **base nueva** (`DATABASE_PATH` temporal): el CI falló
   una vez por correrla sin migrar.
   Si una prueba falla por algo que parece un error de Django o de una dependencia, **leer su código fuente**
   antes de adivinar (pasó con `RemoteUserMiddleware` y `configure_user` en Django 5.2).
7. **Si el bloque tiene interfaz:** `runserver` con `DEV_REMOTE_USER` y revisión en el navegador a escritorio
   y a 390 px, en claro y oscuro, sin desborde horizontal. Para capturas, desplazar con
   `behavior:'instant'` (el scroll suave deja la captura en blanco).
8. **Cerrar el bloque:**
   - marcar `[x]` en `docs/PLAN.md` con notas de lo pendiente;
   - commits pequeños en español e imperativo;
   - `git push -u origin <rama>`;
   - `gh pr create` con título `Bloque <n> · <tema>` y la plantilla de `.github/pull_request_template.md`
     (criterios de aceptación con su prueba, cómo probarlo, pendiente), con base en la rama anterior
     si aún no se fusionó;
   - `gh pr checks` y corregir si el CI falla;
   - informar en el chat: enlace del PR, resultado del CI y qué debe decidir la persona.

## Paralelizar con subagentes

Cuando un bloque tiene partes independientes (arte, semillas, módulos que no se tocan entre sí), define primero el
**contrato** (formato, rangos, ids, un validador en `tools/`) y lanza subagentes de `.claude/agents/` en segundo plano, uno por
archivo. Mientras trabajan, construye lo que no depende de ellos. Al terminar: corre el validador y las pruebas, **mira el
resultado** (hojas de preview, navegador) y corrige tú lo que falle. Ejemplo real: los avatares de 32×32
(`docs/AVATARES_PIXEL.md`), con 4 artistas en paralelo y un validador común.

## Trampas conocidas en este entorno (Windows + PowerShell)

- El entorno bloquea comandos con `Remove-Item` y con textos largos que contienen `'\n'` o muchas rutas
  `/algo/`. Para borrar una base usa `DATABASE_PATH` apuntando a un archivo temporal nuevo; para texto
  largo (cuerpos de PR, scripts) **escribe el archivo con la herramienta Write** y luego ejecútalo.
- `gh pr create` siempre con `--body-file` y la rama base explícita (`--base`).
- Las capturas salen en blanco con `scroll-behavior:smooth`: desplazar con `behavior:'instant'`.
- `.claude/launch.json` del navegador vive en la carpeta **padre** del proyecto, con `--directory`.
- Redondeo: `round()` de Python redondea la mitad al par; para porcentajes usar `int(x + 0.5)`.

**No hacer sin que se pida:** fusionar PR, forzar `push`, subir secretos o datos reales, cambiar la visibilidad
o los *settings* del repositorio.

**Encadenar bloques:** solo si la persona pidió continuar hasta terminar; entonces cada bloque va en su
propia rama y PR, apilados, y no se espera confirmación entre ellos. Si no lo pidió, detenerse y esperar.
