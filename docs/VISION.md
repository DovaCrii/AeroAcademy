# Visión · AeroAcademy · Academia LEV Digital 101

Referencia visual: `design/referencia-academia.jpg`. Portada funcional de referencia: `design/academia/index.html`.
Referencia del primer mundo (Arquitectura): `legacy/ruta-forma-revit/static/index.html`.

**Marca:** AeroAcademy es la plataforma; la Academia LEV Digital 101 es la academia que vive dentro.
**Lema:** Aprender · Compartir · Colaborar · Avanzar.

## Para quién

Un equipo pequeño donde todo es visible: quién está aprendiendo qué, quién tiene qué certificado y a quién preguntar.
El dueño del proyecto modera: aprueba a las personas, valida certificados, ordena el foro y publica avisos.

## Disciplinas (taxonomía transversal)

Arquitectura · Civil-Estructural · Topografía · Mecánica · **Captura/RPA** (drones, LiDAR, escáner; la "Aero" de AeroAcademy).
Todo contenido (rutas, recursos, documentos, hilos, consultas, credenciales, personas) puede etiquetarse con una o más disciplinas.
La organización por empresa de software está en `TAXONOMIA.md`.

## Módulos de la portada → módulos del sistema

| Módulo | Qué es en el sistema | App |
|---|---|---|
| Rutas | Campañas por empresa → producto, cada una en su mundo visual | `catalog` + `paths` + `progress` |
| Equipo | Directorio y **hojas de personaje**: clase, nivel, título, insignias, credenciales validadas | `accounts` + `team` + `gamification` |
| Certificaciones | Repositorio de certificados con validación, vencimientos y exportación | `credentials` |
| Documentos | Biblioteca técnica con versiones | `library` |
| Foro | Hilos por categoría y disciplina; incluye las notas de las rutas | `community` |
| Consultas | Preguntas y respuestas con respuesta aceptada | `community` |
| Avance | Avance por persona y ruta, tablón del gremio y propuestas de mejora | `progress` + `team` + `knowledge` |
| Conocimiento | Lecciones aprendidas, procedimientos, glosario | `knowledge` |
| Teo | Asistente que responde sobre rutas, foro y cómo usar la academia | `assistant` |

## Principios

Una comunidad de profesionales · Información organizada · Colaboración sin límites · Aprendizaje continuo · Un solo lugar para avanzar.
Además: **aprender se tiene que ver**. Cada curso con su certificado desbloquea algo visible, como XP, una insignia, un título o un piso del edificio.

## Estilo visual

- **Marco general:** fondo azul marino profundo, acento azul eléctrico (`#1E8CFF`) y cian (`#4CC6FF`), texto blanco. Alto contraste. Tarjetas de vidrio con borde fino.
- **Mundos:** cada especialidad tiene una metáfora propia tomada de su herramienta. Arquitectura usa corte y láminas; Civil, la planta-perfil del camino; Topografía, la carta topográfica; Mecánica, el despiece; Aero, el HUD de vuelo. Ver `MUNDOS.md`.
- **Capa de juego:** sprites 8-bit en SVG (avatares, insignias, Teo), números de nivel en Press Start 2P y rarezas por color: común gris, rara azul, épica violeta, legendaria dorada. Debe verse profesional: el pixel-art se usa como acento, nunca como fondo de pantalla completa.
- Tipografía Archivo; "ACADEMIA" con tracking ancho; "LEV DIGITAL 101" en negrita, con el "101" en azul.
- Responsive a 390 px, foco visible y `prefers-reduced-motion` respetado (las animaciones de logro se vuelven estáticas).

## Mascota

**Teo**: un teodolito 8-bit con patitas cortas, casco de obra amarillo y una pequeña hélice de dron en la cabeza
(la "Aero"). Cambia de atuendo según el mundo: chaleco reflectante en Civil, sombrero de explorador en Topografía,
gafas de piloto en Aero, lápiz tras la oreja en Arquitectura y llave inglesa en Mecánica. Ver `BOT.md`.
