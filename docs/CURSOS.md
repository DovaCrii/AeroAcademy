# Cursos · mapa, brechas e ideas

Qué cursos hay hoy, qué falta y cómo se agregan más. Es el complemento de `TAXONOMIA.md` (cómo se clasifica),
`MUNDOS.md` (cómo se ven) y la sección «Rutas de conocimiento general» de `GAMIFICACION.md` (cómo se premian).
Los datos de la sección 1 salen de contar `seed/rutas/*.json` (2026-10-13); rehacer el conteo al cambiar las semillas.

Lo específico de una organización concreta (clientes, proyectos, diagnósticos) no va en este documento.

## 1. Inventario

Hoy hay **14 rutas**: 13 en `seed/rutas/` y la de operaciones con drones, que es privada (`private/dgac/`, no entra a git).
«Estructurada» = niveles con misiones y quiz; «externa» = lista de cursos de un proveedor que entrega su propio certificado.

| Slug | Título | Proveedor | Tipo | Disciplinas | Niv. | Misiones | Preguntas | Cursos ext. |
|---|---|---|---|---|---|---|---|---|
| `topografia-101` | Topografía 101 · Entender el territorio | AeroAcademy | **Propia** (estructurada) | Topografía, Transversal | 13 | 61 | 68 | 0 |
| `bim-101` | BIM 101 · Pensar en modelos | AeroAcademy | **Propia** (estructurada) | Transversal, Arquitectura | 9 | 37 | 46 | 0 |
| `dgac-rpas` | Diploma interno RPAS (privada) | DJI (tema) | **Propia** (estructurada, privada) | Captura/RPA, Topografía | 7 | 37 | 38 | 0 |
| `autocad` | Ruta AutoCAD · la base | Autodesk | Externa-guiada (estructurada) | Transversal | 7 | 24 | 7 | 0 |
| `forma-revit` | Ruta Revit | Autodesk | Externa-guiada (estructurada) | Arquitectura, Civil-Est., Mecánica | 7 | 25 | 7 | 0 |
| `forma-coordinacion` | Ruta Forma · Coordinación | Autodesk | Externa-guiada (estructurada) | Arquitectura, Transversal | 5 | 24 | 8 | 0 |
| `civil-3d` | Ruta Civil 3D | Autodesk | Externa-guiada (estructurada) | Civil-Est., Topografía, Arq., Mecánica | 6 | 21 | 8 | 0 |
| `plant-3d` | Ruta AutoCAD Plant 3D | Autodesk | Externa-guiada (estructurada) | Mecánica | 5 | 11 | 5 | 0 |
| `bentley-learn` | Ruta Bentley (MicroStation, OpenRoads, OpenBridge) | Bentley | Externa (`external_track`) | Transversal, Civil-Est. | 4 | 0 | 0 | 6 |
| `bentley-openbuildings` | Ruta OpenBuildings | Bentley | Externa | Arquitectura, Civil-Est. | 1 | 0 | 0 | 2 |
| `bentley-openplant` | Ruta OpenPlant | Bentley | Externa | Mecánica | 1 | 0 | 0 | 4 |
| `bentley-projectwise` | Ruta ProjectWise | Bentley | Externa | Transversal | 1 | 0 | 0 | 5 |
| `bentley-itwin` | Ruta iTwin | Bentley | Externa | Captura/RPA | 2 | 0 | 0 | 6 |
| `bentley-lumenrt` | Ruta LumenRT | Bentley | Externa | Arquitectura | 1 | 0 | 0 | 1 |

Las rutas de Autodesk son «estructuradas» pero su contenido es externo: enlazan a cursos oficiales y agregan misiones
prácticas y un quiz corto del equipo. Solo las tres primeras son contenido **propio**.

### Estado de cada ruta

