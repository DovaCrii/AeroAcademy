# Iconos de rutas y software

Cada ruta tiene un icono propio, **sin repetir** (`apps/catalog/software.py::ROUTE_ICON`, archivos
`apps/core/static/core/img/software/ruta-<slug>.svg`). La prueba `test_every_route_has_its_own_unique_icon_file`
exige que toda ruta de `seed/rutas/` tenga uno y que no haya dos iguales.

## Estado actual

Los 22 iconos `ruta-*.svg` viven en `apps/core/static/core/img/software/`.

- **13 son pictogramas originales** (baldosa con degradado y pictograma blanco), sin logotipos de nadie.
- **9 son logotipos oficiales** (6 de Simple Icons, tabla siguiente, y 3 de Autodesk, más abajo) de la ruta que trata ese producto: baldosa blanca (se ve igual en modo oscuro) con la forma
  del logo sin deformar (solo escala y posición) y su color de marca. El SVG original, sin tocar, está en
  `img/software/oficial/`.

Fecha de obtención: 2026-10-13. Fuente de todos: **Simple Icons 13.21.0** (CC0 para los datos del icono; las marcas siguen
siendo de sus dueños), `https://cdn.jsdelivr.net/npm/simple-icons@13.21.0/icons/<nombre>.svg` (Power BI, de `@latest`).
No se alcanzaron las páginas de marca oficiales de cada fabricante; Simple Icons se usó como respaldo.

| Ruta | Producto | Archivo oficial | Color | Nota de licencia / marca |
|---|---|---|---|---|
| python-datos-101 | Python | `oficial/python.svg` | #3776AB | Marca de la Python Software Foundation |
| herramientas-ia | Git | `oficial/git.svg` | #F05032 | Logo de Git por Jason Long, **CC BY 3.0** (atribución en `/rutas/`) |
| claude-code-mcp | Claude | `oficial/claude.svg` | #D97757 | Marca de Anthropic |
| geospatial-data-science | QGIS | `oficial/qgis.svg` | #589632 | Marca del proyecto QGIS |
| data-science-aplicada | Kaggle | `oficial/kaggle.svg` | #20BEFF | Marca de Kaggle (Google) |
| datos-reportes | Power BI | `oficial/powerbi.svg` | #F2C811 | Marca de Microsoft |

Los colores son los de marca publicados por Simple Icons. Uso nominativo: **se usan para identificar el producto del curso;
no implican respaldo ni relación con las marcas.**

## Iconos de producto oficiales de Autodesk (2026-10-13)

SVG tomados sin modificar de autodesk.com (`images.ctfassets.net/v7wr16nrr0mz/...`, el CDN de las páginas de producto);
copias en `img/software/oficial/autodesk-<producto>.svg`. En las baldosas van dentro de un `<svg>` anidado sobre fondo blanco
(solo cambian posición y tamaño). Uso nominativo: identifican el producto del curso; no implican respaldo de Autodesk.

| Producto | Página de origen | Archivo del CDN | Baldosa(s) |
|---|---|---|---|
| AutoCAD | autodesk.com/products/civil-3d/overview | `autocad-product-icon.svg` | `autocad.svg`, `ruta-autocad.svg` |
| Revit | autodesk.com/products/revit/overview | `revit-product-icon.svg` | `revit.svg`, `ruta-forma-revit.svg` |
| Forma | autodesk.com/products/revit/overview | `forma-product-icon.svg` | `forma.svg`, `ruta-forma-coordinacion.svg` |
| Navisworks | autodesk.com/products/navisworks/overview | `navisworks-simplified-product-icon.svg` | `navisworks.svg` |
| InfraWorks | autodesk.com/products/infraworks/overview | `infraworks-simplified-product-icon.svg` | `infraworks.svg` |

## Sin icono oficial (siguen con pictograma original; falta que el dueño los aporte)

- **Autodesk:** Civil 3D, Plant 3D, ReCap, Dynamo, Autodesk Docs / ACC (sus páginas no publican un icono propio descargable).
- **Bentley Systems (todos):** bentley.com solo publica fotos de producto, no iconos, y el icono `bentley` de Simple Icons
  es el de **Bentley Motors** (otra marca); no se usa.

## Bentley: pictogramas simplificados (NO son archivos oficiales)

Los iconos de MicroStation, ProjectWise, SYNCHRO, iTwin, iTwin Capture, Descartes, OpenRoads, OpenBridge, OpenBuildings,
OpenPlant, OpenFlows y STAAD son **pictogramas simplificados dibujados a partir de la infografía «Suite Bentley · Principales
aplicaciones»** que aportó el dueño como referencia (μ azul, tres círculos, grúa con insignia 4D, nube con ciudad, dron con haz,
malla de terreno, camino curvo, puente colgante, torres de vidrio, tanques y tuberías, gota, pórtico de acero). **No son los
archivos oficiales de Bentley ni su logotipo**: reemplazarlos si se consiguen los oficiales. LumenRT no aparece en la
infografía: su pictograma (sol sobre edificios) es original en el mismo estilo. Van sobre baldosa blanca, sin texto.
Archivos: `img/software/<producto>.svg` y `ruta-bentley-*.svg` (las rutas reutilizan el dibujo de su producto principal:
learn = MicroStation). Uso nominativo: identifican el producto del curso; no implican respaldo de Bentley.
- **MCP** (existe en Simple Icons) no se usó: la única ruta cercana, `agentes-ia`, trata de agentes en general.
- Rutas sin producto (BIM 101, Topografía 101, IA 101, Vibe coding, Agentes de IA): pictograma original.

Cómo cambiar uno: poner el SVG en `img/software/ruta-<slug>.svg` (o apuntar `ROUTE_ICON`) y anotarlo en esta tabla.
