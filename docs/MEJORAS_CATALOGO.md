# Mejoras del catálogo · jerarquía de la información

> Plan de diseño (Opus 5.5 medio, `disenador`), 2026-10-19. Rama `mejora-catalogo-jerarquia`.
> Lo implementa **un** `bloque-dev` (Sonnet 5.5 medio) en PR chicos y apilados. Lo comprueba el `verificador` (Haiku 5.5 medio).
> Mandan sobre este plan: `tokens.css`, `docs/VISION.md`, `docs/HOME.md` y `AGENTS.md`.

## 0. Estado de implementación (2026-10-19)

Rama `mejora-catalogo-jerarquia`, **sin commit** (cambios en el árbol, para revisar). Hechos: **P0-1, P0-2, P1-1 y P1-2**.
Pendientes: **P-6** (colores sueltos de `catalog.css` a tokens, PR de `diseno-ui` aparte) y **todo P2**.

Decisiones de la dueña aplicadas: P-1 (general al final y en el mapa), P-2 (Autodesk · Bentley · IA y datos ·
Topografía/GIS/captura · General), P-3 (sin vitrinas de Bentley), P-4 (sin acordeón), P-5 (sin «Gratuito» ni «Oficial»;
solo «De pago») y P-7 (área deducida de la ruta, sin tocar `seed/`).

- [x] **P0-1** `software.py` (`area_for_resource`, `areas_of`, `catalog_map`, `starters`, filas `more-<área>`), `services.published_path_links`
  y `views.resources` (`?vendor=`, 48 por página en `?software=`, migas, chip «Proveedor»).
- [x] **P0-2** cabecera con búsqueda y filtros, `partials/{filters,map,area,crumbs}.html`, `general.html` al final y CSS «jerarquía 2026-10».
- [x] **P1-1** `partials/card_compact.html`, `card.html` sin banda, `card_meta` (`kind_label`, `paid`) y leyenda.
- [x] **P1-2** `select name="vendor"` primero de la fila y rejilla 2 × 2 a ≤ 640 px.
- [ ] **P-6** y **P2-1 … P2-4**: sin hacer.

### Mediciones (semillero, 354 recursos y 22 rutas; DOM a 375 × 812 y 1280 × 800)

| Meta | Antes | Después | |
|---|---|---|---|
| 375 · página ≤ 5 500 px | 15 866 | **4 116** | cumple |
| 375 · `#vendor-bentley` ≤ 2 600 px | 8 558 | **1 348** | cumple |
| 375 · el mapa empieza a ≤ 812 px | no existía | **481** (termina en 775) | cumple |
| 375 · cada área ≤ 1 000 px | 4 795 / 6 065 | **300 – 703** | cumple |
| 375 · cabecera con filtros ≤ 520 px | 4,0 pantallas hasta los filtros | **402** | cumple |
| 1280 · página ≤ 4 000 px | 13 023 | **2 668** | cumple |
| 1280 · `#vendor-bentley` ≤ 1 600 px | 6 306 | **853** | cumple |
| 1280 · el mapa termina a ≤ 800 px | no existía | **477** | cumple |
| Tarjetas de recurso en `/catalogo/` ≤ 24 | 95 | **14** | cumple |
| Imágenes ≤ 60 | 145 | **26** | cumple |
| HTML ≤ 80 KB | 159 KB | **39 KB** | cumple |
| Clics hasta un curso ≤ 2 | 0 clics pero 10 pantallas | **2** (mapa o chip → producto) | cumple |
| Recursos con área | 163 de 354 | **354 de 354** (suma del mapa) | cumple |
| Consultas de `/catalogo/` ≤ 45 | 45 | **44** | cumple |
| Tarjeta compacta ≤ 190 px (375) | 314 | **173** (máx.) | cumple |
| Tarjeta completa ≤ 230 px (375) | 314 | **212 en promedio; 256–284 si el título ocupa 3 líneas** | cumple en promedio |

Mapa: Autodesk 123 · Bentley 51 · IA y Datos 139 · Topografía, GIS y captura 2 · Conocimiento general 39 (= 354).
Otras vistas (consultas): `?vendor=bentley` 29, `?software=microstation` 33, `?q=` 33, `?todo=1` 33, `?general=1` 49. Ninguna crece con
los datos (`test_catalog_queries_bounded`, `test_catalog_queries_do_not_grow`).

### Diferencias con el plan (se siguió el código real)

1. **Conocimiento general = 39 en el mapa, 41 con `?general=1`.** Para que las 5 áreas sumen 354, un recurso con producto va a su
   familia aunque lleve la etiqueta (2 de ellos). La sección final enlaza a `?vendor=general` (39); `?general=1` (41, por etiqueta) sigue igual.
2. **IA y Datos no tiene filas por producto**: sus 139 recursos no traen producto ni mosaico, así que van todos en «Más de IA y Datos».
   Pasan a filas por producto cuando `curador-semillas` les asigne productos (P-7, tarea aparte).
3. La **portada no usa `data-rail`**: «Para empezar» es una rejilla de 4 columnas desde 641 px y un carril con `scroll-snap` (sin flechas) en celular.
   Las flechas de `catalog.js` siguen en las filas de `?vendor=`.
4. El pack de baldosas de `?vendor=` solo sale si alguna baldosa tiene recursos (IA no lo muestra) y enlaza a `#sw-<slug>`;
   las baldosas vacías siguen apuntando al foro («Sin recursos · proponer»; P2-4 las mueve al pie).
5. El filtro «Proveedor» **no** lleva `data-autosubmit`: se envía con «Buscar» (la opción del plan era opcional).
6. `?vendor=general` es la rejilla paginada de los recursos del área general (no hay filas por producto).
7. La vista de proveedor, el filtro y la portada leen la lista completa una vez (`resource_queryset` + 3 consultas de áreas);
   `?q=`, `?todo=1` y similares suben de 26 a 33 consultas, fijas. Se podría bajar cacheando `essential_ids()` y `general_ids()` por petición.
