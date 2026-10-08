# Referencias de diseño · qué tomamos de cada una

Regla: tomar **un patrón concreto** de cada referencia y adaptarlo a un equipo pequeño de ingeniería.
No copiar estilos ni marcas.

| Referencia | Patrón que tomamos | Dónde se aplica |
|---|---|---|
| **Prototipo propio: Ruta Forma + Revit** (`legacy/`, artefacto del equipo) | Cada pieza de la interfaz es un elemento del oficio: cajetín, corte, Project Browser, schedules y nubes de revisión | Gramática común de todos los mundos (`MUNDOS.md`) |
| **Salesforce Trailhead** | *Trails* con insignias por módulo; **rangos** con nombre que suben con puntos e insignias; *Superbadges* que exigen aplicar lo aprendido | Campañas → trofeos; títulos por nivel; *Reliquias* como "superinsignias" |
| **Microsoft Learn** | XP por módulo completado, nivel visible en el perfil y colecciones propias | XP por misión y capítulo; "mis colecciones" a futuro |
| **Duolingo** | **Racha** con recompensa por constancia y meta diaria o semanal visible; celebración corta al lograrla | Racha semanal (no diaria: es un equipo de trabajo), modal de subida de nivel |
| **Habitica** | **Clases RPG** y **avatar por capas** con equipamiento que se desbloquea; las misiones de grupo suman de forma colectiva | Clases por disciplina, avatar 8-bit por capas, *Expedición del equipo* |
| **Discourse** | **Niveles de confianza**, banderas o reportes, hilos fijados y respuesta aceptada (*solved*) | Moderación, reportes, consultas con respuesta aceptada |
| **Stack Overflow** | Reputación por responder bien; insignias de comunidad | XP por respuesta aceptada, insignias *Sabio del Foro* y *Mentor* |
| **Credly / Open Badges** | Insignia ligada a evidencia verificable (emisor, fecha, URL de verificación) | Cada credencial guarda emisor, ID y URL de verificación; la insignia apunta a la credencial |
| **Khan Academy** | **Mapa de dominio** por niveles (intentado → familiar → competente → dominado) | Atributos de 0 a 20 y árbol de habilidades por vendor |
| **GitHub** | Gráfico de contribuciones (calendario de calor) | Línea de actividad en la hoja de personaje |
| **Geocom Cursos** (soporte.geocom.cl) | Fichas de curso por marca y equipo: portada, tipo, valoración y descripción breve; soporte por línea de producto | Tarjetas de recurso en el catálogo, con vendor, tipo, duración y notas del equipo como "valoración" |
| **Bentley Learn** (learning.bentley.com) | Catálogos por producto y **learning plans de acreditación** (cursos + *Assessment* o *Project Submission*). Tarjetas con portada por producto, tipo (*On Demand*, *ILT*, *Learning plan*), duración, idioma y valoración; filtros por tipo, precio, idioma, duración, nivel, marca y producto | Estructura de la Ruta Bentley (capítulos por producto, acreditaciones como Reliquias); **vitrina de trofeos** de la hoja de personaje y catálogo de recursos con las mismas tarjetas y filtros, más el estado (verificado / en revisión) y el XP. Ver `design/perfil/hoja-personaje.html` |
| **Aerotop** (aerotop.cl y sus publicaciones de LiDAR/drones) | Arte de presentación del levantamiento digital: azul noche con grilla técnica, acento ámbar, **títulos en serif cursiva**, etiquetas monoespaciadas `CLAVE · valor`, recuadros de anotación de línea fina, retículas, **nube de puntos** blanca y ámbar, **línea de escaneo** naranja, barra de escala y secciones numeradas `// 01` | Estilo **Levantamiento** (`core/static/core/levantamiento.css` y `.js`): portada del mundo Arquitectura y, más adelante, el mundo `aero`. Las lecturas muestran datos reales de la ruta, nunca inventados |
| **Videojuegos 8-bit** (RPG clásicos) | Ventanas de diálogo con borde pixelado, barras de vida y XP, cofres al subir de nivel | Modal de logro, barra de XP, diálogos de Teo |

## Qué evitamos

- Rankings individuales permanentes (D17). En su lugar, el tablón semanal y las metas de equipo.
- Notificaciones invasivas: no hay correo en el MVP y la campana se puede silenciar.
- Pixel-art a pantalla completa: el 8-bit es acento, no fondo. La vista profesional del perfil no lleva elementos de juego.
- Premiar el volumen sin evidencia: el XP grande exige un certificado verificado (D13).

## Mejoras candidatas después del MVP

- Importar las insignias de Credly de cada persona (Bentley y Autodesk publican varias allí).
- Ficha de competencias PDF por persona para licitaciones, desde la vista profesional.
- "Duelo amistoso de quiz" entre dos personas sobre un capítulo, sin XP grande, solo por diversión.
- Temporadas trimestrales, con insignias de temporada que no se vuelven a emitir.
- Mapa del gremio: todas las campañas como un mapa de mundo 8-bit donde se ve en qué mundo anda cada persona.
