# Secciones que debe tener un AGENTS.md

Regla de adopción: **se FUSIONAN las secciones que falten; nunca se reemplaza un AGENTS.md existente.**
Si ya hay una sección equivalente, se deja la existente. Copia solo lo que falte y rellena los `{{PLACEHOLDERS}}`.

---

## Qué es

{{DESCRIPCIÓN en 3-5 líneas: qué hace el proyecto, para quién, qué NO es.}}

## Documentos a leer, en orden

1. `{{DOC_VISION}}`
2. `{{DOC_ARQUITECTURA}}`
3. `{{DOC_PLAN}}`: trabajar un bloque a la vez.
4. `docs/ESTANDAR_TRABAJO.md` (o su copia en este repo): cómo trabajamos con Claude Code.

## Stack

- {{LENGUAJE_Y_GESTOR}}
- {{FRAMEWORK}}
- {{BASE_DE_DATOS}}
- {{PRUEBAS_Y_LINT}}
- {{DESPLIEGUE: una línea; el detalle va en docs/}}

## Comandos

```bash
{{INSTALAR}}
{{EJECUTAR_EN_DESARROLLO}}
{{PRUEBAS}}
{{LINT}}
```

## Reglas

- **Alcance:** implementar solo lo que pide el bloque activo; lo ambiguo se anota como pregunta abierta.
- **Seguridad:** {{REGLAS de autorización, validación de entradas, CSRF, etc.}}
- **Privacidad:** el repositorio es {{VISIBILIDAD}}. Sin secretos, datos de clientes ni datos personales. Secretos solo por variables de entorno.
- **Dependencias:** ninguna nueva sin justificarla en {{DOC_DECISIONES}}.
- **No tocar:** {{RUTAS_INTOCABLES}}.

## Convenciones

- Código en inglés; interfaz y mensajes en español.
- Commits pequeños, en imperativo y en español.
- {{CONVENCIONES_PROPIAS}}

## Definición de terminado

- Criterios de aceptación cumplidos y cubiertos por pruebas.
- Pruebas y lint en verde, también en el CI del PR.
- Documentación actualizada ({{DOC_PLAN}}).
- Revisión de privacidad en verde (`python tools/kit/privacy_scan.py`).
- Rama subida y PR abierto con resumen en español (qué cambia, cómo probarlo, qué queda).

## Flujo con GitHub

**El agente construye, sube y deja el PR listo; la persona revisa y fusiona.**

- Una rama y un PR por bloque: `{{PREFIJO_RAMA}}-<n>-<tema>`.
- Al terminar: `git push -u origin <rama>` y `gh pr create` con la plantilla de `.github/`.
- Revisar el CI del PR (`gh pr checks`); un PR en rojo no está listo.
- Nunca: fusionar PR, `push --force` sobre `main`, subir secretos o datos reales, cambiar visibilidad o settings del repo.

## Skills y subagentes (si el proyecto los usa)

Tabla de `.claude/skills/` y `.claude/agents/`, y la política de modelos (Opus orquesta, Sonnet construye, Haiku verifica).
