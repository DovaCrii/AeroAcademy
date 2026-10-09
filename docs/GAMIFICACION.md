# Gamificación · el gremio de ingeniería

Estética 8-bit tipo D&D, pero aplicada a lo que el equipo hace a diario: terreno, nubes de puntos, modelos y planos.
Debe ser entretenida **y** seria. El perfil tiene una vista profesional, presentable a un cliente, y una vista de juego.

## Vocabulario

| Sistema | En el juego | Nota |
|---|---|---|
| Ruta (`LearningPath`) | **Campaña** | Vive en un mundo (`MUNDOS.md`) |
| Nivel de ruta (`Level`) | **Capítulo** | |
| Hito (`Milestone`) | **Misión** | |
| Curso externo con certificado verificado | **Trofeo** | Ej.: un curso de Bentley Learn |
| Certificación o acreditación oficial verificada | **Reliquia** | Ej.: *Autodesk Certified Professional*, *Bentley Accredited Road Modeler* |
| Habilitación con vencimiento | **Alas** (RPA) o **Sello** (otras) | Ej.: credencial DGAC; si vence, se "apaga" |
| Equipo | **Gremio** | |
| Moderador | **Maestro del gremio** | |

## XP

| Origen | XP | Condición |
|---|---|---|
| Misión marcada | 10 | Se revoca al desmarcar |
| Pregunta de quiz correcta | 5 | Solo la primera vez |
| Capítulo completo (100 %) | 25 | Bonificación |
| Campaña completa | 150 | Bonificación |
| Trofeo (credencial `completion` verificada) | 100 | |
| Sello o Alas (`license` verificada) | 300 | Se conserva al vencer, pero la insignia se apaga |
| Reliquia (`certification` verificada) | 500 | |
| Capacitación interna verificada | 50 | |
| Nota con tipo *Funciona* o *Recomendación* | 5 | Máximo 5 al día |
| Respuesta aceptada en Consultas | 50 | Para quien respondió |
| Curso libre promovido al catálogo | 30 | Por enriquecer la ruta |
| Racha semanal (al menos 1 acción de aprendizaje en la semana) | 20 × semanas seguidas, máx. 100 | Se reinicia si se corta |

Reglas:
- Cada evento es un `XPEvent` único por (persona, `source`). Repetir una acción **no** duplica XP.
- Si una credencial pasa a `rejected` o vuelve a `pending` (al editarla, ver MODELO_DATOS), su XP y sus insignias se **revocan** hasta que se verifique de nuevo.
- El XP grande depende siempre de un certificado verificado (D13).

## Niveles

XP total para alcanzar el nivel `L` = `50 × L × (L − 1)`:

| Nivel | 2 | 3 | 4 | 5 | 6 | 8 | 10 | 12 | 15 | 20 |
|---|---|---|---|---|---|---|---|---|---|---|
| XP | 100 | 300 | 600 | 1 000 | 1 500 | 2 800 | 4 500 | 6 600 | 10 500 | 19 000 |

Como referencia, la Ruta Forma + Revit completa con 3 trofeos y una reliquia deja a una persona cerca del nivel 7.

## Carreras (antes «clases»)

La persona elige su **carrera** en el editor de avatar (o la sugiere el moderador). Son 13, agrupadas por disciplina; cada
una trae nombre real, título de juego, frase, look propio (ropa, gorro, lentes, herramienta y fondo que calzan entre sí),
paletas curadas, bonos a los atributos y una escalera de títulos (`seed/titulos.json`). El detalle vive en
`apps/gamification/avatar/careers.py`. Los slugs de las cinco clases originales no cambiaron.

