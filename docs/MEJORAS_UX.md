# Mejoras de UX tras la primera semana en producción

Plan de la ronda `mejoras-ux` (2026-10-13). Lo escribe el agente de diseño y revisión (Opus), lo implementa un agente
Sonnet y lo verifica un agente Haiku. Sale de lo que reportó el dueño al usar producción (capturas 23 a 34 de la sesión)
y de una auditoría del código en `origin/main` (`9c49c11`).

Restricciones de toda la ronda:

- Estilo *doodle*, papel claro, con modo oscuro.
- Sin framework JS: todo funciona sin JS (D23).
- Las *keys* y los *slugs* son estables.
- Se cumplen las reglas de privacidad de `AGENTS.md`.
- Producción vive en la tailnet, con la identidad de Tailscale, más la puerta pública D36.

Prioridades:

- **P0:** enlaces rotos y claridad de cuentas y entrada.
- **P1:** cómo tomar cursos, flujo, foro, cabecera, rutas, catálogo, avatar y figuras temáticas.
- **P2:** el resto.

Cada prioridad sale en uno o varios PR.

---

## a) Hallazgos

### a.1 «Al clickear llega a Not Found»: resultado del recorrido

Se recorrió el sitio de cuatro maneras:

| Recorrido | Cómo | Páginas | No-200 |
|---|---|---|---|
| Local, admin | `client.get` en una BD de prueba con `seed_catalog` + `cargar_dgac` (fixture) + un hilo por categoría; se siguen todos los `href` internos, se conservan los `?query` en redirecciones y se canonicaliza `/catalogo/` (máx. 1 filtro) | 1322 | **0** |
| Local, miembro | igual | 1317 | **0** |
| Local, pendiente | igual (solo ve `/espera/`) | 5 | **0** |
| Local, miembro sin datos DGAC (`DGAC_DATA_DIR` inexistente) | igual | 1315 | **0** |
| Local, formularios POST (admin y miembro) | se envía cada `<form method=post>` distinto (93 y 84) y se sigue su redirección | 177 | **0** (solo 400 esperados en `/rutas/<slug>/meta/` por datos falsos) |
| **Producción**, GET de solo lectura | `https://aeroacademy.tailccd107.ts.net` con la identidad de este equipo; incluye `href` y `src` y `/static/` | 1499 | **0** |
| URLs externas de `seed/` | GET con *user-agent* de navegador | 350 | 95 «malas»: 93 son **403 de Autodesk** (antibots: hay que confirmarlas en un navegador), 1 **500 de planbim.cl** (`bim-101.json`), 1 *timeout* de usgs.gov (`topografia-101.json`). **Ningún 404** |

**Conteo de 404 internos encontrados: 0.** Con el código actual y los datos de producción, ningún enlace interno
alcanzable da «Not Found». Lo que el dueño vio sale probablemente de una de estas fuentes, que el recorrido **no** cubre:

| # | Fuente probable | Evidencia | Qué hacer |
|---|---|---|---|
| H1 | **Recursos externos** del catálogo y de las rutas: la página del fabricante no existe o cambió. La tarjeta abre una pestaña nueva y el «Not Found» es del sitio externo | 93 URLs de Autodesk no se pueden validar sin navegador; `planbim.cl` responde 500. La captura 24 (NOAA) muestra una página externa | P0-1: el verificador Haiku las abre en un navegador y lista las 404 reales. En la tarjeta se marca con ↗ que el enlace sale del sitio |
| H2 | Despliegue anterior: el dueño navegó antes del último `git pull` (PR #40 a #46 cambiaron rutas, foro y portada) | El crawl de producción se hizo con el código ya desplegado | Reproducir con el dueño. Si vuelve a pasar, el registro de 404 (P0-1) dice qué URL fue y desde dónde |
| H3 | **URL escrita o guardada a mano** (marcadores, enlaces copiados del chat, `/rutas/<slug>` de una ruta retirada o sin publicar) | El 404 de Django por defecto dice literalmente «Not Found» porque **no existe `templates/404.html`** | P0-1: página 404 propia con «Volver», buscador y enlaces a Rutas y Catálogo |
| H4 | «No encuentro la sección», no un 404: **«Equipo» queda oculto** en la barra principal | Capturas 23, 25, 28 y 33: con 1874 px solo se ven Inicio·Rutas·Catálogo·Certificados·Foro·Más. `.nav-main` tiene `overflow-x:auto` con máscara (`base.css` l.42-49) y «Equipo» queda cortado | P1-5 (cabecera) |

**Por qué `tests/test_enlaces.py` no avisa y no avisaría:**

1. `LIMIT = 400`: el recorrido se corta mucho antes de cubrir el sitio. Solo `/catalogo/` genera más de 4800 combinaciones
   de filtros (`?cert=&kind=&ruta=&page=`), así que BFS gasta el presupuesto en el catálogo y nunca llega a todas las
   páginas `?nivel=&paso=` ni a las notas.
2. Al seguir una redirección se queda con `urlparse(target).path` y **pierde el `?query`**. Por eso
   `respond()` → `/rutas/<slug>/?nivel=..&paso=..` nunca se prueba con sus parámetros.
3. Solo siembra `seed_catalog`: no hay ruta DGAC (`cargar_dgac`), hilos, notas, diplomas ni personas pendientes. No hay
   recorrido como `pending` ni como `lead`.
4. Solo sigue `href="…"` con comillas dobles. No mira `src` ni `/static/`, y **no envía formularios POST**.
5. No mira URLs externas (a propósito: el CI no debe depender de internet), y tampoco hay un comando que lo haga a pedido.

### a.2 Otros hallazgos (auditoría de código y capturas)

| Área | Hallazgo | Dónde |
|---|---|---|
| Cabecera | Grid de 6 columnas con marca, 6 enlaces, «Más», nivel, campana, chip y tema. Bajo 1239 px el menú baja a una segunda fila. A 1874 px «Equipo» se corta por el scroll horizontal | `apps/core/templates/core/base.html` l.28-56; `apps/core/static/core/base.css` l.31, 42-57, 116-149; `brand.css` |
| Cabecera duplicada | La portada repite debajo una **cinta** (`nav.w-strip`, «Accesos rápidos»: Rutas, Catálogo, Certificaciones, DGAC, Foro, Equipo, Mi avance, Ayuda) y luego un **tercer** navegador `nav.w-jump` («En esta página») | `core/home.html` l.11-22 y l.66-68; `core/welcome.css` l.234-238, 347-349, 495-499 |
| Anónimos | `accounts/_public.html` no tiene botón «Entrar» en la cabecera. No hay texto «¿Cómo obtengo mi cuenta?». En la puerta pública, el pie dice «Solo dentro de la red del equipo (Tailscale)» | `accounts/_public.html` l.24-35, 46; `welcome.html` l.9-12; `login.html` l.11-14 |
| Sesión | «Salir» es solo un ícono ⏻. No hay cambio de contraseña, recuperación propia ni página «Mi cuenta». Nada enlaza a `/seguridad/2fa/` | `core/base.html` l.47; `accounts/urls.py` |
| Espera | `/espera/` no dice a quién avisar, no tiene «Salir» y supone que se entró por Tailscale | `accounts/waiting.html` |
| D35 | `team_signup_result.html` responde distinto si el correo ya tiene cuenta (`has_account`) o es lead o admin (`personal_link`): **permite enumerar cuentas** con el enlace del equipo | `accounts/team_link.py`, `team_signup_result.html` |
| Admin | En Equipo → Personas no hay paso a paso. El botón «Copiar enlace de registro» en realidad **genera** uno nuevo. `docs/OPERACION.md` no explica cómo dar de alta. `PRODUCCION.md` l.133 habla de un 401 que ya no existe | `team/people.html` l.16, 43, 51; `docs/OPERACION.md` |
| Entrada a los cursos | Ninguna tarjeta de ruta tiene un botón «Empezar» o «Continuar», salvo `gen-pct` del catálogo general. La portada del mundo no tiene llamada a la acción: la ruta se abre en el primer nivel pendiente sin decirlo | `core/partials/route_rows.html`, `paths/index.html` l.44-58, `worlds/*/cover.html`, `worlds/*/_app.html` |
| Iconos | Los 22 slugs de `seed/rutas` tienen icono único. **`dgac-rpas` no tiene** (`route_icon` devuelve `""` y la prueba solo recorre `seed/rutas`). Las tarjetas del foro («Notas de las rutas») no muestran icono. El catálogo general usa un *doodle* en vez del icono | `apps/catalog/software.py` l.143-157; `tests/test_software_guides.py` l.336-348; `community/forum_index.html` l.61 |
| Dron DGAC | El dron va en `translate(x, y-30)` y la etiqueta del waypoint par (`above`) en `y-32`. En D0 (y=262) «Roles» y el dron quedan a 2 px, **uno encima del otro**. Pasa en todo waypoint par que sea el actual | `worlds/aero/journey.html` l.20-33; `apps/progress/services.py::_waypoints` l.169-208 |
| Civil | El marcador «TÚ» se dibuja encima de la estaca del último curso verificado. Las estacas muestran la *key* cruda (`itw-c0`, `rea-c1`) en vez de un nombre corto | `worlds/civil/journey.html`; `apps/progress/external.py::_journey` l.119-169 |
| Figuras | 12 rutas *structured* sin mundo propio caen en **arquitectura**: «COTA ±0,00», cotas +3,50… (`_floors` l.152), «Escala», «Lámina X-101», «Dibujo y modelado». iTwin, ProjectWise, LumenRT, OpenPlant y OpenBuildings usan «Planta y perfil · estacas · pilares del puente» | `worlds/architecture/journey.html` l.1-3, 27; `*/_app.html`; `catalog_extras.py::FLAVOURS` l.58-124; `progress/views.py::resolve_world` l.32-55 |
| Avatar | Lienzo 32×32 + marco = 36 u. Se muestra a 128, 96, 64, 32 y 24 px: **ningún múltiplo entero**. El chip de cabecera es un busto de 32 px recortado en círculo de 38 px. Los 18 fondos son oscuros y el contorno es `#0A0E13`, así que la silueta se pierde. El editor es una página con 23 grupos y ~209 opciones y renderiza ~170 SVG por GET. Nivel, XP y título se repiten en cabecera, hoja y portada. Los bonos de carrera salen 3 veces | `apps/gamification/avatar/engine.py` l.344-385; `services.py` l.203; `sheet.css` l.7; `avatar_editor.html`; `sheet.html` |
| Foro | 6 categorías: `general`, `autodesk`, `bentley`, `topografia-captura`, `mecanica`, `ideas-mejoras` (esta es `opinions.POLL_CATEGORY`). Faltan Implementación, Seguimiento y Propuestas. Ya existe `knowledge.Improvement` (Idea → Plan → Ejecución → Resultado, en `/conocimiento/mejoras/`) | `seed/foro.json`; `apps/community/opinions.py` l.19; `apps/knowledge/models.py` l.43 |
| Catálogo | La fila «Ruta» tiene 23 píldoras en 5 filas. Suma 9 pestañas de tipo y 3 interruptores (captura 31). Los recursos de rutas internas dicen «CAPACITACIÓN INTERNA» aunque sean de NOAA, ISO o buildingSMART (captura 27). El título enlaza afuera sin marcarlo | `catalog/resources.html` l.46-50; `catalog/partials/card.html` |
| /rutas/ | Pestañas por **empresa** (Autodesk, Bentley, DJI, Microsoft, AeroAcademy, Anthropic, Kaggle, Open source). IA y Datos, Topografía, BIM y DGAC quedan repartidos. No hay «Empieza aquí» ni «Mis rutas» | `apps/paths/services.py::path_listing`; `paths/index.html` |
| Portada | El flujo cuesta (captura 33). Civil 3D aparece como tarjeta completa en Arquitectura, Civil y Topografía. El *doodle* del héroe (ampolleta y dron) pisa los círculos de disciplina de la derecha | `core/home.html`, `core/partials/route_rows.html`, `core/welcome.css` |
| Profundidad | Tarjetas, barra de filtros y cinta son azul sobre azul en oscuro: no hay capas | `core/tokens.css`, `components.css`, `welcome.css` |

---

## b) Cambios priorizados

Formato de cada cambio: **Meta · Archivos · Enfoque · Aceptación · Pruebas**.

### P0-1 · Enlaces: auditoría que sí detecta, página 404 útil y externos revisables

- **Meta.** Ningún enlace interno rompe sin que el CI avise. Si alguien llega a un 404, sabe volver. Los externos rotos
  quedan listados.
- **Archivos.**
  - `tests/test_enlaces.py` (reescribir).
  - `tests/conftest.py` (fixture `site_world`).
  - `apps/core/templates/404.html` (nuevo) y `apps/core/templates/403.html` si falta.
  - `apps/core/views.py` (handler).
  - `config/urls.py` (`handler404`).
  - `apps/core/management/commands/revisar_enlaces.py` (nuevo).
  - `apps/catalog/templates/catalog/partials/card.html`.
  - `seed/rutas/bim-101.json` (planbim) si el dueño lo confirma.
- **Enfoque.**
  1. **Recorrido de prueba.** Fixture que siembra `seed_catalog`, `cargar_dgac` con `tests/fixtures/dgac`, un hilo por
     categoría, una nota por ruta y un lead. El recorrido conserva la *query* en redirecciones y canonicaliza
     `/catalogo/` (máx. 1 parámetro, sin `page`). Sin límite artificial (tope 3000). Sigue `href` y `src` con comillas
     simples o dobles. Parametrizado: admin, lead, miembro y pendiente. Una segunda prueba envía un POST por cada
     formulario distinto (sin los destructivos) y sigue la redirección. El script de referencia está en
     el scratchpad de la sesión (`test_zz_crawl_tmp.py`): copiar su lógica.
  2. **Página 404 propia** en el estilo *doodle*:
     - texto: «Esta página no existe o ya no está disponible»;
     - botones: Volver, Inicio, Rutas, Catálogo y Buscar (form GET a `assistant:help_index`);
     - no revela si el recurso existe (mismo texto para «oculto» y «no existe»).
  3. **Registro del 404:** `logger.info("404 %s ref=%s", path, referer_path)`. Solo la ruta (sin *query* ni host externo)
     y solo para usuarios autenticados. Nada de correos.
  4. **`manage.py revisar_enlaces [--externos]`:** lista los enlaces internos rotos y, con `--externos`, hace GET a las
     URLs de `Resource.url` y de `seed/`. Escribe un CSV en `private/` y no lo corre el CI.
  5. **Tarjeta del catálogo:** ícono ↗ y `aria-label="… (abre el sitio de <plataforma>)"` en los enlaces externos.
- **Aceptación.**
  - El recorrido cubre más de 1000 URLs por rol en menos de 3 min y falla con la lista `código URL ← origen`.
  - Una URL inventada (`/rutas/no-existe/`) muestra la 404 propia con los 5 accesos.
  - `revisar_enlaces --externos` termina y separa 404 de 403 o *timeout*.
- **Pruebas.** `test_no_internal_link_is_broken[admin|lead|member|pending]`, `test_post_forms_do_not_404[admin|member]`,
  `test_404_page_is_helpful_and_does_not_leak`, `test_404_is_logged_without_query`.

### P0-2 · Cuentas: cómo se entra y cómo se da de alta

- **Meta.** Un visitante sabe cómo entrar y cómo conseguir cuenta. Quien tiene sesión ve «Mi cuenta» y «Salir». La
  administradora tiene en pantalla los pasos para invitar gente.
- **Archivos.**
  - `apps/accounts/templates/accounts/_public.html`, `welcome.html`, `login.html`, `waiting.html`,
    `team_signup_result.html`, `account.html` (nuevo), `password_change.html` (nuevo).
  - `apps/accounts/views.py`, `urls.py` (`cuenta/` → `accounts:account`, `cuenta/contrasena/` → `accounts:password_change`).
  - `apps/accounts/services.py`, `team_link.py`.
  - `apps/core/templates/core/base.html` (menú de usuario).
  - `apps/team/templates/team/people.html`.
  - `docs/OPERACION.md` (sección nueva), `docs/PRODUCCION.md` (l.92, 97, 133, 173).
- **Enfoque.**
  1. **Cabecera pública:** botón **«Entrar»** a `accounts:login` y enlace **«¿Cómo obtengo mi cuenta?»** a
     `accounts:welcome#cuenta`.
  2. **Bloque `#cuenta` en la bienvenida**, según la puerta (`request.public_door`):
     - «Las cuentas se crean por invitación: el administrador te manda un **enlace personal** (dura 7 días, un uso) o el
       **enlace del equipo**. Si usas Tailscale con tu correo del equipo, abre el sitio y listo: no necesitas contraseña.»
     - En la puerta pública no se muestra la frase de Tailscale ni el pie «Solo dentro de la red del equipo».
  3. **Con sesión.** El chip de usuario pasa a `<details class="usermenu">` con:
     - Mi hoja (`gamification:my_sheet`);
     - Mi avatar;
     - Mi cuenta (`accounts:account`), que muestra login, puerta, rol, 2FA (enlace a `accounts:two_factor` solo en la tailnet) y cambio de contraseña solo si la sesión es por contraseña;
     - **Salir** con texto (POST), solo si `password_session`.
     Sin JS es un `details`.
  4. **Cambio de contraseña** con `PasswordChangeForm` de Django, POST con CSRF y `update_session_auth_hash`. No hay
     recuperación por correo (no hay correo): el texto dice «¿Olvidaste tu contraseña? Pide un enlace nuevo al
     administrador».
  5. **`/espera/`:**
     - texto según cómo se entró;
     - «Te avisamos en la campana cuando te aprueben. Si pasa más de un día, escríbele al administrador del equipo»;
     - botón «Salir» si la sesión es por contraseña.
  6. **D35 sin enumeración.** Para `has_account`, `personal_link` y `refused`, una **sola respuesta** con el mismo texto
     y código: «Si el correo es válido, ya quedó registrado o un administrador te contactará. Si ya tienes cuenta, entra
     con tu contraseña». La rama `pending` se queda igual porque es el caso nuevo. Los avisos internos a leads no cambian.
  7. **Equipo → Personas:** caja «Cómo dar de alta» con 4 pasos numerados:
     1. Agrega el correo o apruébalo.
     2. Genera el enlace personal o el del equipo.
     3. Mándalo por un canal privado.
     4. La persona crea su contraseña o entra por Tailscale.
     Se cambia el texto del botón a «Generar enlace de registro» y se corrige «Solo funciona dentro de la tailnet» según
     la puerta.
  8. **`docs/OPERACION.md` «Cómo dar de alta cuentas»:**
     - `sudo aeroacademy aprobar <correo> [--rol member|lead|admin]`;
     - `sudo aeroacademy enlace_registro <correo>`;
     - `sudo aeroacademy enlace_equipo --dias 14` y `--revocar`;
     - `importar_equipo equipo.csv --dry-run`;
     - qué pasa si el enlace vence (400 con «Este enlace ya no sirve…»: se genera otro).
     Se corrigen las líneas viejas de `PRODUCCION.md`.
  9. **Bitácora:** los comandos `aprobar`, `enlace_registro` y `enlace_equipo` registran en `moderation.log` como la UI
     (sin el secreto).
- **Aceptación.**
  - Un anónimo ve «Entrar» y «¿Cómo obtengo mi cuenta?» en las dos puertas.
  - Con sesión por contraseña hay «Salir» con texto y se puede cambiar la contraseña.
  - Con sesión Tailscale no hay «Salir» ni cambio de contraseña.
  - D35 da la misma respuesta y el mismo código para correo existente, lead o rechazado.
  - Todo `next` sigue validado.
  - Nada sensible en los logs.
- **Pruebas.**
  - `test_public_header_has_login_and_how_to_get_account[tailnet|public]`;
  - `test_public_door_hides_tailscale_copy`;
  - `test_password_change_requires_old_password_and_csrf`;
  - `test_tailscale_session_has_no_password_change`;
  - `test_team_signup_same_response_for_existing_and_lead`;
  - `test_waiting_page_has_logout_for_password_session`;
  - `test_commands_log_to_moderation`;
  - `test_next_rejects_evil` (`//evil.com`, `/\evil.com`).

### P1-1 · Cómo tomar un curso: llamadas a la acción y «Cómo funciona»

- **Meta.** En cada tarjeta y en cada ruta hay un solo botón claro: **Empezar la ruta**, **Continuar (N %)** o **Ver
  diploma**.
- **Archivos.**
  - `apps/paths/services.py` (helper `cta_for(person, path)`) y `apps/catalog/templatetags/catalog_extras.py`
    (`{% route_cta path as cta %}`).
  - Partial nuevo `apps/core/templates/core/partials/route_card.html`.
  - `core/partials/route_rows.html`, `paths/index.html`, `catalog/partials/general.html`, `catalog/partials/card.html`,
    `community/forum_index.html`.
  - `worlds/{architecture,civil,aero}/cover.html` y `_app.html`.
  - Partial nuevo `core/partials/how_it_works.html`.
- **Enfoque.**
  1. **`cta_for`** devuelve `{label, url, pct}`:
     - 0 %: «Empezar la ruta →» con URL `paths:detail` + `?nivel=<primer nivel>#panel`;
     - entre 0 y 100: «Continuar · N % →» al primer nivel pendiente (`world_context` ya lo calcula; se extrae a un
       servicio);
     - 100 %: «Ver diploma ✦» (`diplomas.route_link`);
     - *external_track*: «Registrar mi primer curso →».
     Las consultas quedan acotadas: los avances de todas las rutas en 1 o 2 *queries* (`path_percents`).
  2. **Partial `route_card.html` único:** icono, título, empresa, insignias de disciplina, barra de avance y botón CTA.
     Lo usan la portada, `/rutas/`, el catálogo general y el foro.
  3. **«Cómo funciona»** (4 pasos dibujados: Elige ruta → Misiones → Quiz → Avance y diploma), plegable con `<details>`:
     - en `/rutas/` y en la portada de cada mundo;
     - en la portada del mundo, botón grande «Empezar / Continuar» bajo el título.
  4. **Tarjeta de recurso del catálogo:**
     - si pertenece a una ruta, botón «Tomarlo en la ruta <título> →» al nivel donde está;
     - el título enlaza afuera con ↗;
     - la etiqueta de plataforma pasa a decir de quién es el recurso (`resource.platform` / `vendor`) y no
       «CAPACITACIÓN INTERNA» cuando el autor es externo.
  5. **Foro, «Notas de las rutas»:** la tarjeta muestra el icono y dos enlaces: «Ver notas» y «Ir a la ruta».
- **Aceptación.**
  - Cada tarjeta de ruta, en los 4 lugares, tiene icono y exactamente un CTA primario.
  - Sin JS funciona.
  - Desde la portada, cualquier ruta queda a ≤ 2 clics y cualquier nivel a ≤ 3, medido con el recorrido BFS de P0-1
    (profundidad).
- **Pruebas.**
  - `test_cta_states` (0 %, parcial, 100 %, external);
  - `test_route_cards_have_icon_and_cta[home|rutas|catalogo|foro]`;
  - `test_cta_queries_constant`;
  - `test_every_level_within_3_clicks_from_home`.

### P1-2 · Flujo y portada: «Empieza aquí», «Continuar donde quedaste» y sin repeticiones

- **Meta.** Un camino principal obvio, con la próxima acción visible en cada etapa:
  portada → disciplina → ruta → nivel → quiz → diploma, y portada → catálogo → recurso.
- **Archivos.** `apps/core/services.py::home_context`, `core/home.html`, `core/partials/route_rows.html`,
  `core/welcome.css`, `worlds/*/_panel.html`, `catalog/resources.html`, `paths/index.html`.
- **Enfoque.**
  1. **Primer bloque bajo el héroe:**
     - «Continuar donde quedaste» (última ruta tocada, nivel y paso, con CTA);
     - o, si no hay avance, «**Empieza aquí**»: la ruta 101 de su disciplina (BIM 101, Topografía 101, IA 101…).
     Reemplaza «Ver mi misión» y «Explorar rutas» por **un** botón primario y uno secundario.
  2. **Rutas sin repetir:** cada ruta aparece **una vez**, en su disciplina principal (`software.discipline_key`), con
     insignias «también en Arquitectura · Topografía». En la vista de una disciplina se muestran sus rutas propias y una
     línea «También sirven aquí: Civil 3D, …» con enlaces compactos.
  3. **Héroe:** el *doodle* (ampolleta y dron) se reserva en su propia columna (`grid-template-areas`). Los círculos de
     disciplina van debajo, en una rejilla que envuelve. Nada se superpone entre 375 y 1920 px.
  4. **Migas** `Inicio › Rutas › <Disciplina> › <Ruta> › Nivel N` en el detalle de ruta y en las notas. En el panel del
     nivel, «Siguiente: Quiz →» o «Siguiente nivel →» al terminar. Al terminar el último, «Ver diploma».
  5. **Entre catálogo y rutas:** el catálogo muestra arriba «¿Prefieres un camino guiado? Ver rutas». `/rutas/` muestra
     «¿Buscas un recurso suelto? Ir al catálogo».
- **Aceptación.**
  - En la portada de una persona con avance, el primer CTA lleva al nivel pendiente.
  - Ninguna ruta aparece más de una vez como tarjeta completa en la portada.
  - Nada se superpone a 1280 ni a 375 px.
  - Toda ruta queda a ≤ 2 clics de la portada y todo nivel a ≤ 3.
- **Pruebas.** `test_home_continue_block`, `test_home_start_here_101`, `test_home_route_cards_unique`,
  `test_breadcrumbs_on_route_and_notes`, la profundidad BFS de P1-1.

### P1-3 · Foro: Ideas, Implementación, Seguimiento, Propuestas y mejoras, General

- **Meta.** Categorías claras y visibles desde el menú y la portada.
- **Archivos.** `seed/foro.json`, `apps/community/templates/community/forum_index.html`, `core/home.html`,
  `core/base.html` (menú «Foro» o «Más»), `apps/community/opinions.py` (solo si cambia `POLL_CATEGORY`, que **no** debe
  cambiar), `tests/test_forum.py`.
- **Enfoque.** El slug `ideas-mejoras` se mantiene (es `POLL_CATEGORY`) con nombre «Propuestas y mejoras». Se agregan
  **al final** del JSON:
  - `ideas`: «Ideas» (lluvia de ideas sin compromiso);
  - `implementacion`: «Implementación» (cómo lo estamos haciendo: pruebas piloto y configuración);
  - `seguimiento`: «Seguimiento» (estado de lo acordado y de las mejoras en curso; enlaza a `/conocimiento/mejoras/`).
  `general` queda como está. Las 4 de producto (`autodesk`, `bentley`, `topografia-captura`, `mecanica`) siguen.
  En el índice del foro va una franja «Conversaciones del equipo» con 5 tarjetas (General, Ideas, Propuestas y mejoras,
  Implementación, Seguimiento). Cada tarjeta lleva un *doodle*, un conteo y enlaza a `community:forum?categoria=<slug>`.
  En la portada se agrega el bloque «Participa» con los mismos 5 enlaces. El menú «Foro» sigue directo.
  Decisión abierta para DECISIONES: si «Seguimiento» debe unirse a `knowledge.Improvement` (etapas). Por ahora solo se
  enlaza.
- **Aceptación.**
  - `seed_catalog` deja 9 categorías activas, sin borrar ninguna.
  - Las 5 tarjetas se ven en `/foro/` y en la portada.
  - Encuestas y opiniones siguen en `ideas-mejoras`.
- **Pruebas.** `test_forum_seed_has_team_categories`, `test_poll_category_unchanged`, `test_forum_index_team_cards_links`.

### P1-4 · Iconos únicos en todas las tarjetas, DGAC incluida

- **Archivos.** `apps/catalog/software.py` (`ROUTE_ICON["dgac-rpas"]`),
  `apps/core/static/core/img/software/ruta-dgac-rpas.svg` (nuevo: pictograma original de un dron sobre un plan de vuelo
  con waypoints, baldosa con degradado, sin logos), `docs/ICONOS.md`, `tests/test_software_guides.py`.
- **Enfoque.** La prueba de unicidad también mira `apps.dgac.constants.ROUTE_SLUG` y los slugs de `LearningPath` en la
  BD (no solo `seed/rutas`). El partial `route_card.html` (P1-1) usa siempre `route_icon_src`, con el respaldo actual de
  `_path_icon`.
- **Aceptación.** 23 iconos únicos (bytes distintos). Las tarjetas de portada, `/rutas/`, catálogo general y foro
  muestran icono.
- **Pruebas.** Ampliar `test_every_route_has_its_own_unique_icon_file` y `test_route_cards_have_icon_and_cta`.

### P1-5 · Cabecera: menos ruido y sin duplicados

- **Meta.** Una sola navegación, que no se envuelve ni se corta a 1280, 1024, 768 y 375 px, en claro y oscuro.
- **Archivos.** `apps/core/templates/core/base.html`, `core/partials/player.html`, `core/partials/bell.html`,
  `apps/core/static/core/base.css`, `brand.css`, `core/home.html` (quitar `w-strip`), `core/welcome.css`.
- **Enfoque.**
  1. **Grupos:**
     - izquierda: marca compacta (logo + «101»; el texto «Levantamiento Digital» se oculta bajo 1440 px);
     - centro: **5 principales**: Inicio · Rutas · Catálogo · Foro · Equipo;
     - «Más» (≤ 7): Certificados, Documentos, Conocimiento, Gremio, DGAC, Ayuda, Moderación (lead);
     - derecha: campana · avatar con nivel (anillo de XP en el chip, sin barra aparte) · menú de usuario (P0-2) con el
       tema dentro.
     Así salen 2 elementos sueltos (barra de nivel y botón de tema).
     Certificados pasa a «Más» y al menú de usuario («Mis certificados»). Es una decisión de producto: anotarla en
     DECISIONES y confirmarla con el dueño antes de fusionar.
  2. **Sin scroll horizontal:** `.nav-main` deja `overflow-x:auto`. Bajo 1024 px, los principales se esconden en un
     `<details class="nav-burger">` («Menú»), que funciona sin JS.
  3. **Se elimina `nav.w-strip`** de la portada, porque duplica la navegación. «Mi avance» pasa a `w-jump`, que se
     queda solo con anclas de la página. Se renombra «En esta página» y no repite nombres de la cabecera: Tus rutas,
     Tu misión, Tu avance, Módulos, Destacados, Suite Aero.
  4. El *popover* «Más» se alinea al botón y no tapa el nombre (captura 28): `right:auto; left:0` y un ancho máximo.
- **Aceptación.**
  - A 1280, 1024, 768 y 375 px, en claro y oscuro: una sola fila de cabecera (o la hamburguesa), sin cortes, con
    «Equipo» visible o en el menú y sin segunda cinta en la portada.
  - Con teclado: Tab recorre todo y Escape cierra «Más» (con JS).
- **Pruebas.**
  - `test_header_has_five_primary_links_and_more`;
  - `test_home_has_no_duplicate_quicknav` (no existe `.w-strip` y ningún `href` de la cabecera se repite en un `nav` de
    la portada);
  - `test_more_menu_contains_secondary_sections`.

### P1-6 · /rutas/ por área de aprendizaje

- **Archivos.** `apps/paths/services.py::path_listing`, `apps/paths/views.py::index`,
  `apps/paths/templates/paths/index.html`, `components.css`.
- **Enfoque.**
  - Pestañas o anclas por **disciplina**: Transversal, Arquitectura, Civil-Estructural, Topografía, Mecánica,
    Captura·RPA, IA y Datos y DGAC (DGAC como ruta de Captura·RPA con su insignia).
  - Arriba, «**Empieza aquí**» con las rutas 101 y «**Mis rutas**» con las que están en curso y su CTA.
  - La empresa queda como filtro secundario (`<select>`), junto a Producto y Habilidad, dentro de «Más filtros».
  - Enlace destacado al mapa de metro (`paths:map`).
  - Las rutas con varias disciplinas aparecen una vez, en su disciplina principal, con insignias «también en…».
- **Aceptación.** Toda ruta visible es alcanzable desde `/rutas/` sin filtros. Toda disciplina con rutas tiene su
  sección.
- **Pruebas.** `test_every_visible_route_reachable_from_rutas_index`, `test_every_discipline_with_routes_has_section`,
  `test_vendor_is_secondary_filter`, `test_rutas_index_queries_constant`.

### P1-7 · Catálogo sin saturación

- **Archivos.** `apps/catalog/views.py::resources`, `catalog/resources.html`, `catalog/partials/*`, `catalog.css`.
- **Enfoque.**
  - Una caja de búsqueda y **3 filtros visibles**: Disciplina (`select`), Tipo (`select` con conteos) y «Solo
    esenciales» (*checkbox*).
  - **Ruta** pasa a un `<select>` agrupado por disciplina dentro de `<details>` «Más filtros». Ahí también van Con
    certificado, Conocimiento general, Plataforma y Gratuito.
  - Los filtros activos se muestran como **chips removibles** (cada uno es un enlace sin ese parámetro) con «Limpiar
    todo».
  - Se muestra el conteo de resultados.
  - Las 9 pestañas de tipo se quitan: pasan al `select`.
  - Todo es un solo `form` GET y funciona sin JS (`data-autosubmit` opcional).
- **Aceptación.**
  - A 1280 px, la barra de filtros mide ≤ 2 filas cerradas.
  - Cada filtro activo se ve como chip y se quita con un clic.
  - Los parámetros siguen siendo compatibles (`?ruta=`, `?kind=`, `?cert=`) para no romper enlaces.
- **Pruebas.** `test_catalog_filters_compact`, `test_active_filter_chips_remove_param`, `test_legacy_params_still_work`,
  `test_catalog_queries_constant`.

### P1-8 · Dron DGAC y marcadores que se pisan

- **Archivos.** `apps/core/templates/worlds/aero/journey.html` l.27-33, `apps/progress/services.py::_waypoints`,
  `worlds/civil/journey.html`, `apps/progress/external.py::_journey`.
- **Enfoque.**
  - **Aero:** el dron se dibuja en el lado **opuesto** a la etiqueta. `_waypoints` agrega `drone_dy` = `+34` si
    `above` (el dron va debajo del anillo) o `-30` si no. Se valida que quede dentro del `viewBox` 0..330. Si no cabe,
    se desplaza en x (`dx=+30`).
  - **Civil:** «TÚ» va por encima del eje (`marker_y - 26`) con un trazo fino hasta la estaca. Las estacas muestran un
    rótulo corto (`course.short_title` o las 2 primeras palabras del título) y no la *key*.
  - **Arquitectura:** se trunca el nombre del piso con `text-overflow` (SVG `textLength` o un `truncatechars`).
- **Aceptación.**
  - Para n = 2..12 waypoints y cualquier nivel actual, la caja del dron no intersecta la de la etiqueta.
  - En civil, «TÚ» no intersecta la estaca.
- **Pruebas.** `test_drone_never_overlaps_label` (geometría pura sobre `_waypoints`, cajas aproximadas por
  `len(nombre)*7`), `test_civil_marker_clear_of_stake`, `test_stake_labels_are_human`.

### P1-9 · Figuras y vocabulario por ruta (*figure kit*)

- **Meta.** Cada ruta usa una figura y un vocabulario de su tema. Fuera de arquitectura no aparecen «COTA», «+3,50»,
  «Lámina», «Dibujo y modelado» ni «pilares del puente».
- **Mecanismo.**
  - Módulo nuevo `apps/catalog/figures.py` con `FIGURES = {key: {template, labels…}}`.
  - Claves de `labels`: `figure_title`, `zero` (ex «COTA ±0,00»), `step_fmt` (ex `+{i*3.5}`), `unit_label` (ex
    «Escala»), `unit_value`, `sheet_label`, `sheet` (ex «Lámina X-101»), `content` (ex «Dibujo y modelado…»),
    `stats` (lista de rótulos de la cinta, p. ej. CORREDORES · CURSOS · ESTACAS · PILARES), `intro` (texto bajo el
    título), `item` (estaca, piso o waypoint).
  - `LearningPath.figure` (CharField opcional, migración pequeña) más un campo `"figure"` en el JSON de la ruta. Si
    falta, se usa el *flavour* actual (`route_flavour`) llevado a figura.
  - Las plantillas de los tres mundos incluyen `{% include fig.template %}` y leen `fig.labels.*` en vez del texto fijo.
    `_floors` recibe `step_fmt` y `zero`.
- **Figuras** (en `apps/core/templates/worlds/figures/<key>.html`, cada una un SVG que reusa los datos de niveles ya
  calculados: `_floors`, `_waypoints`, `_journey`):

| Figura | Metáfora | Vocabulario | Rutas |
|---|---|---|---|
| `building` (actual) | corte del edificio por pisos | Cota, piso, lámina A-101 | forma-revit, forma-coordinacion, bim-101 (LOD 100→500 en vez de cotas) |
| `pipeline-ai` | datos → modelo → agente, con medidor de «ventana de contexto» | Contexto, capa, *tokens*, *pipeline*, entrega | ia-101, agentes-ia, claude-code-mcp, vibe-coding, herramientas-ia |
| `data-flow` | ingestión → limpieza → análisis → informe | Dataset, consulta, tabla, panel | python-datos-101, datos-reportes, data-science-aplicada |
| `survey-profile` | perfil topográfico con PR (puntos de referencia) y cotas reales | PR, punto, cota, datum | topografia-101, geospatial-data-science (variante «capas GIS») |
| `road-profile` (civil actual) | planta y perfil del corredor | estaca, corredor, km | civil-3d, bentley-learn (OpenRoads) |
| `capture-twin` | escaneo → nube de puntos → modelo → gemelo vivo con sensores | Captura, nube, malla, iModel, sensor | bentley-itwin |
| `plant-iso` | P&ID → isométrico de tuberías | línea, válvula, isométrico | plant-3d, bentley-openplant |
| `doc-flow` | documentos con versiones y estados (WIP → compartido → publicado) | versión, estado, *workflow* | bentley-projectwise |
| `viz-scene` | escena con cámara, luz y render | escena, cámara, render | bentley-lumenrt |
| `building-model` | modelo por disciplinas (estructura, MEP, fachada) | disciplina, modelo, coordinación | bentley-openbuildings |
| `drafting-sheet` | lámina con capas, bloques y XREF | capa, bloque, lámina | autocad |
| `flight-plan` (aero actual) | plan de vuelo | waypoint, ALT, BAT | dgac-rpas |

Estado de cada ruta hoy (de la auditoría):

| Ruta | Qué aprende la persona | Figura y vocabulario hoy | ¿Calza? | Propuesta |
|---|---|---|---|---|
| forma-revit | Revit sobre nube de puntos | edificio, cotas | Sí | `building` |
| forma-coordinacion | Forma ↔ Revit, ACC | edificio | Sí | `building` |
| bim-101 | conceptos BIM | edificio, cotas | A medias | `building` con LOD |
| civil-3d | superficie → alineamiento → corredor | cae en arquitectura con *flavour* civ (perfil) | A medias | `road-profile` |
| autocad | dibujo 2D | edificio (mundo `mechanical` inexistente) | No | `drafting-sheet` |
| plant-3d | P&ID y tuberías | edificio | No | `plant-iso` |
| topografia-101 | geodesia → GNSS → escaneo | edificio, «COTA ±0,00» (captura 23) | No | `survey-profile` |
| geospatial-data-science | GIS y Python | edificio, *flavour* top | No | `survey-profile` (capas) |
| ia-101 | IA en el trabajo | edificio, «Dibujo y modelado», X-101 (captura 30) | No | `pipeline-ai` |
| agentes-ia, claude-code-mcp, vibe-coding, herramientas-ia | agentes, MCP, Git y terminal | edificio, X-101 | No | `pipeline-ai` |
| python-datos-101, datos-reportes, data-science-aplicada | Python, SQL, BI, ML | edificio, X-101 | No | `data-flow` |
| bentley-learn | OpenRoads, MicroStation | planta y perfil | Sí | `road-profile` |
| bentley-itwin | gemelo digital y captura de realidad | planta y perfil, estacas y pilares (captura 34) | No | `capture-twin` |
| bentley-openplant | plantas | planta y perfil | No | `plant-iso` |
| bentley-projectwise | gestión documental | planta y perfil | No | `doc-flow` |
| bentley-lumenrt | visualización | planta y perfil | No | `viz-scene` |
| bentley-openbuildings | edificios | planta y perfil | No | `building-model` |
| dgac-rpas | operaciones con drones | plan de vuelo | Sí (falta corregir el dron, P1-8) | `flight-plan` |

- **Enfoque de entrega.** Primero el mecanismo y las etiquetas: todas las rutas reciben vocabulario propio aunque la
  figura SVG se reuse. Después se dibujan las figuras, de a 2 por commit, empezando por `pipeline-ai`,
  `survey-profile` y `capture-twin`. Las figuras que falten usan la figura genérica `stack` (pila de capas sin cotas)
  con su vocabulario. Si se toca un mundo, aplica la skill `nuevo-mundo`.
- **Aceptación.**
  - En ninguna ruta fuera de `building` aparecen «COTA», «Lámina», «Dibujo y modelado», «+3,50», «pilar» ni «estaca»,
    salvo que la figura las tenga en su vocabulario.
  - La tabla anterior queda en `docs/MUNDOS.md`.
- **Pruebas.**
  - `test_every_route_has_a_figure`;
  - `test_route_page_labels_belong_to_its_figure`: para cada ruta se renderiza el detalle y se comprueba que las
    palabras prohibidas por figura (lista en `figures.FORBIDDEN`) no aparezcan;
  - `test_figure_templates_exist`.

### P1-10 · Avatar y hoja: menos invasivo y una figura legible

> **Ampliado en [`AVATAR_REDISENO.md`](AVATAR_REDISENO.md)** (editor en 6 secciones, escenario 40×40, halo y equipo
> por disciplina, hoja con un lugar por dato y PR 1–7). Ese documento manda sobre esta sección y sobre el PR G.

- **Archivos.**
  - `apps/gamification/views.py`, `templates/gamification/sheet.html`, `avatar_editor.html`, `_preview.html`,
    `_next_goal.html`.
  - `static/gamification/sheet.css`, `game.css`.
  - `apps/gamification/avatar/engine.py`, `palettes.py`, `parts/props.py`, `services.py`, `templatetags/avatar_tags.py`.
  - `docs/AVATARES_PIXEL.md`, `docs/GAMIFICACION.md`.
- **Repeticiones a quitar (un lugar por dato):**
  - nivel, XP y título solo en el chip de cabecera (anillo) y en la tarjeta resumen de la hoja; en la portada, solo
    «Tu avance»;
  - bonos de carrera solo en la lista de atributos;
  - la tarjeta del editor no muestra el «título» de carrera con el mismo estilo que el título de juego: se renombra
    «Oficio».
- **Hoja:**
  - resumen primero: avatar 192 px, nombre, oficio, nivel con anillo y el **próximo logro** (uno solo);
  - debajo, `<details>` para Atributos, Insignias, Habilidades, Credenciales y Línea de tiempo;
  - las tres vistas (juego, compacta, pro) cambian solo cuánto se abre por defecto.
- **Editor:** sigue siendo una página propia, sin modal.
  - Vista previa fija + **4 grupos** en pestañas sin JS (radios + `:checked`): Oficio · Cara y pelo · Ropa y
    herramienta · Fondo y marco.
  - Botones **Guardar** y **Cancelar** (vuelve a la hoja sin guardar). «Sorpréndeme» queda como secundario.
  - Las miniaturas se renderizan en lazy (solo el grupo abierto en el servidor con `?grupo=`) para bajar de ~170 SVG.
- **Figura más legible (especificación para `artista-pixel`, skill `sprite-8bit`):**
  - **Escala entera:** se sirve a 4× (128 px) para la figura completa sin marco. El marco va en CSS (borde de
    `--rarity-*`), no dentro del SVG, así la escala vuelve a ser entera: 32 u → 32, 64, 96, 128 o 192 px.
  - **Chip de cabecera:** busto de 16×16 celdas (recorte cara y hombros) a 2× = 32 px, sin recorte circular (esquinas
    redondeadas de 6 px).
  - **Silueta:** contorno exterior de 1 px en un color claro adaptable (`--av-outline`: `#F4EBD8` en oscuro y `#0A0E13`
    en claro) que se calcula en `render_svg`. Se agregan fondos claros (papel cuadriculado) para el tema claro.
    `outfit_stands_out` se aplica también al elegir a mano y en `apply_career` (con aviso).
  - **Equipo por disciplina, legible a 2×:** jalón y estación total (Topografía), control de dron (Captura), casco y
    plano (Civil), laptop con ícono de modelo (Arquitectura e IA), llave y engranaje (Mecánica). La herramienta ocupa
    ≥ 6×10 celdas y se ve también en el busto (asoma por el hombro).
  - **Información:** insignia de nivel en la esquina (sprite de 8×8 «NV n») y hasta 3 accesorios de logros con
    **leyenda** debajo en la hoja («Casco: insignia Primer cuadrante»).
  - Todo sigue saliendo del motor por capas (datos), sin dibujos a mano.
- **Aceptación.**
  - Ningún tamaño de avatar en plantillas es fraccionario respecto de 32.
  - Contraste de la silueta con el fondo ≥ 3:1 en claro y oscuro (prueba con la utilidad de contraste ya existente en
    `engine`).
  - El editor tiene ≤ 4 grupos visibles, Guardar y Cancelar, y funciona sin JS.
- **Pruebas.** `test_avatar_sizes_are_integer_multiples`, `test_outline_contrast_both_themes`,
  `test_editor_groups_and_cancel`, `test_sheet_each_fact_once`, `test_editor_render_count_bounded`.

### P1-11 · Profundidad visual: tarjetas y barras con capas

- **Archivos.** `apps/core/static/core/tokens.css`, `components.css`, `welcome.css`, `catalog.css`, `base.css`.
- **Enfoque.**
  - **Tokens de elevación:**
    - `--elev-1` (tarjeta: sombra corta + borde de papel);
    - `--elev-2` (*hover* y barras pegajosas);
    - `--elev-3` (*popovers* como «Más», campana y menú de usuario).
  - **Superficies en oscuro:** `--surface-0` (fondo), `--surface-1` (+4 % de luz) y `--surface-2` (+8 %) para separar
    capas.
  - **Acento por disciplina:** `--disc-arq`, `--disc-civ`, `--disc-top`, `--disc-mec`, `--disc-cap`, `--disc-iad`,
    `--disc-tra` (los colores de los círculos de la portada). Se usan como borde superior o «pestaña» de la tarjeta.
  - *Hover:* `translateY(-2px)` + `--elev-2`, que se anula con `prefers-reduced-motion`.
  - Se aplica a `route_card`, tarjetas del catálogo, barra de filtros, `w-jump` y cabecera.
- **Aceptación.**
  - En oscuro, tarjeta y fondo tienen un contraste de luminancia ≥ 1,25:1 y bordes visibles.
  - En claro se mantiene el papel.
  - Sin movimiento con `reduce`.
- **Pruebas.** `test_tokens_define_elevation_and_discipline_accents` (lectura del CSS). El resto es visual (Haiku).

### P2

- **P2-1:** decidir los mundos `survey` y `mechanical` (hoy declarados y sin plantillas) o retirarlos del JSON y usar
  figuras (anotarlo en DECISIONES).
- **P2-2:** registros de seguridad: logins fallidos y bloqueos 429 sin correo en claro (hash), inscripciones D34 y D35.
- **P2-3:** que `resolve_world` implemente «sin `world` → el de la disciplina principal», como dice MUNDOS.md.
- **P2-4:** revisar en navegador las 93 URLs de Autodesk y cambiar las que den 404 real. Reemplazar `planbim.cl` si
  sigue en 500.
- **P2-5:** quitar `tests/test_tmp_debug.py` (archivo vacío en `main`).

---

## c) Riesgos

| Riesgo | Mitigación |
|---|---|
| Sacar «Certificados» de la barra principal es una decisión de producto | Anotarla en DECISIONES y confirmarla con el dueño antes de fusionar P1-5. Alternativa: dejar Certificados y mover Equipo a «Más» |
| Cambiar `team_signup_result` cambia el texto que ven personas reales | Mismo flujo, solo el texto. Probar los 4 resultados |
| Categorías nuevas del foro | Solo se agregan al final. `ideas-mejoras` no cambia de slug (`POLL_CATEGORY`) |
| `LearningPath.figure` necesita migración | Campo opcional con valor por defecto `""`. La migración se aplica sola |
| El recorrido completo alarga el CI | Canonicalizar el catálogo y tope de 3000. Hoy tarda unos 30 s por rol. Si pasa de 3 min, marcarlo `@pytest.mark.slow` y correrlo en un *job* aparte |
| Avatar: subir la escala y cambiar el contorno altera los avatares guardados | La configuración no cambia, solo el render. Comparar el antes y el después con `audit.py` |
| La 404 propia podría revelar que algo existe | Mismo texto y código para «oculto» y «no existe». Prueba incluida |
| Datos DGAC privados | Las pruebas usan solo `tests/fixtures/dgac`. Nada de la ruta real va al repo ni a Nala |
| Ronda grande | Se divide en PR por prioridad (abajo). Ningún PR mezcla P0 con P1 |

---

## d) Tareas para el implementador (Sonnet), en orden

Una rama por PR, apilada sobre `mejoras-ux`. Commits pequeños en español e imperativo. Después de cada PR:
`uv run pytest` + `uv run ruff check . && uv run ruff format --check .`.

**PR A, `mejoras-ux-p0-enlaces` (P0-1)**
1. `Amplía la auditoría de enlaces a todo el sitio y a los formularios` (`tests/test_enlaces.py`, fixture `site_world`).
2. `Agrega una página 404 útil y su registro sin datos personales`.
3. `Agrega el comando revisar_enlaces para enlaces internos y externos`.
4. `Marca los enlaces externos del catálogo`.

**PR B, `mejoras-ux-p0-cuentas` (P0-2)**
5. `Agrega Entrar y cómo obtener cuenta en la cabecera pública`.
6. `Agrega el menú de usuario con Mi cuenta y Salir`.
7. `Agrega el cambio de contraseña para sesiones con contraseña`.
8. `Unifica la respuesta del enlace del equipo para no revelar cuentas`.
9. `Mejora la pantalla de espera`.
10. `Agrega el paso a paso de altas en Equipo → Personas`.
11. `Registra en la bitácora los comandos de alta`.
12. `Documenta cómo dar de alta cuentas` (OPERACION y PRODUCCION).

**PR C, `mejoras-ux-p1-cabecera` (P1-5, P1-11 tokens)**
13. `Agrega tokens de elevación y acento por disciplina`.
14. `Reorganiza la cabecera en cinco secciones y menú Más` (y el menú hamburguesa sin JS).
15. `Quita la cinta duplicada de la portada`.

**PR D, `mejoras-ux-p1-tomar-cursos` (P1-1, P1-4, P1-2)**
16. `Agrega el icono de la ruta DGAC y amplía la prueba de unicidad`.
17. `Agrega el servicio de llamada a la acción por ruta`.
18. `Unifica la tarjeta de ruta con icono y botón`, aplicada en la portada, `/rutas/`, el catálogo y el foro.
19. `Agrega Cómo funciona y el botón Empezar o Continuar en cada mundo`.
20. `Agrega Continuar donde quedaste y Empieza aquí en la portada`.
21. `Muestra cada ruta una vez en la portada con sus otras disciplinas`.
22. `Separa el doodle del héroe de los círculos de disciplina`.
23. `Agrega migas y siguiente paso en el panel del nivel`.

**PR E, `mejoras-ux-p1-rutas-catalogo-foro` (P1-6, P1-7, P1-3)**
24. `Organiza las rutas por disciplina con Empieza aquí y Mis rutas`.
25. `Simplifica los filtros del catálogo`.
26. `Agrega las categorías del foro para el equipo`.
27. `Muestra Conversaciones del equipo en el foro y la portada`.

**PR F, `mejoras-ux-p1-mundos` (P1-8, P1-9)**
28. `Evita que el dron y el marcador TÚ tapen las etiquetas`.
29. `Agrega el kit de figuras y el vocabulario por ruta` (módulo, campo, migración y plantillas leen `fig.labels`).
30. `Asigna figura a cada ruta`: los JSON de `seed/rutas` y `tests/fixtures/dgac/ruta.json`; skill `nueva-ruta`.
31. Dibujar las figuras de a 2 por commit: `pipeline-ai` y `data-flow`, `survey-profile` y `capture-twin`, `plant-iso`
    y `doc-flow`, `viz-scene` y `building-model`, `drafting-sheet`.
32. `Documenta las figuras por ruta en MUNDOS`.

**PR G, `mejoras-ux-p1-avatar` (P1-10)**: el arte se separa del diseño de pantalla.
33. `Ordena la hoja: resumen primero y detalles plegables`.
34. `Reduce el editor a cuatro grupos con Guardar y Cancelar`.
35. `Renderiza el avatar a escala entera con contorno adaptable` (motor).
36. Encargo a `artista-pixel`: equipo por disciplina, sprite de nivel y fondos claros (`parts/props.py`,
    `palettes.py`), en commits separados.
37. `Actualiza AVATARES_PIXEL y GAMIFICACION`.

Reglas:
- Lo que quede ambiguo va a `docs/DECISIONES.md` como pregunta abierta: Certificados en «Más», Seguimiento ↔
  Improvement y mundos survey y mechanical.
- No tocar `legacy/`, `design/`, `deploy/` ni datos DGAC reales.
- Antes de cada PR, pasar la skill `revision-privacidad`.

---

## e) Qué verifica el agente Haiku

1. **Recorrido de enlaces.** `uv run pytest tests/test_enlaces.py -q` en verde. Además, contra un servidor local:
   - `DATABASE_PATH` en el scratchpad;
   - `uv run python manage.py migrate && uv run python manage.py seed_catalog`;
   - `DGAC_DATA_DIR=tests/fixtures/dgac uv run python manage.py cargar_dgac`;
   - `DEV_REMOTE_USER=<admin de prueba> uv run python manage.py runserver`.
   Se recorre como admin, miembro y pendiente, y se entrega la lista `código · URL · origen` (debe estar vacía). Luego
   se corre `revisar_enlaces --externos` y se entrega la lista de 404 externos reales, verificados en un navegador
   (no 403 de antibots).
2. **Lista de enlaces que debe abrir a mano (200):**
   - `/`, `/rutas/`, `/rutas/mapa/`, `/catalogo/`, `/foro/` y cada `?categoria=` de las 9 categorías;
   - `/equipo/`, `/equipo/personas/` (admin), cada entrada de «Más», `/ayuda/`, `/dgac/`, `/perfil/`, `/perfil/avatar/`,
     `/cuenta/`;
   - por cada ruta: `/rutas/<slug>/`, el botón CTA, `/rutas/<slug>/notas/` y el diploma si aplica;
   - `/rutas/no-existe/` debe dar la 404 propia.
3. **Profundidad:** la tabla de clics desde `/` hasta cada ruta (≤ 2) y hasta cada nivel (≤ 3).
4. **Capturas** en claro y oscuro a **1280 y 375 px** (la cabecera, además, a 1024 y 768):
   - cabecera (sin segunda cinta, sin cortes, «Más» sin tapar nada);
   - portada (héroe sin superposición, «Continuar» o «Empieza aquí», rutas sin repetir);
   - `/rutas/` (secciones por disciplina);
   - `/catalogo/` (≤ 2 filas de filtros, chips activos);
   - `/foro/` (5 tarjetas del equipo);
   - `/bienvenida/` sin sesión (botón Entrar y «¿Cómo obtengo mi cuenta?») en la tailnet y en la puerta pública;
   - `/espera/` (con Salir);
   - `/cuenta/`;
   - DGAC (dron sin tapar «Roles» en D0, y con el nivel actual en D2 y D4);
   - bentley-itwin, ia-101, topografia-101, plant-3d y projectwise (figura y vocabulario propios);
   - hoja de personaje y editor de avatar.
5. **Tabla de vocabulario:** por cada una de las 23 rutas, figura, `zero`, `unit_label`, `sheet` y rótulos de la cinta
   de estadísticas, tomados del HTML. Ninguna palabra prohibida fuera de su figura.
6. **Iconos:** 23 rutas con icono distinto (hash de bytes) y visible en la portada, `/rutas/`, el catálogo y el foro.
7. **Accesibilidad básica:** Tab recorre la cabecera y el menú de usuario. Escape cierra «Más». Sin JS (desactivado):
   la navegación, «Más», la hamburguesa, los filtros del catálogo y el editor de avatar funcionan.
8. **Privacidad:** el log del servidor durante el recorrido no tiene correos ni *queries* con datos. Ningún archivo
   nuevo trae datos reales.