8. En la tarjeta compacta la meta va en una sola línea (con puntos suspensivos) para no pasar de 190 px; el detalle completo queda en el `title` y en la vista de lista.

> **2026-10-20 · D43:** el orden de áreas de este plan (Autodesk primero) **cambió**: Bentley y Autodesk son las plataformas
> oficiales, con Bentley primero, y llevan seguimiento de avance. Ver la sección 9 al final.

## 1. Pedido

La dueña pidió lo siguiente (2026-10-19, con una captura de `/catalogo/` en ancho de celular):

> «Mejorar el catálogo de Bentley: queda al fondo, todo queda desplazado muy abajo; buscar una forma de optimizar la
> distribución de cursos, etc., sobre todo la jerarquía de la información».

El problema central es que la jerarquía *vendor → producto → curso* se repite igual para todos los vendors. El primero (Autodesk)
ocupa la mitad de la página y lo demás queda enterrado. Además, no hay un mapa del catálogo ni un camino corto a un proveedor.

## 2. Hallazgos medidos

Medí con el semillero actual: base temporal, `migrate` y `seed_catalog`, con 354 recursos y 22 rutas publicadas. Usé
`runserver` con un admin de prueba. Las alturas se tomaron del DOM (`getBoundingClientRect`) y las consultas con
`CaptureQueriesContext`.

### 2.1 Altura y posición de cada bloque (`/catalogo/`, sin filtros)

| Bloque | 375 × 812: inicio · alto | 1280 × 800: inicio · alto |
|---|---|---|
| Cabecera «Todo lo que hay para aprender» | 63 · 288 px | 69 · 271 px |
| **«// 00 Conocimiento general»** (2 rutas + 6 tarjetas) | 373 · **2 844 px** | 362 · 1 031 px |
| «// 01 Buscar y filtrar» | **3 239 px (4,0 pantallas)** · 389 | 1 415 px (1,8 pantallas) · 217 |
| Autodesk (banda + pack de 10 + 8 filas) | 3 718 · **4 795 px** | 1 723 · 4 539 px |
| **Bentley Systems** (banda + 3 vitrinas + 10 filas) | **8 558 px (10,5 pantallas, 54 %)** · 6 065 | **6 306 px (7,9 pantallas, 48 %)** · 5 557 |
| Primer curso de Bentley (fila MicroStation) | 9 956 px (12,3 pantallas) | 7 176 px (9 pantallas) |
| Topografía, GIS y captura (1 fila) | 14 666 px (92 %) · 866 | 11 907 px (91 %) · 846 |
| **Página completa** | **15 866 px = 19,5 pantallas** | **13 023 px = 16,3 pantallas** |

Otros números:

- **Tarjetas.** Se pintan 95 tarjetas de recurso (89 en filas y 6 en «general»), 145 imágenes y 306 enlaces. El HTML pesa
  159 KB y la vista hace 45 consultas.
- **Filtros.** `?software=microstation` pesa 49 KB y hace 30 consultas. `?q=` y `?todo=1` hacen 26 consultas cada una.
- **Alto de cada pieza.** Una tarjeta mide 314 px. De eso, 84 px son la banda de color con el mosaico de 52 px, que repite
  el producto que ya dice la fila. Cada fila de producto mide entre 370 y 520 px, aunque tenga **1 solo curso**: OpenFlows,
  STAAD, iTwin y SYNCHRO miden 372 px cada una.
- **Bentley repite sus productos 3 veces.** Las vitrinas «Destacados / Nuevos / Más usados» (12 tarjetas) miden
  1 198 px a 375 y 658 px a 1280. Después vienen las 10 filas de esos mismos productos.
- **El pack de iconos de Autodesk** mide 644 px a 375: 10 baldosas de 112 px, 2 de ellas vacías («Sin recursos · proponer»).

### 2.2 Qué se pinta por vendor (función `software.group_by_software`, 8 tarjetas por fila)

| Familia | Filas | Recursos | Tarjetas pintadas | Productos sin recursos en el pack |
|---|---|---|---|---|
| Autodesk | 8 (Revit 18, Civil 3D 17, Forma 13, AutoCAD 23, Plant 3D 8, Docs/ACC 24, Dynamo 5, ReCap 2) | 110 | 55 + 5 «+N» | 2 de 10 |
| Bentley | 10 (MicroStation 27, OpenRoads 4, OpenBridge 2, OpenBuildings 4, OpenPlant 4, OpenFlows 1, STAAD 1, iTwin 1, ProjectWise 6, SYNCHRO 1) | 51 | 32 + 1 «+N» | 3 de 13 |
| Topografía, GIS y captura | 1 (DGAC 2) | 2 | 2 | 2 de 3 |
| IA y Datos | **0** | **0** | 0 | (la sección no aparece) |

**Hallazgo grave: 191 de 354 recursos (54 %) no aparecen en la vista por defecto.** La vista solo pinta los recursos que
tienen mosaico, y ninguno de estos 191 tiene productos asignados ni una palabra clave en el título. Así se reparten:

- **139 de rutas de IA y datos:** Anthropic Academy 53, Kaggle 31, Microsoft Learn 15 y recursos abiertos 40 (GIS e IA).
  Por eso la sección **IA y Datos nunca se pinta**, aunque `FAMILY_LABEL` la define.
- **39 de «Conocimiento general»:** se ven solo en el bloque `// 00`, 6 de ellos.
- **13 de Autodesk Learning:** son de las rutas Forma + Revit, AutoCAD, Civil 3D y Plant 3D, pero el título no dice el producto.

A estos recursos solo se llega buscando, filtrando o con «Ver todos los recursos en una lista» (`?todo=1`).

**Las marcas «esencial» de Bentley son pocas.** En las filas de Bentley hay 6 tarjetas esenciales de 32, todas de
MicroStation y OpenPlant. En las de Autodesk hay 47 de 55. Por eso un criterio «solo esenciales» dejaría a Bentley casi vacío.

### 2.3 Navegación, filtros y vistas que existen hoy

