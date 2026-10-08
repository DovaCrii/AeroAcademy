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
6. **Pruebas primero** para los criterios de aceptación. Luego correr, desde la carpeta del proyecto:
   ```bash
   uv run pytest
   uv run ruff check . && uv run ruff format --check .
   uv run python manage.py makemigrations --check --dry-run
   ```
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

**No hacer sin que se pida:** fusionar PR, forzar `push`, subir secretos o datos reales, cambiar la visibilidad
o los *settings* del repositorio.

**Encadenar bloques:** solo si la persona pidió continuar hasta terminar; entonces cada bloque va en su
propia rama y PR, apilados, y no se espera confirmación entre ellos. Si no lo pidió, detenerse y esperar.