| Slug | Guía por nivel | Imágenes | Diapositivas (`slides`) | Diploma interno | Mundo visual (`world`) → el que se ve |
|---|---|---|---|---|---|
| `topografia-101` | Sí (13/13) | Sí, SVG propios (12/13 niveles) | No | **Sí** | `survey` → Arquitectura (no hay diseño propio) |
| `bim-101` | Sí (9/9) | Sí, SVG propios (9/9) | No | **Sí** | `architecture` |
| `dgac-rpas` | No (usa infografías privadas y banco de preguntas propio) | Sí, infografías privadas | No | **Sí** (al aprobar la prueba) | `aero` |
| `autocad` | Sí (7/7) | No | No | No | `mechanical` → Arquitectura |
| `forma-revit` | Sí (7/7) | No | No | No | `architecture` |
| `forma-coordinacion` | Sí (5/5) | No | No | No | `architecture` |
| `civil-3d` | Sí (6/6) | No | No | No | `civil` → Arquitectura (el mundo civil solo dibuja rutas externas) |
| `plant-3d` | Sí (5/5) | No | No | No | `mechanical` → Arquitectura |
| `bentley-learn` | Parcial (1/4) | No | No | No | `civil` |
| `bentley-openbuildings` | No (0/1) | No | No | No | `civil` |
| `bentley-openplant` | Parcial (1/1) | No | No | No | `civil` |
| `bentley-projectwise` | Sí (1/1) | No | No | No | `civil` |
| `bentley-itwin` | Sí (2/2) | No | No | No | `civil` |
| `bentley-lumenrt` | Sí (1/1) | No | No | No | `civil` |

- **Diapositivas:** ninguna ruta tiene `slides` todavía; el motor de pasos («Paso 3 de 7») está en construcción.
  Los niveles sin `slides` seguirán viéndose como hoy (guía + práctica + quiz).
- **Diploma interno:** solo las rutas de plataforma `interna` (ver `GAMIFICACION.md`). Autodesk y Bentley entregan su
  certificado, que se sube como credencial.
- **Mundos con diseño hoy:** `architecture` (rutas estructuradas), `civil` (rutas externas) y `aero`. Los mundos
  `survey` y `mechanical` están declarados pero sin plantillas: caen al de su tipo de ruta.

## 2. Mapa por disciplina

Una ruta puede estar en varias disciplinas. El camino va de lo base a lo avanzado; los números indican el orden sugerido.

| Disciplina | Rutas | Camino sugerido |
|---|---|---|
| **Transversal** | `topografia-101`, `bim-101`, `autocad`, `bentley-learn` (MicroStation), `bentley-projectwise`, `forma-coordinacion` | 1 `bim-101` y `topografia-101` (cultura común) → 2 `autocad` (dibujo base) → 3 `bentley-projectwise` / `forma-coordinacion` (datos comunes y coordinación) |
| **Arquitectura** | `bim-101`, `forma-revit`, `forma-coordinacion`, `bentley-openbuildings`, `bentley-lumenrt`, `civil-3d` (apoyo) | 1 `bim-101` → 2 `autocad` → 3 `forma-revit` → 4 `forma-coordinacion` → 5 `bentley-openbuildings` o `bentley-lumenrt` según la herramienta del proyecto |
| **Civil-Estructural** | `bentley-learn`, `civil-3d`, `bentley-openbuildings`, `forma-revit` (apoyo) | 1 `bim-101` → 2 `autocad` → 3 `civil-3d` **o** `bentley-learn` (MicroStation → OpenRoads/OpenBridge), según el estándar del proyecto → 4 `bentley-projectwise` |
| **Topografía** | `topografia-101`, `civil-3d`, `dgac-rpas` | 1 `topografia-101` → 2 `civil-3d` (terrenos y superficies) → 3 `dgac-rpas` si captura con dron. **Hueco:** nada de procesamiento (ver sección 3) |
| **Mecánica** | `plant-3d`, `bentley-openplant`, `autocad` (base), `forma-revit` (apoyo) | 1 `autocad` → 2 `plant-3d` **o** `bentley-openplant` según el estándar → 3 `bentley-projectwise` |
| **Captura · RPA** | `dgac-rpas`, `bentley-itwin` | 1 `topografia-101` (niveles de fotogrametría y escaneo) → 2 `dgac-rpas` → 3 `bentley-itwin` (realidad y gemelos). **Oferta corta:** 2 rutas |

## 3. Brechas

Prioridad según el impacto en quien aprende hoy y el esfuerzo (S/M/L) de cerrarla.

