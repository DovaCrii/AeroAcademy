---
name: nuevo-mundo
description: Diseña e implementa el mundo visual de una especialidad en AeroAcademy (civil, survey, mechanical, aero…) siguiendo la gramática del mundo Arquitectura y el contrato de docs/MUNDOS.md. Usar cuando una ruta necesita un mundo que no existe o se quiere rediseñar uno.
---

# Nuevo mundo

Leer primero:
- `docs/MUNDOS.md`: gramática común, los cinco mundos y el contrato técnico.
- **El mundo ya implementado:** `apps/core/templates/worlds/architecture/` y `apps/core/static/worlds/architecture.css`
  (Bloque 3). Es la plantilla real a copiar; el prototipo viejo (`legacy/`) solo es referencia visual.
- `apps/progress/services.py` → `world_context()`: el contexto común que reciben todos los mundos.

## Contrato (lo que `paths:detail` espera)

`paths:detail` usa el mundo si existe `worlds/<world>/path.html`; si no, cae a la vista genérica.
Con la cabecera `X-Partial` renderiza `worlds/<world>/_app.html` (solo el fragmento).

| Archivo | Qué es |
|---|---|
| `worlds/<world>/path.html` | Página completa: carga el CSS/JS del mundo, la portada y `<div id="path-app" data-enhance-root>` con `_app.html` |
| `worlds/<world>/_app.html` | Todo lo que cambia al marcar o responder: recorrido, navegador y panel |
| `worlds/<world>/cover.html`, `journey.html`, `browser.html`, `_panel.html` | Las piezas de la gramática |
| `static/worlds/<world>.css` | Tokens y piel del mundo (claro y oscuro) |
| `static/worlds/<world>-cover.js` | Opcional: animación de la portada (respeta `prefers-reduced-motion`) |

Contexto recibido: `path`, `chapters` (cada uno con `level`, `milestones`, `quiz`, `pct`, `done`, `total`,
`complete`), `current`, `prev_code`, `next_code`, `building` (geometría del recorrido, hoy la del edificio),
`stats`, `goals`, `goal`, `intro`, `flow`, `program_code`, `program_title`.
Las acciones (`progress:toggle_milestone`, `answer_quiz`, `set_goal`) son comunes: los formularios llevan
`data-enhance` y `data-fid` (para devolver el foco tras actualizar).

## Pasos

1. **Metáfora:** tomar la de MUNDOS.md o proponer una que salga de la herramienta real. Prueba: alguien del
   oficio reconoce cada pieza sin explicación. Escribir una línea por cada una de las 8 piezas antes de codificar.
2. **Datos del recorrido:** si el mundo necesita otra geometría (progresivas, curvas de nivel, waypoints),
   agregar un `_<recorrido>()` en `progress/services.py` junto a `_floors()` y exponerlo en `world_context()`;
   no calcular avance en la plantilla.
3. **Plantillas y CSS** según la tabla. Clases con prefijo del mundo (`ar-` en Arquitectura) para no chocar.
4. **Recorrido en SVG inline**, con estados por clases CSS (`on`, `done`) y enlaces `?nivel=<code>` para que
   funcione sin JS.
5. **Teo:** su atuendo para el mundo con la skill `sprite-8bit`.
6. **Pruebas** (ver `tests/test_progress.py`): la página renderiza todas las piezas; porcentajes; lectura sin
   JS; respuesta parcial; texto escapado; el equipo aparece en el recorrido.
7. **Comprobar en el navegador:** escritorio y 390 px, claro y oscuro, sin desborde; interacción real
   (marcar un hito actualiza sin recargar).

## Reglas

- Solo SVG y CSS, sin librerías ni imágenes pesadas. Las fotos propias van en `static/worlds/<world>/`.
- La capa de juego (XP, insignias, cabecera) **no** se cambia por mundo.
- Los términos de software van en inglés con el filtro `terms` (`*término*` → `.term`), que escapa el HTML.
- Un mundo no implementado no rompe nada: la ruta usa la vista genérica.