- **Parámetros de `GET /catalogo/`:** `q` (100 caracteres), `discipline`, `kind`, `esencial=1`, `ruta`, `platform`,
  `cert=1`, `general=1`, `free=1`, `software=<mosaico>`, `todo=1` y `page`.
  - Con cualquier filtro, la vista pasa a una rejilla paginada de 24 resultados.
  - Cada filtro activo se muestra como chip removible.
  - **No existe un filtro por proveedor.** El más cercano es `platform`, pero Bentley tiene una sola plataforma y Autodesk varias.
- **Cómo se llega a un producto:** desde la baldosa del pack o de la vitrina, desde «Ver todo · N» o desde la tarjeta final
  «+N». Todos van a `?software=<slug>`.
  - La vista `?software=` no dice a qué proveedor pertenece el producto ni tiene un camino de vuelta, salvo el chip «×».
- **Anclas existentes:** `#vendor-<familia>` y `#sw-<slug>`, pero **nada enlaza a ellas**. No hay índice ni barra de saltos.
- **Clics hasta un curso de Bentley:** 0 clics, pero con 10,5 pantallas de desplazamiento (375 px) solo para llegar a la
  banda. La alternativa es buscar (`q`), que exige saber el nombre.
  - Con el pack de Bentley: desplazarse 10,5 pantallas, 1 clic en la baldosa y 1 clic en el curso.
  - MicroStation tiene 27 recursos y la página es de 24, así que 3 quedan en la página 2.
- **Enlaces que llegan de afuera y deben seguir funcionando:**
  - `?q=` desde la portada (`home.html`), `route_rows.html`, Nala (`assistant/search.py`, `quick.py`) y las pruebas.
  - `?software=` desde las propias tarjetas.
  - `?ruta=`, `?kind=`, `?cert=`, `?free=`, `?general=`, `?todo=1` y `?page=` desde las pruebas y la auditoría de enlaces de `MEJORAS_UX`.
- **Filtros visibles:** Disciplina, Tipo (con conteos) y «Solo esenciales». En «Más filtros» están Ruta, Plataforma,
  Certificado, General y Gratuito. Esto sale de la decisión P1-7 de `MEJORAS_UX`.
  - El problema no es su forma: es que **el bloque queda debajo de «Conocimiento general»**, a 4 pantallas del inicio en celular.

### 2.4 Contenido de la tarjeta

Hoy la tarjeta pinta, en este orden:

1. Banda con el mosaico, el producto y la etiqueta de nivel.
2. Tipo · tipo · duración.
3. Título.
4. Descripción de 130 caracteres.
5. «En la ruta …».
6. Chips: +XP, Oficial, Gratuito y Certificado.

Lo que dicen los datos:

- **Gratuito** está en 351 de 354 recursos: no informa nada. **Oficial** está en 286 de 354.
- **Duración** solo en 47 de 354.
- La línea de metadatos repite el tipo («On demand · Curso»).
- El nivel se deduce del título y el tipo (`level_for_resource`).

### 2.5 Hallazgos laterales (no se corrigen aquí)

- `catalog.css` redefine en `:root` (l. 66 y 155) las variables `--d-arq…--d-iad` con colores sueltos y además usa
  gradientes de marca fijos (`.vs-*-band`, `.vs-*-thumb`, `.lvl-*`). Eso pisa en claro los `--d-*` accesibles de
  `tokens.css`. Queda como pregunta para un PR de tokens aparte (§ 7, P-6).
  - Este plan **no agrega** colores sueltos; los nuevos elementos usan solo tokens.

## 3. Opciones evaluadas

Cada opción se evaluó por cinco preguntas:
- **Bentley arriba:** ¿acerca Bentley al inicio?
- **Mapa:** ¿da un mapa del catálogo?
- **Sin JS:** ¿funciona sin JS?
- **Costo:** ¿cuánto cuesta implementarla?
- **Riesgo:** ¿qué puede romper?

| Opción | Bentley arriba | Mapa | Sin JS | Costo | Riesgo y comentario |
|---|---|---|---|---|---|
| (a) Barra de proveedores con anclas y conteo | Sí: 1 clic, pero sigue a 10 pantallas en el scroll | Parcial | Sí | Bajo | Salta, pero no acorta. Una barra fija a 375 px resta alto útil, y la cabecera del sitio ya es fija (61 px). |
| (b) Resumen por proveedor primero y detalle en una vista `?vendor=` | Sí | Sí | Sí | Medio | Ningún vendor domina. Exige un parámetro nuevo y cambiar `show_rows`. |
| (b′) El mismo resumen con `<details>` plegado | Sí | Sí | Sí | Bajo | Abrir un `<details>` cerrado desde un ancla no es fiable en todos los navegadores. Al plegarlo se pierden la búsqueda del navegador (Ctrl+F) y el «scroll de vitrina». |
| (c) N cursos por producto y «ver todos (n)» | Ayuda: Autodesk baja de 4 795 a unos 2 000 px | No | Sí | Bajo | Con 8 filas por vendor sigue largo. Bentley tiene filas de 1 curso, así que poner un tope no las acorta. |
| (d) Orden de vendors por uso del equipo o vendor favorito | Sí, para quien lo elija | No | Sí | Medio a alto | Necesita un dato de uso o una preferencia (modelo o sesión). Es una decisión de producto. |
| (e) Búsqueda como entrada principal y filtros cortos visibles, con «Proveedor» | Sí: 1 selección | No | Sí | Bajo | Ya existe casi todo. Falta subirlo y sumar «Proveedor». |
| (f) Celular: una columna, acordeón y tarjetas compactas | Sí | No | Sí | Medio | Las tarjetas compactas valen en todos los anchos. El acordeón tiene el riesgo de (b′). |

## 4. Decisión recomendada: **mapa primero, vitrina corta por área y detalle por demanda**

Es la combinación **(e) + (b) + (c) + tarjeta compacta**, con el mapa como índice de anclas (a, sin barra fija). Nada se
pliega por defecto. Cada área ocupa lo mismo en la portada del catálogo y el detalle completo vive en una vista por proveedor.

