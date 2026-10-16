---
name: nuevo-mundo
description: Diseña e implementa el mundo visual de una especialidad de AeroAcademy (survey, mechanical u otra; hoy existen architecture, civil y aero) o una figura temática de ruta, con la gramática y el contrato de docs/MUNDOS.md, funcionando sin JS y en claro y oscuro. Usar cuando una ruta necesita un mundo o una figura que no existe, o al rediseñar uno.
---

# Nuevo mundo (o figura temática)

Reparto (`orquestar`): **Opus 5.5 medio** (`disenador`) fija la metáfora, las 8 piezas y el plan, y revisa el
resultado; **Sonnet 5.5 medio** (`bloque-dev`, `artista-pixel` para el atuendo de Nala) implementa; **Haiku 5.5 medio**
(`verificador`) corre pruebas y enlaces.

Leer: `docs/MUNDOS.md` (gramática y contrato), un mundo ya hecho (`apps/core/templates/worlds/architecture/` +
`apps/core/static/worlds/architecture.css`; `legacy/` solo como referencia visual), `world_context()` en
`apps/progress/services.py`. Figuras por ruta: `docs/MEJORAS_UX.md` P1-9.

## Contrato

`paths:detail` usa `worlds/<world>/path.html` si existe (si no, la vista genérica); con `X-Partial` devuelve `_app.html`.

| Archivo | Qué es |
|---|---|
| `worlds/<world>/path.html` | Página: CSS/JS del mundo, portada y `<div id="path-app" data-enhance-root>` con `_app.html` |
| `worlds/<world>/_app.html` | Lo que cambia al marcar o responder: recorrido, navegador y panel |
| `cover.html`, `journey.html`, `browser.html`, `_panel.html` | Piezas de la gramática |
| `static/worlds/<world>.css` | Tokens y piel (claro y oscuro) |
| `static/worlds/<world>-cover.js` | Opcional; respeta `prefers-reduced-motion` |

Contexto: `path`, `chapters` (`level`, `milestones`, `quiz`, `pct`, `done`, `total`, `complete`), `current`,
`prev_code`, `next_code`, `building`, `stats`, `goals`, `goal`, `intro`, `flow`, `program_code`, `program_title`.
Acciones comunes (`progress:toggle_milestone`, `answer_quiz`, `set_goal`): formularios con `data-enhance` y `data-fid`.

## Pasos

1. **Metáfora (Opus):** una línea por cada una de las 8 piezas; alguien del oficio la reconoce sin explicación.
2. **Datos:** otra geometría va en un `_<recorrido>()` de `progress/services.py` expuesto en `world_context()`; nada de
   cálculo en la plantilla.
3. **Plantillas y CSS** con prefijo de clase propio (`ar-` en Arquitectura). Recorrido en SVG inline, estados por clase
   (`on`, `done`) y enlaces `?nivel=<code>`: **todo funciona sin JS**.
4. **Notas del equipo:** `_panel.html` cierra con `{% load community_tags %}` y `{% level_notes path current.level.code %}`;
   forma del oficio en `apps/community/static/community/notes.css` (`.world-<world> .note`).
5. **Nala:** su atuendo del mundo con la skill `sprite-8bit` (`apps/core/static/game/teo/teo-<world>.svg`).
6. **Pruebas** (`tests/test_progress.py`, `tests/test_notes.py`): todas las piezas, porcentajes, lectura sin JS,
   respuesta parcial, texto escapado, el equipo en el recorrido.
7. **Navegador:** escritorio y 375 px, claro y oscuro, sin desborde; marcar un hito actualiza sin recargar.

## Reglas

- Solo SVG y CSS, sin librerías ni imágenes pesadas; fotos propias en `static/worlds/<world>/` (nada de clientes).
- La capa de juego (XP, insignias, cabecera) no cambia por mundo.
- Términos de software con el filtro `terms` (`*término*` → `.term`, escapa HTML).
- Un mundo no implementado no rompe nada: la ruta usa la vista genérica.
