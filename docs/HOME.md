# Portada (home): estructura y por qué

Problema: la portada era un solo scroll muy largo (unas 9 pantallas a 1280×800) con todo apilado.

Decisiones (sin quitar contenido ni rutas):

1. **Hero compacto + selector de disciplinas.** Los círculos ya no se recortan (rejilla que envuelve y se centra). Son un selector: «Todas» o una disciplina.
2. **Rutas justo bajo el selector.** Sin JS funciona con radios hermanos (`#d-<slug>:checked ~ .w-sec-routes`, estilos generados en la plantilla); con JS solo se añade scroll suave, `#d-<slug>` en la URL y resaltado de sección.
   «Todas» muestra un resumen (2 rutas por disciplina, 4 en Transversal) con «Ver las N →»; una disciplina muestra todas sus rutas en tarjetas (icono, título, empresa, estado).
3. **Navegador pegajoso** (`.w-jump`): Tus rutas · Tu misión · Tu avance · Módulos · Destacados · Suite Aero (solo anclas de la página; la cinta duplicada de accesos rápidos se quitó, la navegación vive en la cabecera).
4. **Bloques secundarios plegados** con `<details>` (Módulos, Destacados, Suite Aero): el contenido sigue en el HTML y se abre con el navegador o por ancla.
5. **Números grandes** (contornos, rotación leve, sombra de color) en secciones, «Primeros pasos», proceso del equipo y pasos de portadas de curso (`.lv-flow .n`, `.ar-sn span`); el HTML («// 01») se conserva.

Hooks conservados: `#rutas`, `#mision`, `#avance`, `#equipo`, `#modulos`, `#destacados`, `#suite`, `data-d`, `.w-mod-ill`, `.w-app-go`.

## Tus plataformas oficiales (D43)

Franja `#oficiales` justo bajo el bloque de bienvenida y «Empieza aquí» (antes de «Rutas por disciplina», sin cambiar lo que ya
estaba arriba). Bentley y Autodesk son las plataformas oficiales de la academia (Bentley primero) y la franja muestra, por cada una
y **solo para quien mira**: cursos hechos de cuántos y su porcentaje, una barra `<progress>` accesible, los esenciales hechos de los
totales y un botón «Seguir con <siguiente curso sugerido>». Sin avance, en vez de ceros muestra el primer paso («Empezar con …»).
«Hecho» es lo mismo que en las rutas externas: credencial verificada; en revisión = pendiente. No aparece sin catálogo.
Código: `apps/catalog/official.py` (`home_summary`, 6 consultas fijas), plantilla `catalog/partials/official_panel.html` y CSS
`catalog/official.css` (compartidos con el catálogo). Detalle y mediciones en `docs/MEJORAS_CATALOGO.md`, sección 9.

## Suite Aero (oculta por ahora)

El bloque «Suite Aero» de la portada (y su acceso en la barra de la página) está oculto por decisión del dueño (2026-10-19). Se vuelve a mostrar con la variable de entorno `SHOW_SUITE_AERO=1` (ajuste `SHOW_SUITE_AERO`). El texto de auspicio del pie del sitio se mantiene.