### 4.1 Nueva jerarquía de `/catalogo/` (sin filtros)

```
┌ Cabecera compacta ─────────────────────────────────────────────┐
│ // Catálogo · 354 recursos · 22 rutas                          │
│ Todo lo que hay para aprender                                  │
│ [ 🔍 Busca por software, tema o habilidad … ]  [Buscar]        │  ← la búsqueda es la entrada principal
│ Proveedor ▾  Disciplina ▾  Tipo ▾  ☐ Solo esenciales  Más ▸   │  ← una fila a 1280; 2×2 a 375
└────────────────────────────────────────────────────────────────┘
┌ Mapa del catálogo (// 01) ─────────────────────────────────────┐
│ [Autodesk 123 · 8 productos] [Bentley 51 · 10] [IA y datos 139]│  ← tarjetas-ancla a #vendor-<clave>
│ [Topografía, GIS y captura 2] [Conocimiento general 41 · 2 rutas]│  ← 5 tarjetas: 1 fila a 1280, 2 columnas a 375
└────────────────────────────────────────────────────────────────┘
┌ Autodesk (// 02) ──────────── 123 recursos · Ver todo Autodesk →┐  ← banda compacta (≤ 96 px)
│ Productos: [RVT Revit 18] [C3D Civil 3D 17] [CAD AutoCAD 23] … │  ← chips → ?software=<slug>
│ Para empezar: ▢ ▢ ▢ ▢   (4 tarjetas compactas, carril)         │
└────────────────────────────────────────────────────────────────┘
┌ Bentley Systems (// 03) ───── 51 recursos · Ver todo Bentley → ┐
│ Productos: [MS MicroStation 27] [ORD OpenRoads 4] …            │
│ Para empezar: ▢ ▢ ▢ ▢                                          │
└────────────────────────────────────────────────────────────────┘
… Topografía, GIS y captura · IA y datos (mismo molde) …
┌ Conocimiento general · transversal ────────────────────────────┐
│ 2 tarjetas de ruta (BIM 101, Topografía 101) + «Ver los 41 →»  │  ← sin las 6 tarjetas de recurso
└────────────────────────────────────────────────────────────────┘
[ Ver todos los recursos en una lista → ]   ·   leyenda de etiquetas
```

**Vista por proveedor `?vendor=bentley`** (nueva). Muestra la banda, una lista de productos que salta a `#sw-<slug>` y las
filas por producto de **ese** vendor: es el detalle de hoy, pero solo de un vendor. El chip activo es «Bentley Systems ×».
Las vitrinas «Destacados / Nuevos / Más usados» se quitan, porque repiten los productos (P-3).

**Vista por producto `?software=<slug>`** (existente). Suma una ruta de migas: «Catálogo › Bentley Systems › MicroStation».
La página pasa a **48** resultados, para que el producto más grande (27) quepa entero y cualquier curso quede a ≤ 2 clics.

### 4.2 Por qué esta y no otra

- **Ninguna área domina el scroll.** Cada una mide lo mismo: banda, chips de producto y 4 tarjetas. El orden fijo deja de
  castigar al segundo vendor, y Bentley pasa de 10,5 a unas 3 pantallas a 375 px y queda a **1 clic** desde el mapa.
- **El mapa responde «qué hay» en la primera pantalla.** Muestra los totales por área, incluida la que hoy es invisible:
  IA y datos, con 139 recursos.
- **Funciona sin JS y sin trucos:** anclas, enlaces GET y carriles con `scroll-snap`, que ya existen. No hay `<details>`
  plegados que oculten contenido, ni una barra fija que reste alto en celular.
- **Reusa lo que hay:** `vendor_sections`, `group_by_software`, `cat-row`, el carril, los chips de filtro y `sw_pack_item`.
  No hay modelos ni semillas nuevos.

### 4.3 Qué queda del bloque superior «Todo lo que hay para aprender»

- Se quedan el título, el *kicker* con los conteos y la ilustración *doodle*, esta solo desde 641 px.
- La bajada (`cat-lead`) se acorta a una línea. La explicación de XP y esencial ya está en la leyenda.
- **La búsqueda y los filtros pasan dentro de la cabecera**: se elimina el bloque `// 01 Buscar y filtrar` aparte y la
  línea «N resultados» de la vista sin filtros.
- «Conocimiento general» deja de ir antes que todo:
  - es un área más del mapa;
  - su sección va al final, solo con las tarjetas de ruta y «Ver los 41»;
  - las 6 tarjetas de recurso viven en `?general=1`.
  
  Esto es una decisión de producto (P-1).

### 4.4 Jerarquía dentro de la tarjeta

La **tarjeta compacta** se usa en las vitrinas y en las vistas `?vendor=` y `?software=`. Lleva, en orden de lectura:

1. **Título** (enlace, 3 líneas como máximo, ↗ si es externo). Es lo primero que se lee.
2. **Una línea de meta:** nivel (punto o etiqueta del color del nivel con su texto) · tipo sin repetir (p. ej. «Curso» o
   «Examen») · duración si existe.
3. **«En la ruta X»** en una línea; si hay más rutas, «+1».
4. **Chips**, como máximo 3, en este orden: Esencial · +XP o Certificado · «De pago» (solo si `is_free` es falso).

Se quitan de la tarjeta compacta:
- la banda de 84 px con el mosaico: el producto ya lo dice la sección o el carril;
- la descripción: queda en `title` y en la vista de lista;
- el chip «Gratuito» (351/354);
- el chip «Oficial» (286/354), que pasa a la leyenda como regla general: «salvo indicación, del fabricante».

**En los resultados mezclados** (`?q=`, filtros, `?todo=1`) se usa la tarjeta completa, sin la banda. El mosaico pasa a
tamaño `sw-sm` (22 px), en línea con la meta, y la descripción se mantiene. La meta: alto de tarjeta ≤ 200 px a 375,
frente a 314 px hoy.

### 4.5 Orden de las áreas

