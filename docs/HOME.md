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