| Disciplina | Carrera (slug) | Título de juego | Look | Bonos |
|---|---|---|---|---|
| Arquitectura | Arquitecto/a (`architect`) | Mago de la Forma | Blazer, rollo de planos, fondo plano azul | DOC +2, MOD +1 |
| Arquitectura | Modelador/a BIM (`bim_modeler`) | Tejedor de Familias | Polerón BIM, audífonos, taza de café | MOD +2, COL +1 |
| Arquitectura | Dibujante Proyectista (`drafter`) | Escriba de Láminas | Cardigan, escalímetro | DOC +2, NOR +1 |
| Civil | Ingeniero/a Civil-Estructural (`engineer`) | Paladín de las Cargas | Chaleco reflectante, gorra de seguridad, calculadora | ANA +2, NOR +1 |
| Civil | Inspector/a de Terreno (`inspector`) | Centinela de la Obra | Chaleco de campo, cámara | NOR +2, DOC +1 |
| Topografía | Geomensor/a (`cartographer`) | Explorador de Poligonales | Chaqueta de geomensor, jalón con prisma, curvas de nivel | CAP +2, ANA +1 |
| Topografía | Especialista GIS (`gis`) | Cartomante de Capas | Sweater, tablet, mapa SIG | ANA +2, DOC +1 |
| Mecánica | Ingeniero/a Mecánico/a (`artificer`) | Artífice de Engranajes | Overol, llave inglesa, engranajes | MOD +2, ANA +1 |
| Captura y RPA | Piloto RPA (`pilot`) | Piloto de Nubes | Chaqueta de vuelo, visor FPV, control de dron, HUD | CAP +2, NOR +1 |
| Captura y RPA | Especialista en Escaneo 3D (`scanner`) | Domador de Láser | Chaqueta, escáner láser, nube de puntos | CAP +2, MOD +1 |
| Transversal | Líder de Levantamiento Digital (`lev_lead`) | Gran Maestre del Levantamiento | Chaleco de campo, credencial, tablet, nube de puntos | CAP +2, COL +1 |
| Transversal | Coordinador/a BIM (`bim_coord`) | Director de la Orquesta BIM | Polo, tablilla, isométrico BIM | COL +2, NOR +1 |
| Transversal | Prevencionista HSE (`hse`) | Guardián de la Faena | Chaleco HSE, gorra de seguridad, franja de seguridad | NOR +2, COL +1 |

Los bonos se suman a los atributos de la hoja (tope 20). Al cambiar de carrera sin tocar la ropa, el avatar se viste con el
look de la nueva; lo elegido a mano manda. «Sorpréndeme» arma una combinación al azar con las listas y paletas de la carrera
(la ropa siempre se distingue del fondo) y nunca usa piezas bloqueadas.

### Piezas del avatar

17 ropas (con la de cada oficio), 13 gorros (cascos, gorras de seguridad, legionario, boina…), 9 lentes (seguridad y visor
FPV incluidos), 17 peinados, 8 vellos faciales, 13 herramientas en la mano, 4 pines de solapa, 18 fondos (10 con dibujo por
disciplina) y 5 marcos. Desbloqueos por insignia: casco de obra, gafas de piloto y marcos raro, épico y legendario. Desbloqueos
por nivel: marco de bronce NV 3, pin de casquito NV 5 y pin de teodolito dorado NV 10.

## Títulos

Se desbloquean por nivel. La persona elige cuál mostrar entre los que ya desbloqueó.

| Nivel | Título general | Variante por clase (ejemplos) |
|---|---|---|
| 1 | Aprendiz de Cota | — |
| 3 | Dibujante de Grilla | Cartógrafo: *Portador del Jalón* |
| 5 | Modelador de Familias | Calculista: *Guardián del Eje* |
| 7 | Topógrafo Arcano | Piloto: *Domador de Hélices* |
| 10 | Maestro de Nubes de Puntos | Artífice: *Señor del Despiece* |
| 13 | Arquitecto del Gemelo Digital | Arquitecto: *Tejedor de Láminas* |
| 16 | Archimago BIM | Calculista: *Archicalculista* |
| 20 | Leyenda LEV 101 | — |

Hay además títulos especiales, que no dependen del nivel:
- **Primera Luz:** primera misión de la academia.
- **Cerrador de Poligonales:** completó una campaña del mundo *survey*.
- **Constructor de Puentes:** levantó todos los pilares de la Ruta Bentley.
- **Sabio del Foro:** 10 respuestas aceptadas.

## Insignias

Hay cuatro rarezas, con su color: **común** (gris), **rara** (azul), **épica** (violeta) y **legendaria** (dorada, con brillo animado desactivable).