Por defecto: **Autodesk · Bentley · IA y datos · Topografía, GIS y captura · Conocimiento general**. Es el orden de hoy
más las dos áreas que faltaban.

Al tener todas el mismo alto, el orden pesa poco. Si la dueña quiere a Bentley primero, se cambia la tupla de
`vendor_sections` (P-2).

La opción de poner primero el área de la disciplina de la persona (`Person.disciplines`) queda en P2.

### 4.6 Celular (375 px)

- **Cabecera:** una columna.
- **Filtros:** rejilla de 2 × 2 (Proveedor | Disciplina, Tipo | esenciales) más «Más filtros». Altura ≤ 230 px.
- **Mapa:** 2 columnas de tarjetas de 44 px de alto como mínimo (objetivo táctil).
- **Chips de producto:** se ajustan en varias líneas, sin carril horizontal.
- **«Para empezar»:** el carril actual, con tarjetas de `min(78vw, 260px)`.
- No hay barra fija ni acordeón (ver P-4).

## 5. Plan de implementación (P0 / P1 / P2)

Lo hace un solo implementador, `bloque-dev` (Sonnet 5.5 medio), en **PR apilados**. Cada PR tiene sus dueños de archivo
y ninguno toca los del siguiente mientras está abierto.

Ramas:
- `mejora-catalogo-p0-servicio`
- `mejora-catalogo-p0-portada`
- `mejora-catalogo-p1-tarjeta`
- `mejora-catalogo-p1-filtros`

Pruebas nuevas en `tests/test_catalogo_jerarquia.py`, creadas en el PR 1 y ampliadas por bloque, cada bloque solo con sus funciones.

### P0-1 · Servicio: área de cada recurso, mapa y `?vendor=` (solo Python)

- **Dueño de:** `apps/catalog/software.py`, `apps/catalog/views.py` y `tests/test_catalogo_jerarquia.py` (nuevo).
- **Enfoque:**
  1. `family_for_resource(r, path_tiles)` asigna el área, en este orden de preferencia:
     - la familia del primer mosaico (como hoy);
     - si no hay mosaico, la del **primer mosaico de su primera ruta publicada** (`software_for_path`; las rutas vienen de
       `services.published_paths_for`, precargadas con `products`);
     - si el recurso está en `general_ids()`: `"general"`;
     - si no, la familia por el *vendor* de la ruta (`anthropic`, `kaggle`, `microsoft` u `open-source` → IA;
       `aeroacademy` → `internal`).
  2. `group_by_software` agrupa los que no tienen producto pero sí familia en una fila **«Más de <área>»** (clave
     `more-<familia>`, sin mosaico) al final de su área.
  3. Esto **no cambia** `software_for_resource` (lo usan las tarjetas y las rutas).
  4. `catalog_map(resources)` devuelve `[{key, label, total, products: [{tile, total}], anchor}]` para las 5 áreas, con los
     productos con recursos ordenados por `ROW_ORDER`. Los productos sin recursos ya no salen en el mapa.
  5. `vendor_sections(rows, preview=4)` agrega `starters`: hasta 4 tarjetas por área, **una por producto** en rondas
     (esencial primero, luego oficial y luego el orden actual). Así Bentley no queda solo con MicroStation. Se quitan
     `shelves` y `FEATURED/NEWEST` (P-3).
  6. `views.resources`:
     - lee `vendor` y lo valida contra las claves de `FAMILY_LABEL` más `general`;
     - `show_rows` es verdadero si no hay filtros **o** si el único filtro es `vendor` (vista por proveedor);
     - agrega el chip «Proveedor»;
     - la página de `?software=` pasa a 48.
  7. Sin filtros, se pintan solo los `starters`. Los `in_paths` se calculan solo para las tarjetas pintadas, en una consulta.
- **Aceptación:**
  - La suma de `total` de las 5 áreas del mapa es igual a `resource_queryset().count()`: **los 354 recursos tienen área**
    (hoy faltan 191).
  - Con el semillero, IA y datos tiene ≥ 139 recursos y la fila «Más de Autodesk» tiene 13.
  - `?vendor=bentley` devuelve 200 y solo filas de Bentley. `?vendor=<script>` y `?vendor=nada` devuelven 200 y se ignoran.
  - `?software=`, `?q=`, `?ruta=`, `?kind=`, `?cert=`, `?free=`, `?general=1`, `?todo=1` y `?page=2` responden igual que
    antes (mismo conjunto de resultados).
- **Pruebas:**
  - `test_every_resource_has_an_area`;
  - `test_catalog_map_totals_match_queryset`;
  - `test_starters_one_per_product_round_robin`;
  - `test_vendor_param_filters_rows`;
  - `test_vendor_param_ignores_garbage`;
  - `test_legacy_params_unchanged`, parametrizada con los 10 parámetros;
  - **`test_catalog_queries_bounded`**: cuenta consultas en `/catalogo/`, `?vendor=bentley` y `?software=microstation`;
    duplica recursos y rutas (fábrica); el número no crece. Además, el techo absoluto de `/catalogo/` es ≤ 45, el de hoy.

### P0-2 · Portada del catálogo: cabecera con búsqueda, mapa y vitrina por área (plantillas y CSS)

- **Dueño de:**
  - `catalog/resources.html`;
  - partials nuevos `catalog/partials/filters.html` (el `form` actual movido sin cambios de nombres de campo),
    `partials/map.html`, `partials/area.html` y `partials/crumbs.html`;
  - `partials/general.html`;
  - `static/catalog/catalog.css`: bloques nuevos al final, rotulados `/* ===== jerarquía 2026-10 ===== */`.
