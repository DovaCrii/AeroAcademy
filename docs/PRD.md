# PRD · Academia LEV Digital 101 (MVP)

## Problema

El equipo se capacita en muchas plataformas (Autodesk, Esri, Microsoft, Oracle, fabricantes de drones, etc.).
Hoy el avance no se ve, lo aprendido no se comparte, y los certificados quedan repartidos en correos y
carpetas personales. Cuando una licitación o un cliente pide acreditar competencias, cuesta reunir la evidencia
y nadie sabe qué credencial está por vencer.

## Objetivo del MVP

Un solo lugar, interno y accesible por la tailnet, donde:

1. Se publican **rutas de aprendizaje** de cualquier plataforma (la primera: Ruta Forma + Revit de CC 410).
2. Cada persona registra su **avance** (hitos y quiz) y el equipo lo ve.
3. El equipo deja **notas** sobre recursos: qué funciona, qué no, recomendaciones y dudas.
4. Cada persona sube sus **certificados y credenciales**, que un responsable valida, con control de **vencimiento**.
5. Se puede **exportar evidencia** (por persona o por selección) para licitaciones y clientes.
6. El equipo encuentra **documentos** técnicos vigentes, **conversa** en un foro, **resuelve consultas** y guarda **conocimiento** reutilizable.

Todo organizado por disciplina: Arquitectura, Civil-Estructural, Topografía y Mecánica (ver `VISION.md`).

## Roles

| Rol | Puede |
|---|---|
| Miembro | Ver catálogo y rutas, registrar su avance, dejar notas, subir y editar sus credenciales, ver el tablero del equipo |
| Responsable (lead) | Todo lo anterior, validar o rechazar credenciales, ver archivos de credenciales del equipo, exportar evidencia |
| Administrador (Maestro del gremio) | Todo lo anterior, aprobar personas, moderar el foro, publicar anuncios, definir expediciones, administrar plataformas, recursos, rutas y personas |

## Historias de usuario (MVP)

### Catálogo y rutas
- Como miembro, veo un catálogo de **plataformas** (Autodesk Learning, Esri Training, Microsoft Learn…) con sus recursos.
- Como miembro, abro una **ruta** y la recorro por niveles, como en el prototipo (corte del edificio, Project Browser).
- Como admin, cargo una ruta desde un JSON (formato de `seed/rutas/forma-revit.json`) sin tocar código.

### Avance
- Como miembro, marco hitos y respondo el mini quiz de cada nivel; mi porcentaje se actualiza.
- Como miembro, defino mi **meta de certificación** por ruta.
- Como equipo, vemos una **tabla de avance** por persona y por ruta.

### Notas
- Como miembro, dejo una nota sobre un nivel o un recurso con tipo *Funciona*, *No funciona*, *Recomendación* o *Duda*.
- Como miembro, respondo notas y borro solo las mías.
- Como equipo, vemos una **bitácora** filtrable por tipo, ruta y nivel.

### Certificados (repositorio)
- Como miembro, subo un certificado (PDF o imagen) con: título, plataforma/emisor, tipo, ID de credencial,
  URL de verificación, fecha de emisión y de vencimiento, y habilidades asociadas.
- Como miembro, puedo vincular el certificado a una ruta o recurso (ej.: *Learn Forma Site Design in 90 minutes*),
  y al hacerlo se marca el hito correspondiente si existe.
- Como responsable, valido o rechazo con comentario; el estado queda registrado.
- Como equipo, vemos el **listado** de credenciales validadas (sin abrir el archivo).
- Como responsable, recibo en el tablero las credenciales que **vencen en 60 días** y las vencidas.
- Como responsable, **exporto evidencia**: ZIP con los PDF + planilla XLSX (persona, credencial, emisor, ID, fechas, URL).

### Documentos
- Como miembro, busco documentos por disciplina, tipo (manual, guía, plano tipo, normativa, plantilla, familia) y etiqueta.
- Como responsable, publico un documento y sus nuevas versiones; se ve siempre la versión vigente y el historial.

### Foro y consultas
- Como miembro, abro un hilo en una categoría y disciplina, y respondo hilos de otros.
- Como miembro, publico una consulta; quien la hizo (o un lead) marca una respuesta como solución.
- Como equipo, vemos las consultas sin respuesta destacadas en la portada.

### Conocimiento y mejoras
- Como miembro, propongo una mejora que avanza por Idea → Plan → Ejecución → Resultado.
- Como lead, convierto una consulta resuelta o una lección aprendida en artículo de conocimiento.

### Tablero
- Portada como `design/academia/index.html`: disciplinas, 7 módulos, rutas por disciplina; más avance del equipo por ruta, últimas notas, credenciales validadas recientes y por vencer.
- **Matriz de competencias**: personas × habilidades, a partir de credenciales validadas y rutas completadas.

### Rutas por empresa de software
- Como miembro, navego las rutas por **vendor** (Autodesk, Bentley…) → producto → campaña y filtro por disciplina.
- Como miembro, en la **Ruta Bentley** registro cada curso de learning.bentley.com que termino (nombre + certificado). Cuando el moderador lo verifica, avanzo en la ruta.
- Como miembro, registro un **curso libre** que no está en la lista; el moderador puede sumarlo al catálogo.
- Como miembro, cada ruta se ve con el **diseño de su especialidad** (MUNDOS.md).

### Juego y hoja de personaje
- Como miembro, gano **XP** por misiones, quiz y, sobre todo, por certificados verificados; subo de **nivel** y desbloqueo **títulos**.
- Como miembro, gano **insignias** y las veo en mi hoja de personaje, junto con mi clase, mis atributos y mi avatar 8-bit.
- Como miembro, edito mi hoja: titular, bio, enlaces, clase, título y avatar.
- Como equipo, vemos el **tablón del gremio** y una **expedición** mensual compartida.

### Teo
- Como miembro, le pregunto a Teo qué me falta, cómo subir un certificado o qué dijo el equipo sobre un tema, y me responde con enlaces internos.

### Moderación
- Como moderador, apruebo a cada persona nueva antes de que vea contenido.
- Como moderador, fijo, cierro, oculto y muevo hilos; reviso reportes; publico anuncios.
- Como miembro, recibo notificaciones en la campana: certificados revisados, insignias, respuestas, anuncios.

## Fuera del MVP

- Login propio o SSO corporativo (el MVP usa la identidad de Tailscale).
- Notificaciones por correo (se deja el gancho, ver PLAN bloque 8).
- Integración automática con APIs de las plataformas (Credly, Autodesk, etc.). En el MVP la carga es manual.
- App móvil. La web debe ser responsive.
- Publicación en internet.

## Métricas de éxito (primeros 3 meses)

- 100 % del equipo con al menos una ruta iniciada.
- Al menos 1 nota por persona.
- Todas las credenciales vigentes del equipo cargadas y validadas.
- Exportar la evidencia de una licitación en menos de 5 minutos.
