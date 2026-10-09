# Decisiones

## Tomadas

| # | Decisión | Motivo |
|---|---|---|
| D1 | Django monolito modular + HTMX + SQLite, gestionado con `uv` | Mismo patrón que otros proyectos del equipo; admin gratis; una VM basta |
| D2 | Identidad desde Tailscale (`tailscale serve`), sin login propio | Acceso solo por la tailnet; nada de contraseñas que administrar |
| D3 | Todos ven el avance y las notas de todos | Definido por el equipo: saber a quién preguntar y compartir lo que funciona |
| D4 | Archivos de certificados privados: solo dueño, leads y admin los descargan; el resto ve el listado | Contienen datos personales |
| D5 | Comandos y términos de software en inglés en la interfaz | Coinciden con la pantalla y con los cursos oficiales |
| D6 | Carga manual de credenciales | Las integraciones con plataformas varían y no son necesarias para validar el uso |
| D7 | Las `key` de hitos y preguntas son estables y solo se agregan al final | Para no romper avances guardados ni la migración del prototipo |
| D8 | 4 disciplinas base y 7 módulos según `VISION.md` | Imagen de referencia definida por el equipo |
| D9 | Marca: **AeroAcademy** (repositorio y plataforma) → **Academia LEV Digital 101** (la academia interior). **CC 410** es el código de programa de la Ruta Forma + Revit, no el nombre del producto. Cierra A4 | Definido por el dueño del proyecto |
| D10 | Un solo lead y moderador general: el dueño del proyecto (primer login en `BOOTSTRAP_ADMINS`). Configurable en el admin. Cierra A1 | Equipo pequeño; se puede abrir por disciplina más adelante |
| D11 | Alta de usuarios = Tailscale + **aprobación manual** (`Person.status = pending` hasta aprobar) | El moderador decide quién entra aunque esté en la tailnet |
| D12 | Bot **Teo** sobre **NVIDIA NIM** (`integrate.api.nvidia.com`, compatible con OpenAI). Solo se envía contenido público del catálogo, rutas, foro y artículos más la pregunta. **Nunca** credenciales, archivos, correos ni datos personales | Gratis para empezar; la regla de datos mantiene lo privado dentro de la red |
| D13 | El XP grande (trofeos, reliquias, habilitaciones) solo se otorga con credenciales **verificadas** por un lead. Las misiones y el quiz dan poco XP | Antitrampa: el certificado es la prueba |
| D14 | Hay dos tipos de ruta: `structured` (niveles, hitos y quiz propios; ej. Forma + Revit) y `external_track` (lista de cursos de un sitio externo que entrega certificado; ej. Bentley Learn) | Autodesk se arma internamente; Bentley ya tiene su ruta y certificado |
| D15 | Cada ruta pertenece a un **mundo** visual (`architecture`, `civil`, `survey`, `mechanical`, `aero`) con metáfora propia. La capa de juego es común a todos | Originalidad por especialidad, coherencia por el juego (`MUNDOS.md`) |
| D16 | Dependencia nueva permitida: `httpx`, solo en la app `assistant` | Cliente HTTP con *timeout* y pruebas simples (`httpx.MockTransport`) para la API de NIM |
| D17 | Ranking: **tablón del gremio** (logros del equipo y de la semana), no una tabla individual permanente | Equipo pequeño: motivar sin competir de forma tóxica |
| D18 | Tipografía de juego *Press Start 2P* (OFL, local) solo en niveles, insignias y títulos; el resto en Archivo | Toque 8-bit sin perder lectura profesional |
| D19 | Repositorio público `DovaCrii/AeroAcademy`. **El agente construye, sube y deja el PR listo; la persona revisa y fusiona.** Un PR por bloque, apilados (`docs/FLUJO_GITHUB.md`) | Seguimiento por bloque y control humano sobre `main` |
| D20 | Licencia MIT, como el resto de la Suite Aero | Consistencia con AeroControl, AeroBim y AeroConvert |
| D21 | La academia lleva un mensaje de auspicio de **Suite Aero** (bienvenida y pie). Los repositorios privados (AeroPlanner, AeroLink) se nombran pero no se enlazan | Dar a conocer el software propio sin exponer repos privados |
| D22 | Se separó la portada: **12a Bienvenida** se entrega con el Bloque 2; **12b** (XP, misión sugerida, Teo, tablón) espera a los bloques 13, 15 y 16 | La persona pidió una ventana de inicio desde el principio |

| D23 | Mientras no se agregue `htmx.min.js`, la actualización parcial la hace un ayudante propio (`core/static/core/enhance.js`, ~60 líneas, mismo contrato `X-Partial`). Sin JS todo funciona con formularios normales | Evitar una descarga externa sin permiso y una dependencia nueva; se puede cambiar a HTMX sin tocar las vistas |

