---
name: cerrar-pendientes
description: Publica y cierra el trabajo en GitHub de un repositorio de la suite Aero - push, PR con plantilla, espera real del CI, fusiones apiladas con merge commit, ramas y worktrees ya fusionados, PR de dependabot - y deja un informe corto con lo hecho y lo que decide la persona. Usar al publicar un bloque, al pedir "cierra los pendientes", "fusiona lo que esté en verde", "limpia GitHub" o al terminar una ronda.
---

# Publicar y cerrar pendientes

Regla (decisión de la persona, 2026-10-13): **el agente sube, espera el CI en verde y fusiona con merge commit; la persona
despliega.** Es la última fase de `orquestar`. Reparto: **Haiku 5.5 medio** (`verificador`) inventaría y vigila el CI;
**Sonnet 5.5 medio** arregla lo rojo; **Opus 5.5 medio** decide el orden, revisa y fusiona.

## Límites

- Solo `gh pr merge N --merge`. Nunca *squash*, *rebase*, `--admin`, CI saltado o en rojo, `push --force`.
- Nunca cambiar *settings* o visibilidad del repositorio, ni publicar *releases*, ni tocar despliegue o producción.
- Sin pedido de la persona solo se **listan**: borrar ramas remotas, cerrar PR ajenos o sin fusionar, dependabot mayor.

## Pasos

1. **Antes de publicar.** Skill `revision-privacidad` en verde y revisión del diff hecha (fase Revisar de `orquestar`).
2. **Publicar.** `git push -u origin <rama>`; `gh pr create --base <base> --body-file <archivo>` con la plantilla de
   `.github/` (qué cambia, criterios con su prueba, cómo probarlo, pendiente).
3. **Inventario (Haiku).**
   ```bash
   gh pr list --state open --json number,title,headRefName,baseRefName,isDraft,mergeStateStatus,statusCheckRollup
   gh run list --limit 10
   git worktree list && git branch --merged origin/main
   ```
   Clasifica: *listo*, *esperando CI*, *en rojo*, *conflicto*, *dependabot*, *obsoleto*.
4. **Esperar el CI de verdad.** `gh pr checks --watch` termina al instante con «no checks reported» si la corrida no
   arrancó: espera a que aparezca (`gh run list --branch <rama>`) y vigílala con `gh run watch <id> --exit-status`.
   Un push nuevo cancela la anterior: vale la última.
5. **Arreglar lo rojo (Sonnet).** `gh run view <id> --log-failed`, arreglo en la rama, nuevo push. «Falló algo ajeno» se
   demuestra o se reintenta; no se fusiona encima.
6. **Fusionar en orden (Opus).** Apilados de abajo hacia arriba: fusiona, `gh pr edit N --base main`, espera su CI,
   fusiona. Cadenas largas: `python tools/fusionar_cadena.py` (`docs/FUSIONES.md`). Sin `--delete-branch` hasta el final.
7. **Después.** `git fetch`, `main` local al día, `python tools/preflight.py`. Avisa a la persona si hay que desplegar
   (`docs/PRODUCCION.md`) y qué variables nuevas hay.
8. **Limpieza.** Con pedido: ramas remotas fusionadas, `git worktree remove`, `git branch -d`. Sin pedido: solo la lista.
9. **Informe corto:** PR fusionados (enlace), en rojo y por qué, lo que espera decisión, lo abierto a propósito.

## Qué decide la persona

Dependabot mayor o que cambia producción · PR de otra sesión o persona · borrar ramas remotas o cerrar sin fusionar ·
todo lo de seguridad, privacidad o una decisión abierta de `docs/DECISIONES.md`.
