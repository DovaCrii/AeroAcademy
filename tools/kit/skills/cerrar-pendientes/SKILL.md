---
name: cerrar-pendientes
description: Publica y cierra el trabajo en GitHub de {{PROYECTO}} - push, PR con plantilla, espera real del CI, fusiones apiladas con merge commit, ramas y worktrees ya fusionados, PR de dependabot - y deja un informe corto con lo hecho y lo que decide la persona. Usar al publicar un cambio, al pedir "cierra los pendientes", "fusiona lo que esté en verde" o al terminar una ronda.
---

# Publicar y cerrar pendientes

Regla: **el agente sube, espera el CI en verde y fusiona con merge commit; la persona despliega.** Reparto: **Haiku 5.5
medio** inventaría y vigila el CI; **Sonnet 5.5 medio** arregla lo rojo; **Opus 5.5 medio** decide el orden y fusiona.

## Límites

- Solo `gh pr merge N --merge`. Nunca *squash*, *rebase*, `--admin`, CI saltado o en rojo, `push --force`.
- Nunca cambiar *settings* o visibilidad del repositorio, publicar *releases* ni tocar {{ARCHIVOS_DE_DESPLIEGUE}}.
- Sin pedido de la persona solo se **listan**: borrar ramas remotas, cerrar PR ajenos o sin fusionar, dependabot mayor.

## Pasos

1. **Antes.** Skill `revision-privacidad` en verde y diff revisado.
2. **Publicar.** `git push -u origin <rama>`; `gh pr create --base <base> --body-file <archivo>` con la plantilla.
3. **Inventario (Haiku).** `gh pr list --state open --json number,title,headRefName,baseRefName,mergeStateStatus,statusCheckRollup`,
   `gh run list --limit 10`, `git worktree list`, `git branch --merged origin/main`.
4. **Esperar el CI de verdad.** `gh pr checks --watch` sale al instante si la corrida no arrancó: espera a que exista
   (`gh run list --branch <rama>`) y vigílala con `gh run watch <id> --exit-status`. Vale la última corrida.
5. **Arreglar lo rojo (Sonnet).** `gh run view <id> --log-failed`, arreglo en la rama, nuevo push.
6. **Fusionar en orden (Opus).** Apilados de abajo hacia arriba: fusiona, `gh pr edit N --base main`, espera su CI, fusiona.
7. **Después.** `git fetch`, `main` local al día; avisa si hay que desplegar y qué variables nuevas hay.
8. **Limpieza** solo con pedido; sin pedido, la lista.
9. **Informe corto:** fusionados (enlace), en rojo y por qué, lo que espera decisión, lo abierto a propósito.