- **Enfoque:**
  1. La cabecera incluye `filters.html`. La línea «N resultados» se muestra solo con filtros.
  2. `map.html`:
     - es un `<nav aria-label="Mapa del catálogo">` con una tarjeta-ancla por área: nombre, total, n productos y una
       baldosa `sw-md` del primer producto;
     - cada `id` lleva `scroll-margin-top` (la cabecera del sitio mide 61 px);
     - al final de cada área va «↑ Volver al mapa».
  3. `area.html`, para la portada:
     - banda compacta (padding ≤ 14 px y título de `--fs-h3`);
     - chips de producto (baldosa de 22 px, nombre y conteo; enlace a `?software=`);
     - carril «Para empezar» con los `starters`;
     - enlace «Ver todo <área> (n) →» a `?vendor=<clave>`.
  4. `resources.html` con `?vendor=` reutiliza las filas `cat-row` actuales y antepone `crumbs.html`.
  5. `general.html` sin las 6 tarjetas: va después de las áreas.
  6. El `.vs-pack` de baldosas de 112 px sale de la portada y queda solo en la vista `?vendor=`, como índice de anclas a
     `#sw-<slug>`. Las vitrinas de Bentley se eliminan.
  7. CSS solo con tokens: `--sheet`, `--sheet-2`, `--line`, `--hair`, `--ink`, `--ink-2`, `--amber`, `--amber-ink`,
     `--disc-*`, `--sp-*`, `--r-*` y `--fs-*`. Los colores de marca de las bandas son los que ya existen; no se agregan nuevos.
- **Aceptación**, medida por el `verificador` con el semillero y la página sin filtros:
  - **375 × 812:**
    - página ≤ **5 500 px** (hoy 15 866);
    - el mapa empieza a ≤ 812 px, en la primera pantalla;
    - `#vendor-bentley` empieza a ≤ **2 600 px** (hoy 8 558);
    - cada área mide ≤ 1 000 px.
  - **1280 × 800:**
    - página ≤ **4 000 px** (hoy 13 023);
    - el mapa termina a ≤ 800 px;
    - `#vendor-bentley` empieza a ≤ **1 600 px** (hoy 6 306).
  - Tarjetas de recurso pintadas en `/catalogo/` ≤ 24 (hoy 95) e imágenes ≤ 60 (hoy 145). El HTML pesa ≤ 80 KB (hoy 159 KB).
  - **Clics:** cualquier curso está a ≤ 2 clics desde `/catalogo/`: chip de producto en el mapa o en el área, y luego la
    tarjeta, porque la página de 48 no pagina ningún producto. Bentley está a 1 clic (tarjeta del mapa).
  - Sin JS: todo se ve y navega (anclas, enlaces y carril con `scroll-snap`). En claro y oscuro: `contrast.py` en verde con
    los pares base. No hay `#hex` nuevos en `catalog.css` (`git diff` sin colores sueltos agregados).
- **Pruebas:**
  - `test_catalog_has_map_with_all_areas`: 5 anclas y sus `href="#vendor-…"` existen en la página;
  - `test_area_links_to_vendor_view`;
  - `test_vendor_view_has_breadcrumb`;
  - `test_search_form_is_first_form` (el `form[role=search]` está antes del mapa);
  - `test_catalog_card_count_bounded` (≤ 24 `cat-card` sin filtros);
  - ajustar `test_conocimiento_general.py` donde espere las 6 tarjetas en `/catalogo/`, y solo eso.

### P1-1 · Tarjeta compacta y chips con información

- **Dueño de:**
  - `catalog/partials/card.html`;
  - `partials/card_compact.html` (nuevo);
  - `apps/catalog/templatetags/catalog_extras.py` (`card_meta`: tipo sin repetir, `paid`);
  - el bloque `/* tarjeta */` de `catalog.css`.
- **Enfoque:** el que describe § 4.4. `area.html` y las filas de `?vendor=` usan `card_compact.html`; la rejilla de
  resultados usa `card.html` sin la banda. La leyenda suma «De pago» y quita «Oficial» y «Gratuito».
- **Aceptación:**
  - tarjeta compacta ≤ 190 px y completa ≤ 230 px a 375;
  - ningún «Gratuito» en `/catalogo/`;
  - «De pago» en los 3 recursos de pago;
  - en la tarjeta compacta, el `h3` del título es el primer elemento con texto (la meta va después);
  - XP visible en las tarjetas con certificado (D33).
- **Pruebas:**
  - `test_compact_card_order`: dentro de la tarjeta compacta, el `h3` aparece antes de la meta y de `.chips`;
  - `test_no_free_chip_and_paid_chip`;
  - `test_xp_chip_still_shown`;
  - la regla de consultas acotadas sigue en verde.

### P1-2 · Filtros: «Proveedor» y rejilla en celular

- **Dueño de:** `catalog/partials/filters.html` y el bloque `/* filtros */` de `catalog.css`.
- **Enfoque:**
  - `select name="vendor"` con «Todos» y las 5 áreas con su conteo, primero de la fila;
  - rejilla de 2 × 2 a ≤ 640 px;
  - `data-autosubmit` opcional (`enhance.js` ya lo soporta); sin JS manda el botón «Buscar».
- **Aceptación:**
  - a 1280, los filtros visibles caben en 1 fila; a 375, la cabecera completa con filtros mide ≤ 520 px;
  - el `vendor` se combina con `q` y `kind` (p. ej. `?vendor=bentley&kind=exam`).
- **Pruebas:** `test_vendor_combines_with_other_filters` y `test_vendor_chip_removes_param`.

### P2 (después, solo si la dueña lo pide)

- **P2-1 · Área de la persona primero:** el área de `Person.disciplines` (o la última `?vendor=` visitada, en sesión) va
  primera en el mapa y en las secciones. Depende de P-2.
- **P2-2 · Barra de áreas fija solo en escritorio** (≥ 1024 px, `position:sticky` bajo la cabecera, el patrón `.w-jump`
  de la portada), únicamente en la vista sin filtros.
- **P2-3 · Marcar esenciales en Bentley:** hoy hay 6 de 51. Es tarea de `curador-semillas` en `seed/rutas/bentley-*.json`,
  no de este bloque. Mejora la vitrina «Para empezar».
- **P2-4 · Productos sin recursos:** pasan a «Proponer un curso» al pie del área, en vez de baldosas vacías.

### Lo que comprueba el `verificador` (Haiku), en cada PR