| Prio. | Brecha | Detalle | Esf. |
|---|---|---|---|
| **Alta** | Curso externo que vence | `forma-coordinacion`: Autodesk publica los cursos hasta el **15-10-2026**. Hacerlos antes o buscar reemplazo; revisar el resto de rutas externas con la misma pregunta | S |
| **Alta** | Cursos propios sin diapositivas | `topografia-101` y `bim-101` tienen guía e imágenes pero no `slides`; es lo primero que debe usar el motor nuevo | M |
| **Alta** | Sin evaluación final por curso | Solo `dgac-rpas` tiene prueba final que da diploma. Las otras rutas propias terminan cuando se marcan misiones y se acierta cada pregunta; falta un examen integrador (p. ej. 15 preguntas sorteadas de las existentes) | M |
| **Alta** | Mundo propio de Topografía (`survey`) | `topografia-101` es la ruta propia más larga y se ve con el mundo de Arquitectura. Diseño ya descrito en `MUNDOS.md` (carta topográfica, niebla de guerra) | L |
| **Media** | Mundos de Mecánica y Transversal | `mechanical` (despiece explosionado) sin plantillas; Transversal usa el mundo civil por defecto y Arquitectura en la práctica. Definir si Transversal necesita mundo o se queda con uno neutro | L |
| **Media** | Disciplinas con poca oferta | **Mecánica:** 2 rutas y una es externa. **Captura/RPA:** 2 rutas. **Topografía:** una propia y una externa de apoyo | M |
| **Media** | Herramientas sin ruta | SIG/QGIS/ArcGIS, procesamiento de nubes de puntos (ReCap, Descartes y similares), Navisworks y coordinación en la nube (ACC), Trimble TBC y Access, DJI Terra, georradar. Todas ya están en `vendors.json` o en el plan | M c/u |
| **Media** | Enlaces `verify_url` pendientes | `bentley-learn` (1), `bim-101` (2), `topografia-101` (1): confirmarlos con cuenta o buscador y quitar la marca | S |
| **Media** | Niveles externos sin guía | `bentley-openbuildings` (0/1) y 3 de 4 niveles de `bentley-learn` | S |
| **Baja** | Quiz corto en rutas guiadas | `autocad`, `forma-*`, `civil-3d` y `plant-3d` tienen entre 5 y 8 preguntas en total (≈1 por nivel); subir a ≥ 4 por nivel cuando se conviertan a diapositivas | M |
| **Baja** | Imágenes en rutas externas | Ninguna lleva infografías propias; priorizar los conceptos que el curso oficial explica peor | M |
| **Baja** | Contenido en inglés | Los cursos oficiales de Bentley y Autodesk están en inglés; resúmenes en español por nivel ayudan | M |

## 4. Ideas que vienen (backlog priorizado)

Esfuerzo: S = días, M = 1–3 semanas, L = más. «Propia» = contenido escrito aquí (genera diploma interno);
«externa» = lista curada de cursos de otro proveedor (certificado propio). Los prerrequisitos son sugeridos, no bloqueos.

| # | Curso | Objetivo | Público | Prerrequisitos | Fuentes posibles | Esf. | Tipo |
|---|---|---|---|---|---|---|---|
| 1 | **Nubes de puntos 101** | Entender qué es una nube, cómo se captura, se limpia, se registra y se entrega; leer calidad (densidad, ruido, georreferencia) | Todo el equipo; foco topografía, captura y BIM | `topografia-101` niveles de escaneo | Documentación pública de fabricantes de software de nubes; guías de ASPRS/ISPRS; infografías propias | M | Propia |
| 2 | **SIG/QGIS 101** | Cargar capas, sistemas de coordenadas, consultas y mapas; unir datos de terreno con proyectos | Topografía, civil, transversal | `topografia-101` (geodesia) | Documentación y cursos de QGIS (libre) y de Esri Training; datos abiertos del IDE Chile | M | Propia (con enlaces a externos) |
| 3 | **Coordinación BIM y ACC** | Plan de ejecución, modelos federados, detección de interferencias, incidencias y entorno común de datos | Coordinación, arquitectura, civil | `bim-101`; `forma-revit` o equivalente | Nivel propio sobre ISO 19650 y BCF; cursos oficiales de Autodesk para ACC y Navisworks | M | Propia + externa |
| 4 | **Fotogrametría avanzada** | Planificar vuelo, puntos de control, PPK/RTK, procesar y revisar calidad; cuándo no sirve | Captura, topografía | `topografia-101` (fotogrametría) y `dgac-rpas` | Manuales del software de procesamiento; guías públicas de ASPRS; casos propios genéricos | M | Propia |
| 5 | **Seguridad en terreno** | Riesgos al medir y volar (tránsito, altura, clima, calor, fauna), EPP, comunicación y qué hacer ante un accidente | Todo quien sale a terreno | Ninguno | Normativa pública (Ley 16.744, Mutualidades, ACHS/IST/Mutual), procedimientos propios genéricos | S–M | Propia |
| 6 | **Escaneo 3D en planta (brownfield)** | Levantar instalaciones existentes: planificar estaciones, registrar nubes, modelar tuberías y estructuras | Mecánica, captura | `plant-3d` o `bentley-openplant`; Nubes de puntos 101 | Guías públicas de escáner láser terrestre; infografías propias | M | Propia |
| 7 | **Trimble TBC y Access** | Procesar GNSS y estación total, ajustar redes y entregar | Topografía | `topografia-101` | Trimble Learning y su documentación pública | S (solo ruta) | Externa |
| 8 | **Georradar (GPR) 101** | Qué detecta, límites, interpretación básica y cuándo contratar | Topografía, civil | `topografia-101` | Guías públicas de geofísica aplicada; USACE/FHWA | M | Propia |
| 9 | **Gestión de datos del proyecto (CDE)** | Estructura de carpetas, nombres de archivo, versiones y control de cambios | Todo el equipo | `bim-101` | ISO 19650 resumida con palabras propias; `bentley-projectwise` | S–M | Propia |
| 10 | **Primavera P6 / programación** | Leer y actualizar un cronograma; relacionar con el modelo (4D) | Jefaturas de proyecto, civil | `bim-101` | Oracle University y guías propias | S (solo ruta) | Externa |
| 11 | **Power BI para ingeniería** | Tableros de avance y calidad a partir de planillas y modelos | Quien reporta | Ninguno | Microsoft Learn | S (solo ruta) | Externa |
| 12 | **Normativa DGAC para RPA** (versión pública) | Resumen general y enlaces oficiales de las reglas de vuelo, sin procedimientos internos | Pilotos, quien contrata vuelos | `dgac-rpas` (versión privada, que sigue como está) | Normativa vigente en dgac.gob.cl (leer la DAN vigente) | S | Propia |

