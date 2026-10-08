## Qué cambia

<!-- Resumen corto, en español, de lo que hace este PR. -->

## Bloque

<!-- Ej.: Bloque 3 · Mundo Arquitectura (docs/PLAN.md). Si apila sobre otro PR, indícalo. -->

## Criterios de aceptación

<!-- Copia los "Acepta si" del bloque y marca los que cumple, con la prueba que lo cubre. -->

- [ ] …

## Cómo probarlo

```bash
uv sync
uv run pytest
uv run python manage.py runserver   # con DEV_REMOTE_USER=tu@correo
```

## Fuera de alcance / pendiente

<!-- Lo que quedó anotado en docs/DECISIONES.md o en las notas del bloque. -->

## Lista de verificación

- [ ] `uv run pytest` en verde
- [ ] `uv run ruff check . && uv run ruff format --check .` en verde
- [ ] Migraciones generadas y aplicables desde cero (`makemigrations --check`)
- [ ] `docs/PLAN.md` actualizado (bloque marcado y con notas)
- [ ] Sin secretos, claves ni datos personales en el diff
- [ ] Interfaz revisada a 390 px y en tema claro y oscuro (si toca pantallas)
