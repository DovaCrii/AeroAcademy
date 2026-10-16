---
name: orquestar
description: Método único de trabajo de {{PROYECTO}} - fases (Entender, Diseñar, Implementar, Verificar, Revisar, Publicar y cerrar), qué modelo y esfuerzo hace cada una (Opus 5.5 medio diseña y revisa, Sonnet 5.5 medio implementa, Haiku 5.5 medio verifica) y cuándo preguntar a la persona. Usar en toda ronda con más de un paso o más de un agente.
---

# Orquestar una ronda

Fuente única del método de la suite Aero. Opus organiza, Sonnet construye, Haiku comprueba; todos con esfuerzo medio.

| Modelo (esfuerzo) | Rol | Agentes (`.claude/agents/`) |
|---|---|---|
| **Opus 5.5 medio** | Sesión principal: entiende, diseña, decide, reparte, **revisa diffs**, integra y fusiona | `disenador`, `revisor` |
| **Sonnet 5.5 medio** | Implementa: código, pruebas, documentos, arreglos de CI | `general-purpose` con `model: "sonnet"` |
| **Haiku 5.5 medio** | Mecánico: inventarios, comprobaciones, enlaces, vigilar el CI, resumir logs | `verificador` |

Al lanzar con `Agent`, pasa siempre `model` explícito; sin él podría heredar el modelo de la sesión.

## Fases

1. **Entender (Opus).** Partes independientes; lectura mínima de `AGENTS.md` y del tema. Inventario con `verificador`.
2. **Diseñar (Opus · `disenador` si es grande).** Plan corto: archivos, criterios con su prueba, riesgos, reparto con
   **dueños de archivos sin cruce**, qué verifica Haiku. Cambios no triviales: visto bueno de la persona.
3. **Implementar (Sonnet, en paralelo).** Un agente por parte, cada uno en su rama o `git worktree`; prompt
   autosuficiente; commits locales; sin `push` ni PR.
4. **Verificar (Haiku).** `{{COMANDO_PRUEBAS}}`, `{{COMANDO_LINT}}`, `{{COMANDO_FORMAT_CHECK}}`,
   `python tools/kit/privacy_scan.py`. Reporta; no corrige.
5. **Revisar (Opus · `revisor`).** Diff completo: criterios contra pruebas, seguridad, privacidad, interfaz. Lo bloqueante
   vuelve al implementador.
6. **Publicar y cerrar (Opus · skill `cerrar-pendientes`).** Skill `revision-privacidad`, PR, CI en verde, merge commit.
   La persona despliega.

## Cuándo preguntar a la persona

Seguridad, privacidad o datos de clientes; decisiones de producto; dependencias nuevas; despliegue o producción
({{ARCHIVOS_DE_DESPLIEGUE}}); borrar ramas remotas o cerrar PR ajenos. Lo demás ambiguo: pregunta abierta y propuesta por defecto.

## Ahorro de tokens

Una búsqueda, un agente. Informes cortos; el detalle se lee del diff. Modelo equivocado con poco avance: detener y relanzar.