**Banco de ideas desde roadmap.sh** (revisado 2026-10-13; se usan como mapa de temas, el contenido se escribe aquí con
palabras propias y recursos gratuitos oficiales). Ya incorporados en el área IA y Datos: `prompt-engineering`,
`claude-code`, `ai-agents`, `vibe-coding`, `code-review-best-practices`, `ai-product-builder`, `ai-red-teaming`,
`technical-writer`, `git-github-beginner`, `shell-bash`, `linux`, `python`, `python-data-analysis`, `sql`, `power-bi`,
`bi-analyst`, `data-analyst`, `ai-data-scientist`, `machine-learning`, `postgresql-dba` (PostGIS), `data-engineer`.
Para más adelante, si el equipo publica herramientas propias: `docker`, `cloudflare`, `api-design`, `mlops`;
para jefaturas: `product-manager`, `engineering-manager`. Otras brechas del área IA y Datos: deep learning y visión
por computador (Kaggle, Hugging Face; útil para clasificar nubes e imágenes de dron), ciencia de datos espacial con Esri
(no se encontró un curso gratuito oficial verificable), R (`r-programming`) y MLOps. Descartados por no aplicar al equipo: frameworks web y
móviles, lenguajes de sistemas, blockchain, desarrollo de juegos.

**Videos explicativos (idea, no construida).** HyperFrames (HeyGen, Apache-2.0, HTML → MP4) serviría como motor opcional
de render para lecciones cortas con subtítulos o para exportar un esquema animado a video. Hoy los esquemas animados de
los cursos (`diagram`) corren dentro de la página, sin video, con teclado y sin JS. Si se adopta: empezar con una sola
plantilla de 3–5 escenas (HTML/SVG + GSAP en pausa), subtítulos y transcripción editables, versión estática para quien
prefiere menos movimiento, render en un proceso aislado con versiones fijas de navegador y FFmpeg, y revisión humana antes
de publicar. No reemplaza al motor de diapositivas ni a los esquemas de la página.

Orden sugerido: 5 y 1 primero (alto valor, no dependen del motor de pasos), luego 2 y 3, después 4 y 6. Las rutas externas
(7, 10, 11) son rápidas de armar con la skill `nueva-ruta` y sirven para cerrar brechas de herramientas sin escribir contenido.

## 5. Cómo escalar

### Plantilla de curso propio

Una ruta nueva es un JSON en `seed/rutas/<slug>.json` (skill `nueva-ruta`; no se toca código). Estructura mínima por nivel,
con la clave `slides` (presentación, ver esquema abajo), `guide`, `quiz` y `images`:

