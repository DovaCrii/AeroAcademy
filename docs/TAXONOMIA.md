# Taxonomía · cómo crece la academia

## Ejes

```
Vendor (empresa de software)   Autodesk · Bentley · Trimble · Esri · Microsoft · Oracle · DJI …
  └─ Product                     Revit · Forma · OpenRoads Designer · MicroStation · TBC · ArcGIS Pro …
       └─ LearningPath (Campaña) Ruta Forma + Revit · Ruta Bentley Learn · …
            └─ Level (Capítulo) → Milestone (Misión) / QuizQuestion / ExternalCourse
```

Etiquetas transversales, que se combinan con los ejes anteriores:

| Etiqueta | Valores | Uso |
|---|---|---|
| **Disciplina** | `arquitectura`, `civil-estructural`, `topografia`, `mecanica`, `captura-rpa` | Filtros, clase del personaje, mundo por defecto, portada |
| **Habilidad** (`Skill`) | `modelado-bim`, `corredores-viales`, `nubes-de-puntos`, `georreferenciacion`, `documentacion`, `analisis-ambiental`, `normativa-dgac`, … | Matriz de competencias y atributos de la hoja de personaje |
| **Tipo de recurso** | `course`, `module`, `tutorial`, `exam`, `guide`, `article`, `collection`, `learning_plan` | Iconos y filtros |
| **Mundo** | `architecture`, `civil`, `survey`, `mechanical`, `aero` | Diseño visual de la ruta (`MUNDOS.md`) |

**Platform** y **Vendor** son cosas distintas. La plataforma es *dónde* se aprende o se certifica (Autodesk Learning, Bentley Learn, Certiport, Geocom Cursos, DGAC). El vendor es *de quién* es el software. Un mismo vendor puede tener varias plataformas.

## Tipos de ruta

| `kind` | Qué es | Cómo se avanza | Ejemplo |
|---|---|---|---|
| `structured` | Ruta propia del equipo, con niveles, hitos, quiz, notas y kit | Marcando misiones y respondiendo el quiz; los certificados de los recursos marcan los hitos ligados | `forma-revit` (CC 410) |
| `external_track` | Lista curada de cursos de un sitio externo que **ya entrega certificado** | Registrando cada curso por nombre y subiendo su certificado. Un lead lo verifica y eso desbloquea el avance | `bentley-learn` |

Una ruta `external_track` acepta además **cursos libres**: la persona escribe nombre, URL y fecha de un curso que no
está en la lista y sube el certificado. Si el lead lo aprueba, puede promoverlo al catálogo con un clic. Así la
ruta crece con lo que el equipo realmente hace.

## Reglas

- **Slugs:** en minúsculas, con guiones y sin tildes (`openroads-designer`). Son estables: renombrar el título no cambia el slug.
- **Keys:** estables y solo se agregan al final (D7). El formato es por tipo:

  | Tipo | Formato | Ejemplo |
  |---|---|---|
  | Hito | `nX-tY` | `n3-t6` |
  | Pregunta | `nX-qY` | `n3-q1` |
  | Curso externo | `<capitulo>-cY` | `ord-c3` |

- **Etiquetado:** toda ruta declara `vendor`, `products[]`, `disciplines[]` y `world`. Un recurso hereda las disciplinas de su ruta salvo que declare las propias.
- **Crecimiento:** para sumar un vendor o un producto se edita `seed/vendors.json`; para sumar una ruta, se agrega un JSON en `seed/rutas/` usando la skill `nueva-ruta`. No hace falta tocar código.
- **Vista de navegación:** *Rutas* → pestañas por vendor → tarjetas de producto → campañas, con filtros por disciplina y habilidad. La portada muestra además "Rutas de mi disciplina".
