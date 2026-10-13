# CLAUDE.md · {{PROYECTO}}

@AGENTS.md

## Cómo trabajamos (resumen; el estándar completo está en `docs/ESTANDAR_TRABAJO.md` de AeroAcademy)

- **Plan primero.** Antes de cambiar algo no trivial, propón un plan corto (qué, en qué archivos, cómo se prueba) y espera el visto bueno.
- **Bloques pequeños.** Una rama y un PR por cambio acotado: `{{PREFIJO_RAMA}}-<tema>`. Nunca trabajes directo sobre `main`.
- **Pruebas.** Escribe o ajusta pruebas junto con el código. Antes de entregar corre: `{{COMANDO_PRUEBAS}}` y `{{COMANDO_LINT}}`.
- **Quién fusiona.** Tú construyes, subes la rama, abres el PR, esperas el CI en verde y fusionas con *merge commit*. La persona despliega. Nunca `push --force` a `main`, nunca saltes el CI ni cambies los *settings* del repo.
- **Privacidad (repositorio {{VISIBILIDAD}}).** Sin claves, `.env`, certificados, datos de clientes ni datos personales en git, logs ni pruebas. Lo privado va en `private/` (ignorado por git).
- **Idioma.** Interfaz y documentación en español; código, nombres y URLs en inglés.
- **Alcance.** Haz solo lo pedido. Lo ambiguo se anota como pregunta abierta, no se decide solo.
- **No tocar** despliegue ni producción ({{ARCHIVOS_DE_DESPLIEGUE}}) sin que se pida explícitamente.