```json
{
  "slug": "mi-curso-101", "title": "Mi curso 101 · Subtítulo", "program": "Curso interno · …",
  "platform": "interna", "kind": "structured", "vendor": "aeroacademy",
  "products": [], "disciplines": ["transversal", "topografia"], "world": "survey",
  "description": "…", "intro": {…}, "flow": […], "glossary": […], "certification_goals": […],
  "levels": [{
    "code": "n0", "order": 0, "short": "Para qué sirve", "title": "1 · …", "estimated_hours": "2 h",
    "audience": "…", "goal": "…", "mastery_signals": ["…"],
    "slides": [{"title": "…", "body": "Markdown corto", "points": ["…"],
                "image": "core/img/<tema>/<archivo>.svg", "caption": "…",
                "callout": {"kind": "dato|ojo|ejemplo|en-terreno", "text": "…"}, "terms": ["*término*"]}],
    "guide": {"title": "Guía rápida · …", "software": "gis", "do": ["…"], "commands": ["*término*"],
              "mistakes": ["…"], "essential": "Fuente principal",
              "images": ["core/img/<tema>/<archivo>.svg"]},
    "resources": [{"order": 0, "title": "…", "url": "https://…", "description": "…", "tags": ["Conocimiento general"]}],
    "milestones": [{"key": "n0-t0", "text": "…"}],
    "quiz": [{"key": "n0-q0", "question": "…", "options": ["…", "…", "…", "…"], "answer": 0, "explanation": "…"}]
  }]
}
```

**Detalle de una diapositiva** (`apps/catalog/guides.py:slides_for`; lo inválido se descarta sin romper la página):

| Campo | Qué es |
|---|---|
| `title` | Obligatorio (≤ 160). Sin título la diapositiva se omite. |
| `body` | Markdown de `apps/core/markdown.py`: `**negrita**`, listas, `código`, enlaces. **No** hay cursiva. |
| `points` | Hasta 8 viñetas; admiten `*término*`. |
| `image` | `core/img/…svg` (público) o `priv:<archivo>.jpg/png/webp/svg`, que se lee de `private/cursos/<slug>/fotos/` y se sirve por `/cursos/foto/<slug>/<archivo>` solo si la persona ve la ruta. Si la foto no está instalada, se muestra el texto sin imagen. |
| `callout` | `{"kind": …, "text": "…"}` con `kind` = `dato`, `ojo`, `ejemplo` o `en-terreno`. |
| `terms` | Hasta 12 chips. |
| `diagram` | Esquema animado tipo explainer: `nodes` (≤ 12; `id` `[a-z0-9_-]`, `label`, `sub`, `kind` equipo/dato/proceso/producto/persona, `x`,`y` = centro en % de un lienzo 16:9), `edges` (≤ 16; `from`, `to`, `label`, `flow: true` hace viajar un punto; su id es `from-to`) y `steps` (listas de ids que se revelan por partes; lo que no aparece se ve desde el inicio). Funciona sin JS; con JS, → revela la parte siguiente. |

Navegación: `/rutas/<slug>/?nivel=<code>&paso=<portada|1..N|guia|practica|quiz|recursos|notas>#panel`. Un nivel sin
`slides` se ve como portada + guía + práctica + preguntas.

Reglas de la plantilla:
- Las **keys** (`nX-tY`, `nX-qY`) y los `code` de nivel son estables y solo se agregan al final: de ellas dependen XP,
  insignias y diploma. Las diapositivas son solo presentación y no los cambian.
- Cada nivel: 6–10 diapositivas (concepto → cómo funciona → ejemplo chileno o de terreno → errores típicos → resumen),
  ≥ 4–6 preguntas de escenario con la respuesta correcta en posiciones variadas y **explicación siempre**.
- Los nombres de campos (`images`, `slides`) deben seguir el esquema vigente en `seed/rutas/topografia-101.json` y en
  `apps/catalog/guides.py`; ante una duda, manda el código.
- Para que cuente como «conocimiento general»: `"Conocimiento general"` en `tags` de cada recurso (ver `GAMIFICACION.md`).

### Checklist de autoría

- [ ] **Fuentes verificadas:** cada dato y cifra con una fuente pública abierta y revisada en navegador; anotar la fecha en `_nota`.
- [ ] **Palabras propias:** nada de párrafos, preguntas ni diagramas copiados; esquemas en SVG propios.
- [ ] **Sin marcas** en los cursos generales: conceptos, no productos. Las marcas van en las rutas por proveedor.
- [ ] **Público o privado:** lo que identifica clientes, proyectos, precios o procedimientos internos **no entra al repo**
  (carpeta `private/`, fuera de git, instalada solo en la VM). Revisar con búsqueda de texto antes de subir.
