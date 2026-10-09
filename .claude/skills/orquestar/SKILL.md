---
name: orquestar
description: Cómo repartir una ronda de trabajo de AeroAcademy entre subagentes - qué modelo usa cada uno (Opus orquesta, Sonnet construye, Haiku verifica y busca), en qué orden y con qué reglas, para no gastar tokens de más. Usar cuando una petición tenga varias partes independientes o mucho trabajo mecánico.
---

# Orquestar una ronda (Opus + Sonnet + Haiku)

Decisión del dueño (2026-10-09): **Opus es el orquestador principal**; los subagentes se reparten por modelo según lo que
requiera la tarea, para optimizar tokens y tiempo.

## Quién hace qué

| Modelo | Rol | Agentes (`.claude/agents/`) | Ejemplos |
|---|---|---|---|
| **Opus** (sesión principal) | Orquesta: entiende el pedido, decide, reparte, revisa, integra, prueba en el navegador, abre y fusiona el PR | — | Planificar la ronda, resolver dudas con la persona, revisar lo entregado |
| **Sonnet** | Construye | `bloque-dev`, `artista-pixel`, `curador-semillas`, `revisor-bloque` | Código y migraciones, diseño y CSS, sprites, rutas y cursos, revisión independiente |
| **Haiku** | Mecánico y de lectura | `verificador-enlaces`, `explorador` | Buscar dónde está algo, inventarios, revisar enlaces, resumir salidas de pruebas o logs |

Al lanzar con la herramienta Agent, pasa siempre `model` explícito (`"sonnet"` o `"haiku"`), aunque el agente lo traiga en
su definición: si el tipo no está disponible y se usa `general-purpose`, sin `model` heredaría Opus.

## Orden de una ronda

1. **Entender (Opus).** Separar el pedido en partes independientes. Lo que dependa de una decisión de la persona se pregunta
   antes (p. ej. datos internos en un repositorio público).
2. **Explorar (Haiku, opcional).** `explorador` ubica archivos y dueños antes de repartir.
3. **Repartir (Sonnet, en paralelo y en segundo plano).** Un agente por parte, con **dueños de archivos sin cruce**: el
   prompt dice qué archivos edita y cuáles no toca. Sin `git` en los subagentes.
4. **Ajustar en marcha (Opus).** Pedidos nuevos de la persona se mandan al agente dueño con SendMessage; no se lanza otro
   agente sobre los mismos archivos.
5. **Integrar (Opus).** Leer el informe, mirar el diff, correr `tools/preflight.py`, revisar en el navegador (escritorio y
   375 px, claro y oscuro).
6. **Verificar (Haiku).** `verificador-enlaces` al final de toda ronda que tocó rutas, catálogo o plantillas.
7. **Publicar (Opus).** Rama, PR, CI en verde, fusión con merge commit (`docs/FUSIONES.md`), comandos para la VM.

## Ahorro de tokens

- No dupliques: si un agente ya busca algo, no lo busques en paralelo.
- Prompts autosuficientes y cortos: contexto, archivos dueños, criterios de aceptación, cómo verificar, qué reportar.
- Pide informes concisos (archivos, decisiones, pruebas); los detalles se leen del diff.
- Si un agente arrancó con el modelo equivocado y lleva poco, detenlo y relánzalo con el correcto; descarta sus cambios a
  medias para partir limpio.
