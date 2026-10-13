# Estándar de trabajo con Claude Code (suite Aero)

Método extraído de AeroAcademy (`AGENTS.md`, `.claude/skills`, `.claude/agents`, CI, plantilla de PR, `docs/FLUJO_GITHUB.md`) y del
tutorial de vibe coding de roadmap.sh. Aplica a AeroAcademy, AeroConvert, AeroControl, AeroBim y los próximos (AeroLink, Aeroplanner).
Plantillas listas para copiar en `tools/kit/`; cómo adoptarlas en `tools/kit/adopt.md`.

## 1. Principios

1. **Git primero.** Todo vive en git, con ramas; nada de trabajo suelto sobre `main`.
2. **El briefing es parte del repo.** `CLAUDE.md` (corto, importa `@AGENTS.md`) y `AGENTS.md` (stack, comandos, reglas, definición de terminado).
3. **Plan antes de código.** Cada función parte de un plan corto aprobado por la persona.
4. **Pasos pequeños e iterativos.** Un bloque = una rama = un PR revisable.
5. **Probar siempre.** El código sin prueba no está terminado.
6. **Persona al mando.** El agente construye y deja el PR listo; la persona revisa y fusiona.
7. **Siempre hay vuelta atrás.** Ramas, commits pequeños y despliegue con rollback.

## 2. El ciclo

**plan → bloque pequeño → pruebas → PR → CI → revisión y fusión humana**

1. Plan en modo plan (sin editar): qué, dónde, cómo se prueba, qué queda fuera. Dudas = pregunta abierta, no decisión propia.
2. Rama `bloque-<n>-<tema>` (o `fix-`/`docs-`) desde `main`.
3. Pruebas primero cuando se pueda; commits chicos en español e imperativo.
4. Lint y pruebas locales, revisión de privacidad (`tools/kit/privacy_scan.py`).
5. `git push -u origin <rama>` y `gh pr create` con la plantilla; revisar `gh pr checks`. Un PR en rojo no está listo.
6. La persona revisa el diff y fusiona (merge commit). Después, despliegue según `docs/PRODUCCION.md`, con rollback.

## 3. Política de modelos

| Modelo | Rol |
|---|---|
| **Opus** | Orquesta: entiende, decide, reparte, revisa, integra y publica el PR |
| **Sonnet** | Construye: código, pruebas, documentos, revisión independiente |
| **Haiku** | Revisa lo mecánico: búsquedas, inventarios, enlaces, resumen de logs |

Al lanzar un subagente se pasa `model` explícito. Cada subagente tiene dueños de archivos sin cruce (idealmente su propio
`git worktree`), no hace `push` ni PR, y quien lo lanza verifica el resultado. Detalle en la skill `orquestar`.

## 4. Privacidad en repositorios públicos

- **Va a git:** código, documentación, datos de ejemplo inventados, plantillas, semillas públicas.
- **No va a git:** secretos (`.env`, claves, tokens, certificados), datos de clientes, datos personales (RUT, correos y teléfonos reales),
  nubes de puntos o planos de proyectos, bases de datos, contenido de `private/`.
- Lo privado vive en `private/` (en `.gitignore`), variables de entorno o un gestor de secretos.
- `tools/kit/privacy_scan.py` corre local y en CI: falla con `private/`, `.env`, claves (`nvapi-`, `sk-`, `AKIA`), llaves privadas,
  correos de dominios reales, RUT y archivos basura que empiezan con `--`. Los falsos positivos se declaran en `.privacy-scan.json`;
  las reglas no se debilitan.
- Si algo sensible llegó a un commit: avisar, rotar la clave y decidir con la persona cómo limpiar el historial (borrar el archivo no basta).
- Claude Code no lee `.env*`, claves ni `private/` (`deny` en `.claude/settings.json`). No pegar datos sensibles en el chat.

## 5. Definición de terminado

- Criterios de aceptación cubiertos por pruebas.
- Pruebas, lint y formato en verde, también en el CI del PR.
- Revisión de privacidad en verde.
- Documentación y plan actualizados.
- Rama subida y PR abierto con resumen en español (qué cambia, cómo probarlo, qué queda).
- Despliegue solo cuando la persona lo decide, con plan de rollback.

## 6. Recuperación

- Nunca `push --force` sobre `main`, ni reescribir ramas compartidas.
- Un bloque fallido se descarta cerrando la rama; `main` no se toca. Para deshacer: `git revert` (cambios ya fusionados) o `git restore`/`git switch` (locales).
- Fusión con merge commit para poder revertir el bloque completo.
- Despliegue: guardar el commit anterior, probar con humo (`tools/_smoke_prod.py` en AeroAcademy) y volver al commit previo si falla.
- Cambios de base de datos: migraciones pequeñas, nunca editar una ya aplicada, respaldo antes de migrar.

## 7. Brechas encontradas en AeroAcademy

1. **Faltaba `CLAUDE.md`.** Solo existía `AGENTS.md`; Claude Code lee `CLAUDE.md`. Resuelto con un `CLAUDE.md` que importa `@AGENTS.md`.
2. **Sin revisión de privacidad en el CI.** Solo había `.gitignore` y revisión manual; un archivo basura (`--help`) llegó al repo.
   Resuelto con `privacy_scan.py` en el CI y el archivo eliminado.
3. **No había `.claude/settings.json` compartido** con permisos conservadores. Agregado.
4. **Pruebas lentas** (suite grande, pasos largos en el CI): por medir y acotar (marcar pruebas lentas, ejecutar en paralelo con `pytest-xdist`
   y correr solo las del bloque durante el desarrollo). Pendiente.
5. Los datos de prueba usan dominios reservados (`example.com`); el usuario y la IP del servidor no se publican en el repo (van como `example@<IP-DE-LA-VM>`). El resto de dominios ficticios (`empresa.cl`, etc.) están declarados en `.privacy-scan.json`.

## 8. Checklist para adoptarlo en un repo

- [ ] Rama o worktree aparte; línea base de pruebas
- [ ] `AGENTS.md` con las secciones de `tools/kit/AGENTS.sections.md` (fusionar, nunca reemplazar)
- [ ] `CLAUDE.md` que importa `@AGENTS.md` y resume cómo trabajamos
- [ ] `.claude/settings.json` con `deny` de secretos
- [ ] Skills `plan-y-bloque`, `revision-privacidad`, `orquestar`
- [ ] `privacy_scan.py` + paso en el CI + `.gitignore` con `private/` y `.env*`
- [ ] Plantilla de PR y guía para compañeros
- [ ] Cero cambios en archivos de despliegue o producción
- [ ] Pruebas, lint y revisión de privacidad en verde