- [ ] **Tema oscuro y claro**, y legible a 375 px; texto de cada diapositiva ≤ 70 caracteres por línea.
- [ ] **Enlaces verificados** (el agente `verificador-enlaces`); marcar `verify_url` solo si falta confirmar.
- [ ] **Quiz:** keys estables, una sola respuesta correcta, explicación, sin datos personales.
- [ ] **Nala (la asistente; el código conserva el nombre `teo`)** solo recibe contenido público: nada privado va al índice de búsqueda ni a ninguna API externa.
- [ ] Correr `seed_catalog --dry-run`, `pytest` y `ruff`; recorrer la ruta en el navegador.

### Roles

| Rol | Hace | No hace |
|---|---|---|
| **Autor/a** | Escribe la ruta con la plantilla y las fuentes; prepara esquemas | Fusionar sus propios cambios |
| **Revisor/a técnico/a** | Lee el contenido de su especialidad, valida cifras, normas y casos; confirma que las preguntas tienen una sola respuesta correcta | Editar contenido de otra especialidad |
| **Admin** | Fusiona, instala en producción, copia lo privado a la VM, decide qué se publica y qué diploma otorga | Escribir contenido sin revisión |

Una persona no autoriza su propio curso: autoría y revisión técnica van separadas (ver `FLUJO_GITHUB.md`).

### Ritmo sugerido

- **Un nivel por semana** por autor/a: ~8 diapositivas, 5–6 preguntas y 4–5 misiones. Un curso de 9 niveles ≈ 2 meses.
- Alternar: una semana de escritura, una de revisión y ajustes; la revisión técnica no debe pasar de 3 días.
- No empezar un curso nuevo mientras haya uno sin evaluación final.
- Revisar cada trimestre los cursos externos (vencen y cambian) y los enlaces.

### Métricas (qué mirar)

| Métrica | Pregunta que responde |
|---|---|
| **Finalización por nivel** | ¿En qué nivel se abandona? Un descenso brusco suele ser contenido largo o confuso |
| **Aciertos por pregunta** | ¿Qué preguntas fallan casi todos? Reescribir la pregunta o explicar mejor el concepto |
| **Tiempo por nivel** (estimado vs real) | ¿Las horas declaradas son honestas? |
| **Diplomas emitidos** | ¿Se llega al final? ¿Cuánto tarda en promedio? |
| **Insignias que nunca se ganan** | ¿Hay un logro imposible o mal planteado? |
| **Consultas del asistente sobre un tema** | ¿Qué falta explicar en el curso? |

Revisar estas métricas por cohorte y no solo en total; usar el resultado para ajustar contenido antes de agregar más cursos.

### Cuándo pasar de «curso interno» a oferta externa

Conclusiones generales del análisis interno de escalabilidad y de mercado (no público; los datos concretos no se reproducen aquí):

1. **Primero demanda, después producto.** Un curso propio solo se ofrece fuera cuando alguien externo lo pidió o ya lo usa en
   piloto. Sin eso, seguir como curso interno.
2. **Condiciones mínimas** antes de abrirlo: examen final, contenido 100 % propio o con licencia clara, sin datos internos,
   revisado por una persona experta externa al autor y con la política de privacidad lista.
3. **El diploma es interno.** No llamarlo «certificado» ni sugerir que reemplaza al de Autodesk, Bentley, DGAC u otro
   organismo. Para valor externo se necesitan insignias verificables con enlace público de verificación.
4. **Cursos con franquicia o registro oficial** (p. ej. capacitación con código SENCE) requieren una institución
   autorizada y registro de asistencia; la plataforma sola no alcanza. Considerar aliarse en vez de construirlo.
5. **Infraestructura:** hoy la plataforma es de acceso cerrado (red privada). Abrir cursos a personas externas implica
   cuentas, almacenamiento y respaldo distintos; resolver eso antes de prometer acceso.
6. **Marcas de terceros:** no usar logos ni material oficial en una oferta comercial sin revisar sus guías de marca; mejor
   enlazar a lo oficial.

Hacer el camino inverso también es válido: un curso propio puede quedarse interno para siempre si su valor es cultural.

## Documentos relacionados

`TAXONOMIA.md` · `MUNDOS.md` · `GAMIFICACION.md` · `PENDIENTES.md` · skills `nueva-ruta` y `nuevo-mundo`.
