---
name: plan-y-bloque
description: Trabaja un cambio de {{PROYECTO}} en bloques pequeños - plan corto, rama, pruebas, código, lint y commits locales - y lo entrega a cerrar-pendientes para publicarlo. Usar al pedir una función nueva, un arreglo o "continúa con el siguiente bloque".
---

# Plan y bloque

Reparto según la skill `orquestar`: **Opus 5.5 medio** planifica y revisa; **Sonnet 5.5 medio** implementa;
**Haiku 5.5 medio** comprueba. Publicar y fusionar es la skill `cerrar-pendientes`.

1. **Plan (Opus, sin editar).** Objetivo, archivos, pruebas de cada criterio, riesgos y qué queda fuera. Visto bueno de
   la persona si no es trivial; seguridad, privacidad o producto siempre se preguntan.
2. **Rama.** `git switch -c {{PREFIJO_RAMA}}-<tema>` desde `main` (nunca trabajar sobre `main`).
3. **Pruebas primero (Sonnet)** cuando se pueda; luego el código que las pasa.
4. **Pasos pequeños.** Un cambio cohesivo por commit, en español e imperativo, ≤ 72 caracteres ("Agrega el filtro por
   fecha"); sin Conventional Commits.
5. **Verificar (Haiku).** `{{COMANDO_PRUEBAS}}`, `{{COMANDO_LINT}}`, `{{COMANDO_FORMAT_CHECK}}` y
   `python tools/kit/privacy_scan.py` en verde.
6. **Revisar (Opus).** Diff completo contra los criterios; lo bloqueante vuelve al paso 3.
7. **Documentación.** Plan y docs que cambien.
8. **Publicar.** Skill `cerrar-pendientes`: push, PR con la plantilla, CI en verde, merge commit. La persona despliega.

Nunca: fusionar con el CI en rojo, `push --force` sobre `main`, subir secretos o datos reales, ni tocar despliegue sin pedido.
Recuperación: `git restore` o `git switch` a la rama anterior; `git revert` si ya se fusionó; no borrar ramas.