1. `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` y `python tools/kit/privacy_scan.py`.
2. `uv run python manage.py revisar_enlaces`: cero enlaces internos rotos en `/catalogo/`, `?vendor=<cada área>` y
   `?software=<cada mosaico con recursos>`.
3. `contrast.py` con los pares base de `diseno-ui`, y `rg "#[0-9A-Fa-f]{3,8}"` sobre las líneas agregadas de `catalog.css`
   (debe dar cero).
4. Mediciones en una base temporal con `seed_catalog` y `runserver` (`DEV_REMOTE_USER` de prueba). Con `javascript_tool`,
   a 375 × 812 y a 1280 × 800, se mide en claro y en oscuro (`resize_window colorScheme`). El reporte da la tabla
   antes/después contra los criterios de P0-2:
   ```js
   const H=document.documentElement.scrollHeight,t=s=>{const e=document.querySelector(s);return e?Math.round(e.getBoundingClientRect().top+scrollY):null};
   ({H, pantallas:(H/innerHeight).toFixed(1), mapa:t('nav[aria-label="Mapa del catálogo"]'), bentley:t('#vendor-bentley'),
     tarjetas:document.querySelectorAll('.cat-card').length, imgs:document.images.length})
   ```
5. Sin JS (desactivar JS o `curl`): el HTML de `/catalogo/` contiene el `form` de búsqueda, las 5 anclas y los enlaces `?vendor=`.

## 6. Qué NO se toca

- **Modelos y migraciones** (`apps/catalog/models.py` y otros), **semillas** (`seed/`), claves y configuración
  (`config/`, `deploy/`).
- **URL y parámetros existentes:** `/catalogo/`, `?q=`, `?software=`, `?ruta=`, `?kind=`, `?platform=`, `?discipline=`,
  `?esencial=`, `?cert=`, `?free=`, `?general=`, `?todo=1` y `?page=`, con la misma semántica. Las anclas
  `#vendor-<clave>` y `#sw-<slug>` se conservan con el mismo `id`.
- `software_for_resource`, `TILES`, `PRODUCT_TILE`, `ROUTE_ICON` y los SVG de `core/img/software/`, que usan las rutas,
  la portada y Nala.
- `apps/core/templates/core/home.html`, `route_rows.html`, Nala (`apps/assistant/*`), `enhance.js` y `tokens.css`.
- Las reglas de visibilidad: lo oculto, en borrador o privado no aparece, porque todo sigue saliendo de `services.resource_queryset`.
- `legacy/` y `design/`.

## 7. Riesgos y preguntas abiertas para la dueña

| # | Pregunta | Mi recomendación |
|---|---|---|
| P-1 | ¿«Conocimiento general» deja de ir primero? Hoy mide 2 844 px a 375 y empuja la búsqueda a 4 pantallas. | **Sí:** un área del mapa y una sección final con sus 2 rutas. Si debe quedar arriba, que sea solo la franja de 2 rutas (≤ 300 px), sin las 6 tarjetas. |
| P-2 | ¿Algún vendor debe ir primero (p. ej. Bentley, que tiene 6 rutas frente a 5 de Autodesk)? | Dejar Autodesk · Bentley · IA y datos · Topografía · General. Con áreas del mismo alto, el orden pesa poco. Si se quiere personalizar, P2-1. |
| P-3 | ¿Se eliminan las vitrinas «Destacados / Nuevos / Más usados» de Bentley? Miden 1 198 px y repiten los productos. | **Sí.** «Nuevos» es una lista fija en el código que se queda vieja. Si quieres conservar algo, que sea «Destacados» dentro de `?vendor=bentley`. |
| P-4 | ¿Se pliega cada proveedor por defecto (acordeón) en celular? | **No.** Con vitrinas cortas la página baja a unas 6 pantallas sin plegar. Plegar oculta contenido a Ctrl+F y las anclas no abren un `<details>` en todos los navegadores. |
| P-5 | ¿Se quitan los chips «Gratuito» y «Oficial» de la tarjeta (están en el 99 % y el 81 % de los recursos) y se muestra solo «De pago»? | **Sí**, y explicarlo en la leyenda. |
| P-6 | `catalog.css` tiene colores de marca y de disciplina fuera de `tokens.css`, y en claro pisa los `--d-*` accesibles. ¿Se migran a tokens en un PR aparte? | **Sí, en un PR aparte** de `diseno-ui`, fuera de este plan, para no mezclar jerarquía con paleta. |
| P-7 | El área de los recursos sin producto se deduce de su ruta (139 de IA y datos y 13 de Autodesk). ¿Prefieres que `curador-semillas` les asigne productos en `seed/`? | Usar la deducción ahora (P0-1, sin tocar semillas) y abrir una tarea de curaduría aparte para asignar productos. Así salen de «Más de <área>» hacia filas por producto. |

**Riesgos:**

- **Pruebas que esperan el bloque general arriba o las vitrinas.** Se ajustan solo esas aserciones en P0-2 y se listan en el PR.
- **Rendimiento.** La deducción del área por ruta suma, como máximo, una consulta fija. La prueba de consultas acotadas lo vigila.
- **Enlaces guardados a `#vendor-bentley`.** Siguen funcionando: el `id` se conserva en la portada.
- **Muchas áreas en el futuro** (Trimble, Esri). El mapa crece una tarjeta por área. A partir de 8 áreas, revisar si se
  agrupan.

## 9. Plataformas oficiales y avance (D43, 2026-10-20)

Pedido de la dueña: «Dar prioridad al avance en Bentley: se ha decidido que son las plataformas oficiales, por lo que es bueno
que muestre más información y seguimiento a esos temas». Decisiones: las plataformas oficiales son **Bentley y Autodesk, con
Bentley primero**; el avance y la información extra se ven en el **catálogo** y en la **portada de inicio** (no en la hoja de
personaje, por ahora). Rama `plataformas-oficiales-avance`, sin commit (cambios en el árbol, para revisar).

### 9.1 Qué cambia

