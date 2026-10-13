---
name: plan-y-bloque
description: Trabaja un cambio de {{PROYECTO}} en bloques pequeños - plan corto, rama, pruebas, código, lint, PR listo. Usar al pedir una función nueva, un arreglo o "continúa con el siguiente bloque".
---

# Plan y bloque

Regla de fondo: **el agente construye, sube y deja el PR listo; la persona revisa y fusiona.**

1. **Plan primero (sin editar).** Lee lo necesario y propone: objetivo, archivos que tocará, pruebas, riesgos y qué queda
   fuera. Espera el visto bueno si el cambio no es trivial. Si falta información, anótala como pregunta abierta.
2. **Rama.** `git switch -c {{PREFIJO_RAMA}}-<tema>` desde `main` (nunca trabajar sobre `main`).
3. **Pruebas primero** cuando sea posible: escribe la prueba que falla y luego el código que la pasa.
4. **Pasos pequeños.** Un cambio cohesivo por commit, en español e imperativo ("Agrega el filtro por fecha").
   Tras cada paso corre `{{COMANDO_PRUEBAS}}`; si falla, arregla antes de seguir.
5. **Calidad.** `{{COMANDO_LINT}}` y `{{COMANDO_FORMAT_CHECK}}` en verde.
6. **Privacidad.** Revisa el diff con la skill `revision-privacidad` y corre `python tools/kit/privacy_scan.py`.
7. **Documentación.** Actualiza el plan o los docs que cambien.
8. **Entrega.** `git push -u origin <rama>` y `gh pr create` con la plantilla; revisa `gh pr checks`.
   Informa: enlace del PR, resultado del CI y qué decide la persona.

Nunca: fusionar, `push --force` sobre `main`, subir secretos o datos reales, ni cambiar archivos de despliegue sin pedirlo.
Plan de recuperación: si un paso sale mal, `git switch` a la rama anterior o `git restore` del archivo; no borrar ramas.
