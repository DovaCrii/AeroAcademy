---
name: orquestar
description: Método único de trabajo de AeroAcademy - fases (Entender, Diseñar, Implementar, Verificar, Revisar, Publicar y cerrar), qué modelo y esfuerzo hace cada una (Opus 5.5 medio diseña y revisa, Sonnet 5.5 medio implementa, Haiku 5.5 medio verifica) y cuándo preguntar a la persona. Usar en toda ronda con más de un paso o más de un agente.
---

# Orquestar una ronda

Fuente única del método (decisión del dueño, 2026-10-16). Las demás skills dicen **qué** hacer en su tema; esta dice
**quién** y **en qué orden**. Opus organiza, Sonnet construye, Haiku comprueba.

## Quién hace qué

| Modelo (esfuerzo) | Rol | Agentes (`.claude/agents/`) |
|---|---|---|
| **Opus 5.5 medio** | Sesión principal: entiende, diseña, decide, reparte, **revisa diffs** e integra | `disenador`, `revisor-bloque` |
| **Sonnet 5.5 medio** | Implementa: código, pruebas, migraciones, CSS, semillas, sprites, arreglos de CI | `bloque-dev`, `curador-semillas`, `artista-pixel` |
| **Haiku 5.5 medio** | Mecánico: inventarios, búsquedas, enlaces, vigilar el CI, resumir logs y pruebas | `verificador` |

Al lanzar con `Agent`, pasa siempre `model` explícito (`"opus"`, `"sonnet"` o `"haiku"`): si el tipo no está registrado y
se usa `general-purpose`, sin `model` heredaría el de la sesión. En ese caso, dile que lea primero su `.claude/agents/<nombre>.md`.

## Fases

1. **Entender (Opus).** Separar el pedido en partes independientes; lectura base de `AGENTS.md` y solo los docs del tema.
   Inventario previo con `verificador` (o el agente `Explore`) si hay que ubicar muchos archivos.
2. **Diseñar (Opus · `disenador` si es grande).** Plan corto: archivos, criterios de aceptación con su prueba, riesgos,
   reparto con **dueños de archivos sin cruce** y qué verifica Haiku. Cambios grandes: plan en `docs/` y visto bueno.
3. **Implementar (Sonnet, en paralelo y en segundo plano).** Un agente por parte, cada uno en su rama o `git worktree`.
   Prompt autosuficiente: contexto, archivos que edita y cuáles no, criterios, cómo verificar, qué reportar. Commits
   locales; sin `push` ni PR. Pedidos nuevos al agente dueño con `SendMessage`, no a uno nuevo sobre los mismos archivos.
4. **Verificar (Haiku · `verificador`).** Lo que corre el CI (ver skill `bloque`), `python tools/kit/privacy_scan.py`,
   `revisar_enlaces` si se tocaron rutas, catálogo o plantillas. Reporta; no corrige.
5. **Revisar (Opus · `revisor-bloque`).** Lee el diff completo: criterios contra pruebas, seguridad y privacidad
   (`AGENTS.md` «Reglas que salieron de las revisiones»), funciona **sin JS**, escritorio y 375 px, **claro y oscuro** (el
   dueño usa oscuro). Lo bloqueante vuelve a la fase 3 al mismo implementador.
6. **Publicar y cerrar (Opus · skill `cerrar-pendientes`).** Skill `revision-privacidad`, push, PR con la plantilla, CI en
   verde y fusión con merge commit. La persona despliega.

Ronda chica (un archivo, un arreglo): Opus puede hacer 2–5 solo, pero no se salta la verificación ni la revisión del diff.

## Cuándo preguntar a la persona (y detener esa parte)

- Seguridad, privacidad, datos de clientes o personales en un repositorio público.
- Una decisión de producto o una pregunta abierta de `docs/DECISIONES.md`.
- Dependencias nuevas, cambios de despliegue o producción, borrar ramas remotas, cerrar PR ajenos.

Lo demás ambiguo se anota como pregunta abierta y se sigue con la propuesta por defecto.

## Ahorro de tokens

- Una búsqueda la hace un solo agente; no la repitas en paralelo.
- Informes cortos (archivos, decisiones, pruebas, pendientes); el detalle se lee del diff.
- Agente con el modelo equivocado y poco avance: detenlo, descarta lo hecho a medias y relánzalo con el correcto.