- **Orden:** Bentley · Autodesk · IA y Datos · Topografía, GIS y captura · Conocimiento general, en el mapa, en las secciones de
  área, en el filtro «Proveedor» y en `?vendor=` (`software.AREA_ORDER`, `FAMILIES`). Las anclas `#vendor-*` y los parámetros
  `?vendor=`, `?software=` y demás no cambian.
- **Marca:** «Plataforma oficial» (texto con borde de `--amber-ink`; sobre las bandas, `currentColor`) solo en Bentley y Autodesk:
  tarjeta del mapa, banda del área y vista `?vendor=`. El mapa les da más ancho (2 por fila a 1280 px; una por fila a 375 px).
- **Avance de quien mira** (`apps/catalog/official.py`, sin modelo nuevo y sin guardar nada), por plataforma:
  «N de M cursos · P %», una barra `<progress>` con `aria-label` y texto de reserva, «Esenciales: x de y» (y los que están en
  revisión), y **«Siguiente sugerido»** con enlace al curso y a su ruta.
  - Criterio de «hecho» **igual al de `progress/external.py`**: credencial verificada = hecho; pendiente = en revisión; rechazada
    o ninguna = por hacer (`credentials.services.states_by_resource`, solo las credenciales de la persona).
  - «Siguiente sugerido»: el esencial por hacer más relevante (nivel más básico, luego oficial, luego título). Sin esenciales por
    hacer, el siguiente por hacer; con todo hecho o en revisión, «Todo al día». Un curso en revisión no se sugiere; uno rechazado sí.
  - Sin avance no hay ceros: «Aún no empiezas aquí · N cursos · M esenciales» y «Primer paso sugerido».
- **Tarjetas de curso** de esas áreas (portada del catálogo, `?vendor=`, `?software=` y resultados): chip de estado («✓ Hecho»,
  «En revisión», «Por hacer», con texto y símbolo; el color solo refuerza) y «Esencial». «Para empezar» muestra **8** tarjetas en
  las áreas oficiales (4 en las demás). La meta ya trae nivel · tipo · duración y la ruta.
- **Portada de inicio:** franja «Tus plataformas oficiales» (Bentley, luego Autodesk) bajo el bloque de bienvenida y «Empieza
  aquí», con el mismo avance y un botón «Seguir con <curso>» (o «Empezar con <curso>» sin avance). No aparece si no hay catálogo.
- **Privacidad:** todo sale de las credenciales de `request.user`; nunca se muestra el avance de otras personas.

### 9.2 Archivos

`apps/catalog/official.py` (nuevo), `software.py` (orden, `OFFICIAL`, `OFFICIAL_STARTERS`), `services.py`
(`resource_queryset(with_skills, ordered)` y `published_path_links` con `UNION`), `views.py`, plantillas
`partials/{official_panel,official_mark,card_state,map,area,card,card_compact}.html` y `resources.html`,
`static/catalog/official.css` (nuevo; solo tokens; lo cargan el catálogo y la portada), `core/services.py` y `core/home.html`.
Pruebas: `tests/test_plataformas_oficiales.py` (nuevo) y los ajustes de orden en `test_catalogo_jerarquia.py` y
`test_software_guides.py`.

### 9.3 Mediciones

Semillero de 354 recursos y 22 rutas; persona de prueba con 4 verificadas, 2 en revisión y 1 rechazada de Bentley, y 6, 2 y 0 de
Autodesk; alturas del DOM.

| Medida | Antes | Después | Presupuesto |
|---|---|---|---|
| Catálogo a 375 px, alto | 4 116 | **4 564** (claro) · 4 467 (oscuro) | ≤ 6 500 |
| Bentley empieza a 375 px | 1 348 (segundo) | **924** (primero) | ≤ 1 500 |
| Mapa a 375 px (empieza · termina) | 481 · 775 | 481 · **904** | — |
| Catálogo a 1280 px, alto | 2 668 | **3 418** | ≤ 4 500 |
| Bentley empieza a 1280 px | 853 | **607** | — |
| Tarjeta compacta a 375 px (máx.) | 173 | **173** | ≤ 190 |
| HTML del catálogo | 39 KB | **48 KB** | ≤ 100 KB |
| Consultas del catálogo | 44 | **44** | ≤ 55 |
| Consultas de `?vendor=bentley` | 29 | **29** | — |
| Consultas de la portada | 52 | **58** (+6) | ≤ +6 |
| Tarjetas de recurso en el catálogo · imágenes | 14 · 26 | **22** · 26 | ≤ 24 · ≤ 60 |
| Desborde horizontal a 375 px | no | **no** | — |

Las consultas no crecen con los datos (`test_catalog_and_home_queries_do_not_grow_with_data`: más recursos, rutas y credenciales
duplicadas). Para no pasar de +6 en la portada: `published_path_links` usa un `UNION` (1 consulta en vez de 2), el área de cada
recurso se calcula sin la consulta de esenciales ni la de etiquetas (salen de los mismos recursos) y la portada no precarga las
habilidades. Contraste (`contrast.py`, claro y oscuro): pares base y los usados por lo nuevo (`--amber-ink` y `--ok` sobre
`--sheet`, `--level` sobre `--sheet-2`) en verde.

### 9.4 Qué queda más débil

- Bentley solo trae **6 esenciales de 51**: «Siguiente sugerido» salta pronto a cursos no esenciales (y hoy el primero es una
  colección de acreditaciones). Marcar más esenciales es P2-3 (`curador-semillas`, `seed/rutas/bentley-*.json`).
- «Siguiente sugerido» abre el sitio del fabricante en otra pestaña; el estado solo cambia cuando se sube y se verifica la credencial.
- En las áreas oficiales a 375 px cada área mide 740 – 880 px (antes ≤ 703): el panel de avance suma unos 170 px.
- Blancos táctiles: los nuevos, las bandas y los chips de producto miden ≥ 44 px; los enlaces dentro de las tarjetas (título,
  «En la ruta», chip de XP) ya medían menos y no se tocaron.
- La hoja de personaje no muestra este avance (decisión de la dueña, «por ahora»).
