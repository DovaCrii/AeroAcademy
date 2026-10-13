# CLAUDE.md · AeroAcademy

@AGENTS.md

## Cómo trabajamos (resumen; estándar completo en `docs/ESTANDAR_TRABAJO.md`)

- **Plan primero.** Antes de cambiar algo no trivial, propón un plan corto (qué, en qué archivos, cómo se prueba) y espera el visto bueno.
- **Bloques pequeños.** Una rama y un PR por cambio acotado: `bloque-<n>-<tema>`. Nunca trabajes directo sobre `main`.
- **Pruebas.** Escribe o ajusta pruebas junto con el código. Antes de entregar corre: `uv run pytest` y `uv run ruff check . && uv run ruff format --check .`.
- **Quién fusiona.** Tú construyes, subes la rama, abres el PR, esperas el CI en verde y fusionas con *merge commit* (decisión de la persona, 2026-10-13). La persona despliega. Nunca `push --force` a `main`, nunca saltes el CI ni cambies los *settings* del repo.
- **Privacidad (repositorio público).** Sin claves, `.env`, certificados, datos de clientes ni datos personales en git, logs ni pruebas. Lo privado va en `private/` (ignorado por git).
- **Idioma.** Interfaz y documentación en español; código, nombres y URLs en inglés.
- **Alcance.** Haz solo lo pedido. Lo ambiguo se anota como pregunta abierta, no se decide solo.
- **No tocar** despliegue ni producción (`deploy/`, `docs/PRODUCCION.md`) sin que se pida explícitamente.

