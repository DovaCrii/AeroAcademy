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

## Figuras por ruta (*figure kit*)

El mundo da la piel (CSS, portada, navegador); la **figura** es la metáfora con que se dibuja el avance de cada ruta y
trae su **vocabulario**. Así una ruta de IA no habla de cotas ni una de topografía de pisos.

- **Dónde.** `apps/catalog/figures.py` (registro, rótulos y reglas), `apps/catalog/figure_layout.py` (geometría, sin
  consultas, con coordenadas enteras) y `apps/core/templates/worlds/figures/<figura>.html` (un SVG por figura; estilos
  comunes en `worlds/figures.css`). Los tres mundos incluyen `{% include fig.template %}` y leen `fig.labels.*`.
- **Cómo se elige.** Clave `"figure"` en el JSON de la ruta (`seed/rutas/<slug>.json` o `private/cursos/<slug>/ruta.json`),
  validada por `seed_catalog` y leída al dibujar (sin campo en la base ni migración). Sin ella, la figura por defecto de
  la disciplina; si la figura no sirve para el tipo de ruta (`structured` / `external_track`), la pila `stack`.
- **`fig.labels`.** `kicker` (línea de la portada), `scene`, `scale` (regla), `sheet_label` y `sheet` (pie de lámina),
  `mark`, `content`, `unit_label`/`unit_value`, `figure_title`, `levels_title`, `levels_sub`, `browser`, `item`/`items`,
  `done_label`, `zero` (solo el corte de edificio) y, para rutas externas, `ext_*` (lead, nombres de la cinta, leyenda).
- **Estaciones.** Cada figura dibuja una *estación* por nivel (rutas estructuradas) o por curso (rutas externas: varias
  tienen un solo capítulo). Cada estación enlaza a `?nivel=<code>#panel`, lleva `data-fid="st-<id>"` y se lee sin JS.
- **Vocabulario vigilado.** `figures.FORBIDDEN` lista, por figura, las palabras de arquitectura que no debe mostrar
  («cota», «lámina», «dibujo y modelado», «+3,50», «pilar», «estaca», «planta y perfil», «corte A-A»); la prueba
  `tests/test_figures.py` renderiza la portada y la lámina de las 23 rutas y falla si aparece alguna.

| Figura | Metáfora | Vocabulario | Rutas |
|---|---|---|---|
| `building` | corte del edificio por pisos | cota, nivel, lámina A-101 | `forma-revit`, `forma-coordinacion` |
| `building-lod` | el mismo corte, con grados LOD en vez de cotas | LOD, nivel | `bim-101` |
| `road-profile` | planta y perfil del corredor (estacas y pilares del puente en rutas externas) | estaca, corredor, km | `civil-3d`, `bentley-learn` |
| `survey-profile` | perfil topográfico con puntos de referencia | PR, cota, datum | `topografia-101` |
| `survey-gis` | el mismo perfil, como capas de un mapa | capa, CRS | `geospatial-data-science` |
| `pipeline-ai` | datos → modelo → agente, en una ventana de contexto con celdas | capa, contexto, *tokens*, pipeline | `ia-101`, `agentes-ia`, `claude-code-mcp`, `vibe-coding`, `herramientas-ia` |
| `data-flow` | ingesta → limpieza → análisis → informe, como cilindros que se llenan | dataset, etapa, informe | `python-datos-101`, `datos-reportes`, `data-science-aplicada` |
| `capture-twin` | escaneo → nube de puntos → malla → gemelo con sensores | captura, nube, malla, iModel | `bentley-itwin` |
| `plant-iso` | P&ID → isométrico de tuberías con válvulas | línea, tramo, válvula, isométrico | `plant-3d`, `bentley-openplant` |
| `doc-flow` | documentos que pasan de WIP a compartido y publicado | versión, estado, *workflow* | `bentley-projectwise` |
| `viz-scene` | escena con cámara, luz y render | escena, toma, cámara, render | `bentley-lumenrt` |
| `building-model` | modelo apilado por disciplinas en isométrico | modelo, disciplina, coordinación | `bentley-openbuildings` |
| `drafting-sheet` | lámina con capas, bloques y XREF | capa, bloque, lámina | `autocad` |
| `flight-plan` | plan de vuelo con waypoints y dron | waypoint, ALT, BAT | `dgac-rpas` |
| `stack` | pila de capas sin cotas (respaldo) | etapa, capa | cualquier ruta sin figura que no calce |

**Marcadores.** El dron del plan de vuelo y «TÚ» del planta-perfil se dibujan en el lado opuesto de las etiquetas
(`progress.services._drone_offset`, `progress.external.MARKER_RISE`); los rótulos se recortan para caber y llevan el
nombre completo en `<title>`. Las estacas muestran las dos primeras palabras del curso, nunca su *key*.

**Figura nueva.** Agregarla a `FIGURES` (rótulos y vocabulario), su geometría en `figure_layout.LAYOUTS`, su plantilla en
`worlds/figures/`, y probarla con `tests/test_figures.py`. Seguir la gramática del mundo y la skill `nuevo-mundo`.

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
- Se crea con la skill `nuevo-mundo`, que además genera el atuendo de Nala para ese mundo.