| Familia | Ejemplos |
|---|---|
| Primeros pasos | *Primera Luz* (1.ª misión), *Primer Trofeo*, *Hoja Completa* (perfil completo) |
| Por vendor | *Iniciado Autodesk*, *Tríada Autodesk* (3 trofeos Autodesk), *Primer Trofeo Bentley*, *Reliquia Bentley* |
| Por campaña | *Cota 0 a Certificación* (Forma + Revit 100 %), *Constructor de Puentes* (Bentley) |
| Cruzadas | *Explorador Multi-vendor* (trofeos de 3 vendors), *Políglota BIM* (Revit + OpenBuildings) |
| Comunidad | *Primera Nube* (1.ª nota), *Sabio del Foro*, *Mentor* (5 respuestas aceptadas a otras personas) |
| Constancia | *Racha de 4*, *Racha de 12* |
| Especiales | *Alas DGAC* (habilitación RPA vigente), *Gremio Unido* (expedición del equipo completada) |

Cada insignia es un sprite SVG de 16×16 o 32×32 (skill `sprite-8bit`) con una regla declarativa en `seed/insignias.json`. Tipos de regla:
- `count`: contar eventos de un tipo con filtros;
- `path_complete`;
- `distinct_vendors`;
- `streak`;
- `credential_kind`;
- `manual`: el moderador la otorga.

## Atributos de la hoja de personaje

Hay seis atributos, como las estadísticas de D&D. Cada uno se calcula de 0 a 20 a partir de las **habilidades** (`Skill`) de las credenciales verificadas y de las campañas completadas:

| Atributo | Habilidades que lo suben |
|---|---|
| **MOD** · Modelado | modelado-bim, familias, corredores-viales, modelado-mecánico |
| **CAP** · Captura | nubes-de-puntos, fotogrametría, gnss, lidar, vuelo-rpa |
| **ANA** · Análisis | análisis-ambiental, cálculo-estructural, hidráulica, earthwork |
| **DOC** · Documentación | láminas, anotación, planos-perfil, entregables |
| **NOR** · Normativa | normativa-dgac, estándares-bim, iso-19650 |
| **COL** · Colaboración | cde, coordinación, más las respuestas aceptadas en el foro |

Fórmula del MVP: `min(20, 2 × credenciales verificadas con esa habilidad + campañas completas que la declaran + 1 cada 3 respuestas aceptadas, este último solo para COL)`.

## Hoja de personaje (perfil)

Concepto navegable: `design/perfil/hoja-personaje.html`.

- **Vistas:** cada persona elige con cuál se abre su hoja (juego, compacta o profesional) en «Editar mi hoja».
- **Vista profesional:** foto o avatar, nombre, titular, disciplina, bio, enlaces (LinkedIn, Credly), credenciales verificadas y matriz de habilidades. Es sobria y quedará lista para exportarse como PDF de competencias.
- **Vista de juego:**
  - avatar 8-bit por capas (clase, tono, color, accesorio desbloqueado);
  - clase, nivel en Press Start 2P, barra de XP y título;
  - atributos en hexágono;
  - vitrina de insignias, árbol de habilidades por vendor y línea de tiempo de logros.
- **Edición:** solo la persona edita su hoja; el moderador solo puede ocultar contenido inapropiado.

## Desbloqueables

Lo que se gana se tiene que ver:
- **Accesorios del avatar:**
  - *Primer Trofeo*: casco de obra;
  - *Alas DGAC*: gafas de piloto;
  - nivel 10: capa con el patrón del mundo favorito.
- **Marcos del avatar** según la rareza de la mejor insignia.
- **Decoraciones del mundo:** al completar una campaña, el edificio se ilumina, el puente se inaugura o la poligonal se cierra.
- **Frases de Teo** nuevas y personalizadas al subir de nivel.

## Gremio (vista de equipo)

- **Tablón del gremio**, que se renueva cada semana: logros de la semana (quién ganó qué), misiones más hechas y trofeos nuevos. No hay ranking individual permanente (D17).
- **Expedición del equipo:** una meta compartida mensual que el moderador define; por ejemplo, "6 trofeos Bentley entre todos". Tiene barra común y se premia con la insignia *Gremio Unido* para quienes aportaron.
- **Misión sugerida:** en la portada, cada persona ve su próxima misión según su avance ("Te falta 1 curso para la Reliquia Bentley Road Modeler").

## Celebraciones

- **Al subir de nivel:** modal 8-bit con Teo, el nuevo título y un sonido corto. El sonido está apagado por defecto y la animación respeta `prefers-reduced-motion`.
- **Al ganar una insignia:** *toast* con el sprite y una notificación en la campana (`notifications`).
