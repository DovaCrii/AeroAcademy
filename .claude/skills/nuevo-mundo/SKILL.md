---
name: nuevo-mundo
description: Diseña e implementa el mundo visual de una especialidad en AeroAcademy (civil, survey, mechanical, aero…) siguiendo la gramática del mundo Arquitectura y el contrato de docs/MUNDOS.md. Usar cuando una ruta necesita un mundo que no existe o se quiere rediseñar uno.
---

# Nuevo mundo

Leer primero:
- `docs/MUNDOS.md`: gramática común, los cinco mundos y el contrato técnico.
- `legacy/ruta-forma-revit/static/index.html`: la referencia. Estudiar cómo cada pieza es un elemento del oficio: cajetín, corte, Project Browser, schedules y nubes de revisión.

## Pasos

1. **Metáfora:** tomar la de MUNDOS.md o proponer una nueva que salga de la herramienta real que usa esa especialidad. Prueba: alguien del oficio debe reconocer cada pieza sin explicación.
2. **Las 8 piezas de la gramática:**
   - portada;
   - recorrido (cómo se ve el avance);
   - navegador;
   - panel del capítulo (compartido; solo piel);
   - tablas;
   - nota del oficio;
   - escalera de certificación;
   - marco.

   Escribir una línea por pieza antes de codificar.
3. **Archivos:**
   - `core/static/worlds/<world>.css`: tokens en `:root` y `[data-world=<world>]`, con modos claro y oscuro.
   - `core/templates/worlds/<world>/cover.html`, `journey.html`, `browser.html` y `note.html`.
4. **Recorrido en SVG inline:**
   - Recibe `levels` con `pct`, `done` y `team_marks`; los estados se dibujan con clases CSS, no con JS.
   - La animación es opcional y se desactiva con `prefers-reduced-motion`.
5. **Teo:** generar su atuendo para el mundo con la skill `sprite-8bit` (ver la lista en VISION.md).
6. **Comprobar:**
   - sin desborde a 390 px, en claro y oscuro;
   - lectura sin JS;
   - contraste AA en texto;
   - foco visible.
7. **Prueba de plantilla:** renderizar una ruta de ejemplo con el mundo y verificar que aparecen todas las piezas.

## Reglas

- Solo SVG y CSS, sin librerías ni imágenes pesadas. Las fotos de portada van en `core/static/worlds/<world>/` y deben ser propias o con licencia.
- La capa de juego (XP, insignias, cabecera) **no** se cambia por mundo.
- Los términos de software van en inglés con `.term`.
