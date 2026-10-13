# Adoptar el estándar en un repositorio

Pensado para AeroConvert, AeroControl, AeroBim y los que vengan (AeroLink, Aeroplanner). Estimado: 30-60 min por repo.

## Reglas de oro

- Se hace en **una rama o un worktree aparte** (`git worktree add ../wt-estandar -b estandar-trabajo origin/main`), nunca en el
  árbol de trabajo de otra rama con cambios sin confirmar.
- **Solo aditivo.** Se agregan archivos; no se reescribe lo existente.
- **Nunca sobrescribir** un `CLAUDE.md` o `AGENTS.md` que ya exista: se fusionan las secciones que falten.
- **Nunca tocar** despliegue ni producción (Dockerfile, `deploy/`, unidades systemd, workflows de despliegue, `.env*`).
- Sin push ni PR hasta que la persona lo decida.

## Pasos

1. **Preparar.** `git fetch`, crear la rama/worktree, correr las pruebas actuales para tener la línea base.
2. **Mirar qué hay.** ¿Existen `CLAUDE.md`, `AGENTS.md`, `.claude/`, `.github/workflows/`, plantilla de PR? Anotar los huecos.
3. **Rellenar placeholders.** `{{PROYECTO}}`, `{{COMANDO_PRUEBAS}}`, `{{COMANDO_LINT}}`, `{{COMANDO_FORMAT_CHECK}}`, `{{PREFIJO_RAMA}}`,
   `{{VISIBILIDAD}}` (pública/privada), `{{ARCHIVOS_DE_DESPLIEGUE}}`.
4. **AGENTS.md.** Si no existe, créalo desde `AGENTS.sections.md`. Si existe, agrega solo las secciones que falten.
5. **CLAUDE.md.** Si no existe, copiar `CLAUDE.md.tpl` (importa `@AGENTS.md`). Si existe, agregar la línea `@AGENTS.md` y la sección
   «Cómo trabajamos» sin borrar nada.
6. **`.claude/settings.json`.** Desde `settings.json.tpl`; si existe, fusionar `permissions.allow` y `permissions.deny`.
   Ojo: `Read(./.env.*)` también bloquea `.env.example`; si el agente debe leerlo, quita esa línea y deja `.env` y las demás.
7. **Skills.** Copiar `skills/*` a `.claude/skills/` los que no existan (no duplicar equivalentes).
8. **Privacidad.** Copiar `privacy_scan.py` a `tools/` (o `tools/kit/`), correrlo; los hallazgos reales se corrigen, los falsos positivos
   (dominios ficticios, datos de prueba) van a `.privacy-scan.json`. Agregar `ci-privacy-step.yml` al CI.
   Confirmar que `.gitignore` incluye `private/`, `.env`, `.env.*` y `!.env.example`.
9. **Plantilla de PR.** Copiar `PULL_REQUEST_TEMPLATE.md` a `.github/` solo si no hay una.
10. **Guía.** Copiar `guia-companeros.md` a `docs/` si hay compañeros no desarrolladores.
11. **Validar.** Pruebas, lint, `privacy_scan.py`, abrir `claude` y comprobar que carga `CLAUDE.md` (`/memory`) y los permisos (`/permissions`).
12. **Entregar.** Commits pequeños en la rama; informar a la persona qué se agregó y qué dudas quedaron. Ella decide el push y el PR.

## Criterio de listo

- `CLAUDE.md` importa `@AGENTS.md`; `AGENTS.md` tiene las secciones del kit.
- `.claude/settings.json` válido, con `deny` de secretos.
- CI con revisión de privacidad en verde.
- Ningún archivo de despliegue modificado (`git diff --stat` lo confirma).