| D24 | Avatares **32×32** con motor propio sin dependencias (`apps/gamification/avatar/`), editables por la persona (cuerpo hombre/mujer/neutro, piel, cara, pelo, barba, lentes, gorro, ropa, colores, fondo y marco). Se descartó DiceBear (build de Node) y el generador LPC (licencias mixtas) | Más variedad y detalle que 16×16, sin dependencias ni datos a terceros |
| D25 | Se trabaja con **subagentes del proyecto** (`.claude/agents/`) alineados con las skills; cada uno edita solo lo asignado y quien lo lanza verifica antes de integrar | Paralelizar arte, semillas y bloques independientes sin pisarse |
| D26 | Un responsable **no revisa sus propias credenciales**; el administrador sí (el equipo puede ser de una persona). La revisión lleva una huella de versión: si la credencial cambió mientras se revisaba, se rechaza | Evita el autoaval y la carrera entre editar y verificar |
| D27 | Una credencial verificada que **vence** sigue contando para el avance y se muestra con una marca de vencida | El curso se hizo; la vigencia es información, no borra el progreso |
| D28 | Motor de juego en `apps/gamification/game.py` + `rules.py`: el XP se **reconcilia** (`sync_*`) con lo que debe existir, no se acumula a ciegas; se llama desde `progress` y `credentials` sin signals. Las insignias se recalculan y se quitan si la condición deja de cumplirse, salvo `manual` y las de racha (cuentan la mejor racha histórica). La racha da 20 × semanas seguidas (máx. 100) por semana con actividad | Marcar/desmarcar, verificar/rechazar y repetir no duplican ni dejan XP de más |
| D29 | Ocultar contenido exige motivo, no borra, avisa a la autora o al autor y queda en la bitácora; los miembros no ven lo oculto y los responsables sí. Un aviso (`Notification`) lleva `key` y no se repite | Moderar sin perder evidencia, y que reintentar una acción no inunde la campana |
| D30 | El contexto de Teo sale solo de una lista blanca (`assistant/context.py` + `search.py`) y el log de Teo no tiene campos para texto; la respuesta del modelo se muestra escapada, sin Markdown ni enlaces propios | Que ni un error de código pueda mandar datos de credenciales al proveedor, ni el modelo pueda inyectar enlaces |
| D31 | «Solo yo y los responsables» oculta el **título, el archivo y los datos** de una credencial; el XP, el nivel y las **insignias** que genera son públicos (como un Credly). Los porcentajes de avance y las listas del equipo sí respetan la visibilidad. Una credencial verificada solo cambia de visibilidad sin nueva revisión: cualquier otro campo la devuelve a *en revisión* | Decisión explícita tras la revisión: el juego es social, pero lo que se verificó no se cambia a escondidas |
| D32 | La mascota y asistente pasa a ser **Nala**, una cachorrita golden retriever (la perrita del dueño del proyecto). Cambia todo lo visible (sprites, textos, prompt); el código conserva los nombres `teo` (URLs `/teo/`, comandos `teo_probar` y `teo_seguimiento`, archivos `game/teo/*.svg`) para no romper enlaces ni tareas programadas | Decisión de la persona (2026-10-09); renombrar el código no aporta y rompe cosas |
| D33 | **XP por curso visible:** cada curso que entrega certificado muestra «+N XP» (100 curso, 500 examen o reliquia) y enlaza a subir su certificado ya vinculado (`?recurso=`). El XP sigue llegando solo al verificarse (D13). Lo **esencial** de una ruta se marca con la etiqueta `Esencial` en la semilla y va primero en el catálogo | «Vincular los puntos»: que se vea qué vale cada curso sin abrir otra vía de XP sin verificar |

## Abiertas (no resolver sin confirmar)

| # | Pregunta | Propuesta por defecto |
|---|---|---|
| A2 | ¿Las credenciales `private` cuentan en la matriz de competencias y en el XP? | No en la matriz; sí en el XP personal (sin mostrar detalle) |
| A3 | ¿Cuántos días de aviso para vencimientos? | 60 días |
| A5 | ¿Se guardan los ZIP exportados como registro de lo entregado a cada licitación? | No en el MVP (se borran a las 24 h) |
| A6 | Nombre definitivo del bot | **Teo** (alternativas: Nivo, Pixi) |
| A7 | Modelo NIM por defecto | Uno *instruct* gratuito de la familia Llama o Nemotron; se fija en `NIM_MODEL` tras probar calidad en español |
| A8 | ¿Se muestra el XP de otros en su perfil o solo nivel y título? | Nivel, título e insignias visibles; XP exacto solo para el dueño |
| A10 | Falta `PressStart2P.woff2` (fuente OFL de Google Fonts) para niveles, insignias y títulos. No se descargó por cuenta propia | Agregar el archivo y su licencia a `apps/core/static/core/fonts/` y descomentar el `@font-face` de `tokens.css` |
| A11 | ¿Se agrega `htmx.min.js` (BSD, ~50 KB) a `core/static/` y se reemplaza `enhance.js`? | Sí, cuando la persona autorice descargar el archivo; hoy `enhance.js` cubre el uso |
| A9 | ¿Una acreditación Bentley completa (learning plan) es *Reliquia* (500 XP) o *Trofeo mayor* (250 XP)? | Reliquia: incluye una evaluación (*Assessment*) o la entrega de un proyecto |
