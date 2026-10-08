# Mundos · un diseño único por especialidad

Cada ruta vive en un **mundo**: un lenguaje visual tomado de la herramienta que enseña. El primero, Arquitectura,
ya existe y es la referencia: `legacy/ruta-forma-revit/static/index.html`. Los demás siguen su misma *gramática*
con otra metáfora.

**Regla:** la originalidad está en el mundo; la coherencia, en la capa de juego. XP, insignias, Teo, la hoja de
personaje y la cabecera son iguales en todos los mundos.

## Gramática común (lo que todo mundo debe tener)

| Pieza | Arquitectura (referencia) | Qué hace |
|---|---|---|
| 1. Portada | Nube de puntos animada + flujo Captura → Nube → Forma → Revit → Entrega | Presenta la campaña con imagen propia del oficio |
| 2. Recorrido | Corte del edificio: cada piso es un nivel y se rellena con el avance | Muestra el avance personal y la posición del equipo de un vistazo |
| 3. Navegador | *Project Browser · Levels* | Lista de capítulos con porcentaje y barra |
| 4. Panel del capítulo | Meta, recursos, hitos, quiz y notas | Igual en todos los mundos: mismo componente, otra piel |
| 5. Tablas | *Schedules* con encabezado tipo Revit | Equipo, flujo, glosario, kit |
| 6. Nota del oficio | Nube de revisión (*redline*) | Forma visual de las notas del equipo |
| 7. Escalera de certificación | Peldaños con certificaciones | Camino hacia la *Reliquia* del vendor |
| 8. Marco | Cajetín y láminas A-101 | Identidad de "documento técnico" |

## Los cinco mundos

### Arquitectura · `architecture` (Autodesk Forma + Revit) · existe
Plano arquitectónico: corte A-A, Project Browser, láminas, nubes de revisión, modo claro y modo *blueprint*.
El avance se ve como pisos del edificio que se rellenan; el equipo aparece como marcas en cada piso.

### Civil-Estructural · `civil` (Bentley: OpenRoads, OpenBridge, MicroStation) · Bloque 5
Planta-perfil de un camino. Concepto navegable en `design/mundos/civil.html`.
- **Portada:** perfil longitudinal con rasante y terreno, y una carretera que se pierde en el horizonte.
- **Recorrido:** el eje del camino con **progresivas** (`km 0+000`, `0+100`…). Cada curso es una **estaca**. Al verificarse un certificado, la estaca se clava y el tramo se pavimenta. Las acreditaciones levantan los **pilares del puente** que cruza el valle al final de la ruta.
- **Navegador:** *Explorer · Corridors*, con los capítulos como corredores.
- **Nota del oficio:** estaca anotada (banderín con texto).
- **Tablas:** planilla de cubicación (*Quantities and Earthwork*).
- **Paleta:** amarillo de señalética `#FFC21A`, gris asfalto `#2B2F36`, blanco de demarcación y verde talud.

### Topografía · `survey` (Trimble TBC, Geocom, iTwin Capture)
Carta topográfica.
- **Recorrido:** mapa con curvas de nivel y *niebla de guerra*. Cada misión descubre una zona del mapa y deja un vértice GNSS. Al completar la ruta, la **poligonal se cierra** y aparece el error de cierre "0.000 m" como logro.
- **Nota del oficio:** punto de control (triángulo con nombre).
- **Paleta:** verde carta, sepia de curvas y rojo de vértice.

### Mecánica · `mechanical`
Plano de taller.
- **Recorrido:** **despiece explosionado**. Cada capítulo es una pieza que vuelve a su lugar; al cerrar la ruta, el mecanismo ensamblado gira (animación desactivable).
- **Nota del oficio:** globo de referencia de pieza (círculo con número).
- **Paleta:** acero `#8A99A8`, rojo de cota y fondo de papel milimetrado.

### Captura / RPA · `aero` (drones, LiDAR, DGAC)
HUD de vuelo.
- **Recorrido:** plan de vuelo con **waypoints**. Cada misión cumplida es un waypoint alcanzado, y la nube de puntos de fondo se densifica con el avance. El altímetro muestra el nivel del personaje y la batería, la racha semanal.
- **Escalera:** Habilitación DGAC = *Alas*.
- **Nota del oficio:** marca de *waypoint* con texto.
- **Paleta:** cian HUD `#4CC6FF`, ámbar de alerta y fondo noche.

## Estilo "Levantamiento" (arte de presentación)

Para todo lo que represente **levantamiento digital** (portadas de ruta, el mundo `aero`, presentaciones y capturas
del README) se usa el estilo tomado de Aerotop: azul noche con grilla, acento ámbar, títulos en **serif cursiva**,
etiquetas **monoespaciadas** (`CLAVE · valor`, `// 01`), recuadros de anotación, retícula, **nube de puntos** y una
**línea de escaneo**. Está en `core/static/core/levantamiento.css` y `levantamiento.js` (`<canvas data-scene="building|terrain">`).
Regla: las lecturas de telemetría son **datos reales** de la ruta (niveles, misiones, avance…), nunca valores de relleno.
Respeta `prefers-reduced-motion` (imagen fija, con la línea de escaneo detenida).

## Contrato técnico

- `LearningPath.world` elige el mundo. Si viene vacío, se usa el de la disciplina principal de la ruta.
- Cada mundo tiene la misma estructura de archivos:
  - `core/static/worlds/<world>.css`: tokens y piel del mundo;
  - `core/templates/worlds/<world>/cover.html`, `journey.html`, `browser.html` y `note.html`.
- Todos reciben el mismo contexto:
  - `path` y `levels` (con `pct`, `done` y `team_marks`);
  - `me` (con `xp`, `level` y `title`);
  - `notes`.
- El panel del capítulo y las tablas son **componentes compartidos**; el mundo solo cambia variables CSS y adornos.
- Todo mundo debe:
  - funcionar sin JS para lectura;
  - no desbordar a 390 px;
  - tener modo claro y oscuro;
  - respetar `prefers-reduced-motion`;
  - usar solo SVG y CSS, sin librerías.
- Se crea con la skill `nuevo-mundo`, que además genera el atuendo de Teo para ese mundo.
