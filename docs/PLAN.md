# Plan de implementación · AeroAcademy · Academia LEV Digital 101

Trabajar **un bloque por sesión** con la skill `bloque`. Al cerrar cada bloque: pruebas en verde, este archivo actualizado y resumen del cambio.
Estado: `[ ]` pendiente · `[~]` en curso · `[x]` terminado.

## Orden

```
Etapa 1 · Base y Autodesk     0 → 1 → 2 → 3
Etapa 2 · Bentley y certif.   5 → 13 → 14
Etapa 3 · Mostrar             12
Etapa 4 · Comunidad           4 → 10 → 16
Etapa 5 · Teo                 15
Etapa 6 · Evidencia y equipo  6 → 7
Etapa 7 · Biblioteca          9 → 11
Etapa 8 · Producción          8
```

Al cerrar la Etapa 2 ya se puede hacer lo central: recorrer la ruta Autodesk, registrar cursos Bentley con su
certificado, que el moderador los valide y ver crecer XP, insignias y la hoja de personaje.

---

## Bloque 0 · Base del repositorio `[x]`

> **Hecho (2026-10-08).** Notas:
> - Proyecto `config/` (settings `base`/`dev`/`prod`) y las 11 apps bajo `apps/`. `prod` exige `SECRET_KEY` y `ALLOWED_HOSTS`; SQLite en modo WAL.
> - `core`: `base.html` con cajetín, huecos `player`/`bell`/`teo` (parciales vacíos; se ocultan solas), `tokens.css` claro/oscuro con capa de juego, `theme.js` y Archivo local.
> - 10 pruebas en `tests/test_bloque0.py`; `ruff` y migraciones en verde; sin desborde a 390 px en claro y oscuro (medido en navegador).
> - **Pendiente:** el archivo `PressStart2P.woff2` (OFL) no está en el repositorio, así que el `@font-face` queda comentado en `tokens.css` y se usa una monoespaciada de respaldo. Ver A10 en DECISIONES.
> - WhiteNoise solo corre en producción; en dev lo reemplaza `runserver`.
- Proyecto Django con `uv`, settings por entorno (`settings/base.py`, `dev.py`, `prod.py`), `ruff`, `pytest`.
- Apps vacías: `core`, `accounts`, `catalog`, `paths`, `progress`, `community`, `credentials`, `team`, `gamification`, `notifications`, `assistant`.
- `core`:
  - plantilla base con cabecera tipo cajetín, marca "AeroAcademy · Academia LEV Digital 101" y huecos para nivel/XP, campana y Teo (vacíos por ahora);
  - `tokens.css` portado del prototipo (claro + oscuro) y fuentes locales Archivo + Press Start 2P (OFL);
  - estructura vacía `core/static/worlds/` y `core/templates/worlds/`.

**Acepta si:** `uv run pytest` pasa con una prueba de humo; la página base renderiza en claro y oscuro sin desborde a 390 px.

## Bloque 1 · Identidad, roles y aprobación `[x]`

> **Hecho (2026-10-08).** Notas:
> - `Person` (login de Tailscale, sin contraseña) con estado `pending`/`approved`/`suspended` y los campos de la hoja de personaje. Roles con grupos `member`/`lead`/`admin` (migración `0002`); el admin es superusuario y `lead` es el grupo.
> - `TailscaleRemoteUserMiddleware`: IP no confiable → 403 (con o sin encabezado); sin encabezado → 401; `DEV_REMOTE_USER` solo con `DEBUG`. Django 5.2 ignora la respuesta de `process_request` en `__call__`, por eso se sobrescribe `__call__`.
> - `ApprovalMiddleware`: `pending` solo ve `/espera/`; `suspended` recibe 403. Cola de aprobación en el admin (acciones aprobar, suspender y asignar rol; el rol solo cambia por `services.set_role`).
> - **Todos** los de `BOOTSTRAP_ADMINS` quedan admin y aprobados (la doc decía "el primero").
> - 45 pruebas en verde; `ruff` y migraciones desde cero en verde.
> - **Pendiente:** `Person.discipline` es texto hasta el Bloque 2 (pasa a M2M con `Discipline`); el título elegido (`selected_title`) llega con gamification (Bloque 13/14); el aviso al moderador por persona nueva llega con notificaciones (Bloque 16).
- `TailscaleRemoteUserMiddleware` según ARQUITECTURA (confianza solo desde `TRUSTED_PROXY_IPS`).
- Modelo Person (con `status` y campos de hoja de personaje, ver MODELO_DATOS), grupos `member`/`lead`/`admin`, `BOOTSTRAP_ADMINS`, `DEV_REMOTE_USER` solo en dev.
- Flujo `pending` → `approved`: página `/espera/` y cola mínima de aprobación en el admin de Django. La pantalla propia llega en el Bloque 16.

**Acepta si:** pruebas cubren:
- encabezado desde 127.0.0.1 crea o actualiza la persona como `pending`; desde otra IP → 403; sin encabezado → 401;
- `DEV_REMOTE_USER` se ignora con `DEBUG=False`;
- `pending` no ve contenido; `BOOTSTRAP_ADMINS` entra aprobado como admin.

## Bloque 2 · Catálogo, vendors y rutas `[x]`

> **Hecho (2026-10-08).** Notas:
> - Modelos de `catalog` y `paths` con admin. `Person.discipline` pasó a M2M `disciplines`.
> - `seed_catalog` carga `vendors.json`, `plataformas.json`, `skills.json` (nuevo) y `rutas/*.json`; valida antes de escribir, es idempotente, acepta `--dry-run` y `--seed-dir`, y es atómico.
> - D7: lo que sale de un JSON se marca `retired`, no se borra. `Milestone.completed_by_resource` se llena desde la semilla (`n1-t0`, `n1-t4`, `n2-t5`).
> - **`insignias.json` y `titulos.json` los carga el Bloque 13**, cuando existan sus modelos.
> - Vistas: `/rutas/` (vendor → producto, filtros por disciplina y habilidad), `/rutas/<slug>/` y `/catalogo/` (filtros, búsqueda y paginación). Las rutas sin publicar solo las ve un lead.
> - Las URLs de Bentley marcadas `verify_url` apuntan al catálogo y siguen pendientes de confirmar con una cuenta Bentley.
> - 79 pruebas del bloque en verde.
- Modelos de `catalog` (Discipline, Vendor, Product, Platform, Skill, Resource) y `paths` (LearningPath con `kind` y `world`, Level, Milestone, QuizQuestion, ExternalCourse, PathExtra, SharedItem). Admin de Django para todo.
- Comando `seed_catalog`:
  - carga `seed/plataformas.json`, `seed/vendors.json`, `seed/rutas/*.json`, `seed/insignias.json` y `seed/titulos.json`;
  - es idempotente y actualiza por `slug`/`key`;
  - opción `--dry-run` que valida sin escribir.
- Vistas:
  - *Rutas*: pestañas por vendor → productos → campañas, con filtros por disciplina y habilidad;
  - catálogo de recursos (por plataforma, tipo, gratuito, certificado);
  - detalle de ruta genérico, sin mundo todavía.

**Acepta si:** `seed_catalog` dos veces no duplica; la ruta forma-revit queda con 7 niveles y todas sus `key`; bentley-learn queda con sus capítulos y cursos externos; `--dry-run` detecta una `key` duplicada.

## Bloque 3 · Mundo Arquitectura: ruta interactiva y avance `[x]`

> **Hecho (2026-10-08).** Notas:
> - `progress`: `MilestoneCheck`, `QuizAnswer` y `PathGoal` (únicos por persona). `SharedCheck` llega con el Bloque 7.
> - Contrato de mundos (`docs/MUNDOS.md`): `worlds/<mundo>/path.html` + `_app.html`; `paths:detail` usa el mundo si existe y si no cae a la vista genérica. Primer mundo: `architecture` (portada con nube de puntos, corte del edificio, *Project Browser*, panel del nivel).
> - Avance = (hitos + preguntas correctas) / (hitos + preguntas), sin lo retirado; redondeo clásico (12,5 → 13).
> - Cada persona aparece en el piso donde trabajó por última vez (solo aprobadas).
> - **Sin HTMX por ahora (D23):** `core/static/core/enhance.js` hace la actualización parcial (`X-Partial`); sin JS, formularios y enlaces normales con redirección.
> - Semilla de Forma ampliada con `description`, `intro` y `flow` (nuevos tipos de extra).
> - 127 pruebas en verde; revisado a escritorio y 390 px, claro y oscuro.
> - **Pendiente:** notas del equipo en el mundo (Bloque 4), tabla del equipo y meta visible por persona (Bloque 7).
- Contrato de mundos de `MUNDOS.md`: componentes compartidos (panel del capítulo, schedules) + piel `architecture` migrada del prototipo (corte del edificio, Project Browser, cajetín, portada con nube de puntos).
- HTMX: marcar hito, responder quiz, fijar meta de certificación. Recalcular porcentajes en la respuesta parcial.
- Avance del equipo visible en el corte (marcas por persona).

**Acepta si:** marcar/desmarcar y responder persisten por persona; los porcentajes coinciden con la regla de MODELO_DATOS;
funciona sin JS para lectura; coincide visualmente con `legacy/ruta-forma-revit/static/index.html` en escritorio y a 390 px.

## Bloque 5 · Repositorio de credenciales + Ruta Bentley (mundo Civil) `[x]`

> **Hecho (2026-10-08).** Notas:
> - `Credential` con archivo **privado** (`PrivateStorage`, sin URL pública; nombre generado `credentials/<persona>/<uuid>.<ext>`), tipo real por firma (PDF/PNG/JPG), máx. 10 MB y SHA-256. Se descarga solo por `credentials:download` (dueño, leads y admin; `attachment`, `nosniff`, `no-store`).
> - Revisión `pending` → `verified`/`rejected` por un lead (rechazar exige comentario). Editar archivo, fechas o emisor de una credencial verificada o rechazada la devuelve a `pending`.
> - Verificar una credencial con `resource` marca las misiones que ese recurso completa (`MilestoneCheck.source="credential"`); esa marca no se deshace a mano y se quita sola si la credencial deja de estar verificada o se borra. Una marca manual previa no se reemplaza.
> - Páginas: mis credenciales, subir/editar/eliminar, detalle, **credenciales del equipo** (solo `verified` + `team`, sin abrir archivos), cola **por revisar**, y **registrar curso + certificado** en rutas externas (curso de la lista o curso libre). Un lead puede **promover** un curso libre al catálogo (queda en el capítulo `lib` con clave `lib-cN`).
> - **Mundo Civil** (`worlds/civil/`): portada en estilo Levantamiento, planta-perfil con una estaca por curso y un pilar del puente por reliquia, *Explorer · Corridors* y panel con estados (verificado, en revisión, rechazado, por registrar). Avance = cursos obligatorios verificados (`any_one` completa con uno).
> - Bug encontrado: con el idioma en español Django escribe `12,5` y rompe las coordenadas del SVG; ahora van como texto con punto (`_n()`), con prueba de regresión.
> - Lint: `E501` desactivado en general (el formateador parte el código; las frases largas en español se permiten).
> - Endurecido tras revisión independiente: sin redirección abierta en 
ext, revisión con bloqueo y huella de versión (D26), no se revisa lo propio, archivos borrados con la fila (señal + on_commit), rechazar una de dos credenciales del mismo curso no quita la marca, promover exige verificada, registro duplicado bloqueado, topes de consultas.
> - 353 pruebas en verde; revisado a escritorio y 390 px.
> - **Pendiente:** XP/insignias al verificar (Bloque 13); avisos al moderador y al dueño (Bloque 16); vencimientos con aviso y exportación (Bloque 6); equipo en el recorrido civil (Bloque 7).
- Alta/edición de credencial con archivo privado; validación de tipo real y tamaño.
- Flujo de revisión: `pending` → `verified`/`rejected` por lead, con comentario. Reglas de MODELO_DATOS (vuelve a pending al editar).
- Vínculo con recurso/ruta y marcado automático de hitos y cursos externos.
- **Registrar curso + certificado** en rutas `external_track`:
  - elegir un curso de la lista, o escribir un curso libre (nombre, URL, fecha) y subir el PDF;
  - el lead puede **promover** un curso libre al catálogo.
- **Mundo `civil`** (skill `nuevo-mundo`): planta-perfil con progresivas, estacas por curso y pilares del puente por acreditación.
- Listados: "Mis credenciales", "Credenciales del equipo" (solo `verified` + `team`), "Por revisar" (leads).

**Acepta si:**
- un miembro no puede descargar archivos ajenos (403) y un lead sí;
- subir un `.exe` renombrado a `.pdf` se rechaza;
- verificar una credencial de *Learn Forma Site Design in 90 minutes* marca el hito correspondiente;
- verificar una credencial de *Bentley Accredited Road Modeler* cumple su curso externo y levanta su pilar;
- promover un curso libre crea un Resource y un ExternalCourse al final del capítulo "Cursos libres".

## Bloque 13 · Motor de juego `[x]`

> **Hecho (2026-10-08).** Notas:
> - Modelos `XPEvent` (único por persona+origen), `Badge`, `PersonBadge`, `Title`, `PlayerState`; `Person.selected_title`. `AvatarItem` no hizo falta: las piezas piden una insignia en `engine.UNLOCKS`.
> - `game.py`: niveles (`50·L·(L−1)`), `award`/`revoke`, reconciliación `sync_progress` (misión 10, capítulo 25, campaña 150) y `sync_credentials` (trofeo 100, reliquia 500, habilitación 300, interna 50), quiz (5, solo la primera vez), racha semanal, títulos disponibles/mostrado y celebraciones. `rules.py`: `count`, `path_complete`, `distinct_vendors`, `streak`, `credential_kind` (+ `vendor`, `platform`, `products_all`, `requires_valid`) y `manual`.
> - Se llama desde `progress.services` y `credentials.services` (verificar, rechazar, editar, borrar, promover), sin signals (D28).
> - `seed_catalog` carga y valida `insignias.json` y `titulos.json` (reglas, sprites, slugs); lo que sale del archivo se retira.
> - 19 sprites 16×16 + candado en `apps/core/static/game/badges/`, dibujados por subagente.
> - Cabecera: nivel, barra de XP y título; aviso de insignia nueva y de subida de nivel hasta que la persona lo cierra (funciona sin JS).
> - `unlocked_badges()` del editor de avatares ya usa las insignias reales.
> - **Pendiente:** fuente Press Start 2P (A10) y sonido opcional; eventos `note`, `accepted_answer`, `profile_completed` los emiten los bloques 4, 10 y 14; vista de historial de XP en la hoja (Bloque 14).
- App `gamification`: XPEvent, Badge, PersonBadge, Title, AvatarItem (MODELO_DATOS).
- `services.award()` / `revoke()` invocados desde los services de `progress`, `credentials` y `community` (sin signals ocultos).
- Motor de reglas de insignias: `count`, `path_complete`, `distinct_vendors`, `streak`, `credential_kind`, `manual`.
- Cálculo de nivel y título según GAMIFICACION; racha semanal.
- Cabecera: nivel en Press Start 2P, barra de XP y título; *toast* de insignia y modal de subida de nivel (respeta `prefers-reduced-motion`).

**Acepta si:** marcar y desmarcar no duplica XP; rechazar o editar una credencial verificada revoca su XP e insignia; cada tipo de regla tiene prueba; el nivel coincide con la tabla de GAMIFICACION.

## Bloque 14 · Hoja de personaje `[x]`

> **Hecho (2026-10-08).** Notas:
> - Rutas: `/perfil/` (mi hoja), `/perfil/editar/` (solo yo: la ruta no recibe un id), `/personas/<id>/` (hoja de otra persona, solo aprobadas) y `/personas/` (**El gremio**, orden alfabético, sin ranking: D17).
> - Edición: titular, bio, clase, título (solo entre los desbloqueados, validado en el servidor), enlaces LinkedIn/Credly (solo https del sitio correcto) y vista por defecto. Cambiar la clase actualiza la del avatar. El avatar sigue en `/perfil/avatar/`.
> - Vista de juego (nivel, barra de XP, atributos en hexágono, vitrina con insignias bloqueadas y su pista, línea de tiempo) y vista profesional (habilidades por vendor y credenciales verificadas), con `?vista=`.
> - Atributos MOD/CAP/ANA/DOC/NOR/COL = 2 por credencial verificada con una habilidad de ese atributo (tope 20; COL suma 1 cada 3 respuestas aceptadas). Todo lo que sale de credenciales respeta la visibilidad del repositorio: de otra persona solo lo verificado y visible al equipo.
> - Completar la hoja (titular, bio, clase y avatar) otorga una vez la marca `profile_completed` → insignia *Hoja Completa*.
> - Cabecera: el avatar y el nivel llevan a la hoja; nueva sección «Gremio».
> - Directorio sin consultas por tarjeta (`game.prefetch_badges`).
> - **Pendiente:** exportar la vista profesional a PDF; árbol de habilidades con las campañas que las declaran; accesorios de nivel 10 (capa del mundo favorito).

> **Adelanto:** el generador de avatares pixel-art ya existe (`apps/gamification/avatars.py`, con pruebas) y su
> galería está en `design/avatares/`. Este bloque lo conecta: componente `{% avatar person size=32 %}`,
> editor de la hoja y validación de piezas desbloqueadas con `clean_config(..., unlocked=...)`. Ver `docs/AVATARES_PIXEL.md`.
- Perfil editable: titular, bio, disciplina, clase, título elegido (solo entre desbloqueados), enlaces y avatar 8-bit por capas (solo items desbloqueados).
- Vista profesional y vista de juego (GAMIFICACION): atributos en hexágono, vitrina de insignias, árbol de habilidades por vendor, línea de actividad.
- Directorio del equipo con tarjetas de personaje.

**Acepta si:** solo el dueño edita su hoja; no se puede elegir un título o un accesorio bloqueado (validación en el servidor); los atributos coinciden con las credenciales verificadas; no hay desborde a 390 px.

## Bloque 12 · Portada Academia `[x]`

> **12a · Bienvenida: hecha (2026-10-08).** Ventana de inicio según `design/academia/index.html`: hero con las
> cinco disciplinas, saludo con el nombre, 7 módulos (con estado según su bloque), rutas por disciplina desde la
> base, banda del equipo, **auspicio de Suite Aero** y valores. El auspicio también va en el pie de todas las páginas.
> Pruebas en `tests/test_welcome.py`.
>
> **12b · Datos vivos: hecha (2026-10-08).** Nivel, XP y título en la cabecera (Bloque 13) y, en la portada, la banda
> «Tu misión sugerida» (sigue la campaña con más avance: próxima misión de una ruta estructurada, o el próximo curso
> obligatorio sin certificado en una externa, saltando lo que está en revisión), Teo estático con su globo, el
> **tablón del gremio** (insignias, campañas y certificados visibles al equipo de los últimos 7 días; nada privado) y
> contadores (certificados por revisar para responsables; credenciales propias por vencer). Código en
> `apps/core/dashboard.py`, pruebas en `tests/test_dashboard.py`. **Pendiente:** consultas abiertas (Bloque 10),
> campana (Bloque 16) y el widget de Teo (Bloque 15).
- Portada según `design/academia/index.html`:
  - disciplinas con fotos;
  - módulos enlazando a cada app;
  - rutas por vendor y disciplina;
  - banda del equipo y valores.
- Suma: XP y nivel de la persona, **misión sugerida**, Teo (estático hasta el Bloque 15), **tablón del gremio** y contadores reales (consultas abiertas, credenciales por vencer, certificados por revisar para el lead).

**Acepta si:** coincide visualmente con la referencia en escritorio y no desborda a 390 px; la misión sugerida corresponde al avance real.

## Bloque 4 · Notas del equipo `[x]`

> **Hecho (2026-10-08).** Notas:
> - `community.Note` (tipos Funciona / No funciona / Recomendación / Pregunta + respuestas de un nivel, máx. 1000 caracteres, borrado lógico). Servicios en `apps/community/services.py`.
> - Páginas: `/rutas/<slug>/notas/` (bitácora con filtros por tipo y capítulo, formulario y respuestas) y un panel «Notas del equipo» con las últimas 3 en cada mundo (`{% level_notes %}`).
> - Forma propia por mundo: nube de revisión (Arquitectura) y estaca anotada (Civil), en `community/notes.css`.
> - XP: 5 por nota *Funciona* o *Recomendación*, **hasta 5 al día**; toda nota cuenta para *Primera Nube*. Borrar revoca el XP y la insignia.
> - Solo quien escribe borra; borrar una nota oculta sus respuestas. Texto escapado; `next` sin redirección abierta; rutas no publicadas dan 404.
> - **Pendiente:** ocultar/reportar (Bloque 16), notas por recurso en el catálogo, aviso al autor cuando le responden (Bloque 16).
- Notas por ruta, nivel y recurso; respuestas; borrado lógico solo por el autor.
- Cada mundo muestra la nota con su forma propia (nube de revisión, estaca anotada…).
- Bitácora con filtros (tipo, ruta, nivel). XP por nota útil (límite diario).

**Acepta si:** pruebas de permisos (no borrar notas ajenas); texto escapado (sin HTML inyectado); el límite diario de XP se respeta.

## Bloque 10 · Foro y consultas `[x]`

> **Hecho (2026-10-08).** Notas:
> - `Category` (semilla `seed/foro.json`, se retiran, no se borran), `Thread` (conversación o consulta) y `Post`. Lógica en `apps/community/forum.py`, vistas en `forum_views.py`.
> - Páginas: `/foro/` (búsqueda, categoría, disciplina, tipo, estado «sin respuesta», **paginado de 20**), `/foro/nuevo/` y `/foro/<id>/` con respuestas, aceptar, cerrar/reabrir y borrar el propio mensaje. El listado enlaza las notas de cada ruta.
> - Solo quien abrió la consulta o un responsable acepta (o quita) la respuesta; cambiarla mueve el XP. **50 XP** a quien respondió (no si se respondió a sí mismo); se revoca al quitarla o borrar el mensaje. Alimenta *Mentor* y *Sabio del Foro*.
> - Texto escapado; portada con contador de consultas sin respuesta; «Foro» en la navegación y el módulo queda disponible.
> - **Pendiente (Bloque 16):** fijar, ocultar, mover, reportar y avisos al responder.
- Hilos y posts por categoría y disciplina; consultas con respuesta aceptada; consultas sin respuesta en la portada.
- Las notas de rutas (Bloque 4) se muestran también en el foro, en la categoría de la ruta.
- XP por respuesta aceptada; insignias de comunidad.

**Acepta si:** solo el autor o un lead aceptan la respuesta; texto escapado; paginación de hilos.

## Bloque 16 · Moderación y notificaciones `[x]`

> **Hecho (2026-10-08).** Notas:
> - App `notifications`: `Notification` (con `key` para no repetir avisos), `Announcement`, `notify()` / `notify_leads()` y campana en la cabecera (contador, últimos 6, «Ver todos»; sin JS, con `<details>`). Bandeja en `/avisos/`.
> - Avisos: persona nueva pendiente y credencial enviada a revisión (a responsables); credencial verificada o rechazada, insignia, subida de nivel, respuesta a tu hilo o nota, respuesta aceptada, contenido ocultado y bienvenida (a la persona); anuncios (a todas las personas aprobadas, más banda en la portada hasta su fecha de vencimiento).
> - **Moderación** (`/moderacion/`, solo responsables): personas por aprobar (rol, disciplina y clase; solo el administrador nombra responsables), cola de certificados, reportes, anuncios y **bitácora** (`ModerationLog`). Rechazar a una persona la suspende.
> - Foro y notas: fijar, ocultar con motivo obligatorio (no se borra; los miembros dejan de verlo, los responsables sí), mover, cambiar el título, cerrar y aceptar respuesta con registro; cualquier miembro reporta un mensaje o una nota (no los propios, sin duplicar) y un responsable lo oculta o lo descarta.
> - Las normas del foro van como panel en `/foro/` (no como hilo fijado: evita un hilo con autor inventado).
> - **Pendiente:** avisos de credencial por vencer/vencida (Bloque 6) y el canal de correo (Bloque 8).
- Pantalla **Moderación**: personas por aprobar, certificados por revisar, reportes y bitácora (MODERACION.md).
- Foro: fijar, cerrar, ocultar, mover, reportar.
- App `notifications`: campana con contador, lista y marcar como leída; anuncios globales; `notify()` con canal `in_app`.
- Expedición del equipo (meta mensual) con barra común en la portada.

**Acepta si:** un miembro no puede moderar (403); cada acción de moderación queda en ModerationLog; los anuncios llegan a todos los `approved`; las notificaciones de la tabla de MODERACION se generan.

## Bloque 15 · Teo (asistente) `[x]`

> **Hecho (2026-10-08).** Notas:
> - `apps/assistant`: cliente `httpx` contra NVIDIA NIM (`client.py`, con transporte inyectable para pruebas), búsqueda FTS5 (`search.py`, migración `0002_fts_index`), lista blanca de contexto (`context.py`) y `services.answer()` con límite diario atómico (`BOT_DAILY_LIMIT`) y respuestas de respaldo.
> - Contexto que viaja: la pregunta, fragmentos visibles para todo el equipo (rutas publicadas, recursos, glosarios, notas, hilos y mensajes no ocultos ni borrados, ayuda), el nombre visible y títulos de misiones pendientes. **Nunca** credenciales, correos/logins ni archivos; una prueba lo verifica sobre el payload real. Los resultados se revalidan contra la base, así que lo ocultado después de indexar no sale.
> - El log guarda solo metadatos (persona, tipo, latencia, tokens, código de error): el modelo ni siquiera tiene campos para la pregunta o la respuesta.
> - Teo: widget en la esquina (despierto/durmiendo), página `/teo/` que funciona sin JS, botón «Resumir con Teo» en hilos de 5+ mensajes, botón para abrir una consulta en el foro con la pregunta prellenada, y ayuda en `/ayuda/` (5 guías). 4 sprites nuevos (idle, happy, thinking, sleep).
> - La respuesta del modelo se muestra como texto escapado: no hay Markdown ni enlaces generados por el modelo; los únicos enlaces son las fuentes internas que pone el servidor.
> - `.env` se lee sin dependencias (`config/settings/base.py`), `.env.example` documenta las variables; la clave no se versiona.
> - **Pendiente:** probar con una clave real (la crea la persona en build.nvidia.com y rota la que se pegó en el chat), elegir `NIM_MODEL` tras probar el español, accesorio de Teo por mundo y la expresión «celebra».
- App `assistant` según BOT.md: widget HTMX con sprite, `/teo/ask`, índice FTS5 (`rebuild_teo_index`), cliente `httpx` a NIM, lista blanca de contexto, límite diario y modo dormido.
- Sprites de Teo: base, 4 expresiones y atuendos de los mundos existentes (skill `sprite-8bit`).
- Botones "Resumir con Teo" en hilos y "Abrir consulta" cuando no sabe.

**Acepta si:** las pruebas con `httpx.MockTransport` pasan (ok, timeout, 401, 429); **ningún** campo de `credentials` ni `login` aparece en el payload; con `BOT_ENABLED=False` el sitio funciona igual; el log no guarda texto.

## Bloque 6 · Vencimientos y exportación de evidencia `[x]`

> **Hecho (2026-10-08).** Notas:
> - Vencimientos: indicadores *por vencer* y *vencida* en listados y detalle (ya existían), página `/certificados/vencimientos/` (propias; los responsables ven además las del equipo) y `manage.py check_expirations` (tarea diaria) que avisa a la persona y a los responsables **una sola vez** por credencial y fecha (D29) y recalcula lo que depende de la vigencia: las *Alas DGAC* se apagan al vencer y el XP se conserva (D27).
> - Exportación (solo responsables): `/certificados/exportar/` con selección por personas, plataformas, tipos y habilidades (solo verificadas o todas), vista previa y descarga de un ZIP con los archivos + `evidencia.xlsx` (fechas tipadas, columnas con ancho, celdas que empiezan con `=`, `+`, `-` o `@` neutralizadas contra inyección de fórmulas). Tope de 500 credenciales y 300 MB; nombres dentro del ZIP generados. Cada exportación queda en la bitácora de moderación.
> - **Desviación:** el ZIP se arma al vuelo y no se guarda, así que no hay nada que limpiar a las 24 h (más seguro que dejar datos personales en disco).
> - Dependencia nueva justificada: `openpyxl` (ya listada en ARQUITECTURA).
> - **Pendiente:** programar `check_expirations` en systemd (Bloque 8) y vencimientos en el tablero del equipo (Bloque 7).
- Indicadores `expires_soon` / `is_expired` en listados, tablero y hoja de personaje (las *Alas* se apagan al vencer).
- Exportación:
  - selección por personas, plataformas, tipos o habilidades;
  - genera un ZIP con los archivos + `evidencia.xlsx` (persona, credencial, tipo, emisor, ID, emisión, vencimiento, URL, estado);
  - limpieza de los ZIP a las 24 h.

**Acepta si:** la XLSX abre en Excel con columnas y fechas tipadas; solo los leads exportan; los archivos del ZIP coinciden con la selección.

## Bloque 7 · Tablero del equipo `[x]`

> **Hecho (2026-10-08).** Notas:
> - `/equipo/`: avance por ruta y persona (calculado **en lote**, con una prueba que lo compara con el cálculo de cada mundo), últimas notas, credenciales recientes, por vencer y vencidas. Todo respeta la visibilidad del repositorio (de otras personas solo lo verificado y visible al equipo; los responsables ven todo).
> - `/equipo/matriz/`: personas × habilidades con el número de credenciales verificadas que las respaldan, filtrable por atributo (MOD, CAP, ANA, DOC, NOR, COL).
> - `/equipo/kit/<ruta>/`: kit del equipo y plan de implementación con **Gantt por fases** y casillas compartidas (`SharedCheck`: la marca el equipo una sola vez y queda quién y cuándo). Sin JS funciona igual (formularios).
> - Rendimiento: con 30 personas y 300 credenciales, el tablero y la matriz cargan en menos de 1,5 s con menos de 60 consultas (prueba incluida).
> - **Desviación:** la matriz no suma «rutas completadas» (las rutas aún no declaran habilidades); queda anotado para cuando existan.
> - **Pendiente:** matriz exportable y filtros por vendor.
- Avance por ruta y persona, últimas notas, credenciales recientes, por vencer y vencidas.
- Matriz de competencias (personas × habilidades) desde credenciales verificadas y rutas completadas.
- Kit y plan de implementación compartidos (SharedItem/SharedCheck) con Gantt, como en el prototipo.

**Acepta si:** el tablero carga en < 1 s con 30 personas y 300 credenciales de prueba (factory-boy).

## Bloque 9 · Documentos `[x]`

> **Hecho (2026-10-08).** Notas:
> - App `library`: `Document` (tipo, disciplinas, etiquetas, descripción, dueño, restringido) y `DocumentVersion` (archivo privado, SHA-256, tamaño, notas, quién subió). Una restricción de base de datos garantiza **una sola versión vigente** por documento.
> - Páginas: `/documentos/` (búsqueda, tipo, disciplina y etiqueta, paginado de 20), subir, ver con historial, editar, subir versión (queda como la vigente), marcar una versión anterior como vigente y eliminar.
> - Archivos: lista de extensiones (pdf, imágenes, Office, dwg/dxf/dgn, rvt/rte/rfa/rft, ifc, txt/csv), firma real cuando el formato la tiene, máx. 50 MB, nombres generados, sin URL pública y descarga siempre como adjunto (`octet-stream`, `nosniff`). Un archivo borrado se retira del disco al confirmar la transacción.
> - Permisos: un documento restringido responde 404 a miembros (no revela que existe); solo su dueño y los responsables editan, suben versiones y borran.
> - **Pendiente:** vista previa de PDF/imágenes en línea (hoy solo descarga) y que Teo cite documentos no restringidos.
- `library`: documentos con versiones, filtros por disciplina, tipo y etiqueta; descarga por vista con permiso.

**Acepta si:** subir una versión nueva deja una sola vigente y conserva el historial; un documento restringido → 403 a miembros.

## Bloque 11 · Conocimiento y mejoras `[x]`

> **Hecho (2026-10-08).** Notas:
> - App `knowledge`: `Article` (lección, procedimiento o pregunta frecuente; borrador o publicado; disciplinas; consulta de origen) y `Improvement` (Idea → Plan → Ejecución → Resultado).
> - **Markdown seguro sin dependencias** (`apps/core/markdown.py`, filtro `|md`): se escapa todo primero y solo se agregan títulos, párrafos, listas, citas, código, negrita y enlaces `https://`, `http://` o rutas locales; nada de `javascript:`, `data:`, imágenes ni HTML propio. 18 cargas de XSS en las pruebas.
> - «Convertir en artículo» en las consultas con respuesta aceptada (solo quien abrió la consulta o un responsable; no con hilos o respuestas ocultas): precarga la pregunta y la respuesta y deja enlazada la consulta de origen.
> - Tablero de mejoras por etapa (`/conocimiento/mejoras/`): cualquiera propone; solo un responsable mueve de etapa y asigna a quién está a cargo; *Resultado* exige contar qué se logró; la persona que propuso recibe un aviso por cada cambio de etapa.
> - Los artículos publicados entran al índice de Teo; los borradores no, y un artículo despublicado después de indexar deja de salir (se revalida).
> - **Pendiente:** historial de ediciones de un artículo y comentarios.
- Artículos (Markdown sanitizado) y propuestas de mejora con etapas Idea → Plan → Ejecución → Resultado.
- Acción "convertir consulta resuelta en artículo". Los artículos entran al índice de Teo.

**Acepta si:** el Markdown sale sin HTML peligroso; hay tablero de mejoras por etapa.

## Bloque 8 · Despliegue y migración `[x]`

> **Hecho (2026-10-08).** Notas:
> - `deploy/install.sh` (idempotente): usuario `centro`, código en `/opt/aeroacademy`, `uv sync`, `/etc/centro/env` con `SECRET_KEY` aleatoria (solo la primera vez, permisos 640), `collectstatic`, `migrate`, `seed_catalog`, servicio `centro.service` (gunicorn en `127.0.0.1:8000`, con endurecimiento de systemd), comprobación de `/healthz` y `tailscale serve --bg 8000`. Nunca usa `funnel` (una prueba lo vigila).
> - Tareas diarias con timers de systemd: respaldo (`sqlite3 .backup` + `tar` de los archivos privados, 30 días, permisos 077) y `check_expirations` (Bloque 6).
> - `/healthz`: responde sin identidad **solo** desde el proxy local; lo demás sigue exigiendo Tailscale.
> - `manage.py import_legacy --db ruta.db [--dry-run]`: importa personas (aprobadas), avance, meta, notas (con su fecha original, sin XP ni avisos) y casillas del kit y plan desde el prototipo. Idempotente (`Note.legacy_id`), en una transacción, con la base de origen abierta en solo lectura y un resumen de lo omitido.
> - `notify()` deja el gancho `email-hook` que solo escribe una línea en el log, sin contenido.
> - `docs/OPERACION.md`: instalación, primera administradora, respaldos y cómo restaurar, importación y tareas.
> - **Pendiente:** probar `install.sh` en una VM real (aquí solo se validó su contenido) y activar el correo cuando se decida.
- `deploy/install.sh`, `centro.service`, respaldo diario (DB + media), `README` de operación.
- `import_legacy` desde el `ruta.db` del prototipo.
- Gancho de correo en `notify()` (solo registra en log).

**Acepta si:** una instalación limpia en una VM Ubuntu deja el sitio en la URL de `tailscale serve`; `import_legacy` es idempotente.

---

## Después del MVP (no implementar aún)
- Mundos `survey`, `mechanical` y `aero`, con sus rutas: Trimble TBC / Geocom, ReCap y nubes de puntos, normativa DGAC para pilotos RPA.
- Más rutas: Civil 3D, ArcGIS Pro, Primavera P6.
- Correo semanal con vencimientos y avance.
- Importar credenciales e insignias desde Credly.
- Ficha de competencias por persona en PDF para licitaciones.
- Temporadas, mapa del gremio y duelos de quiz (REFERENCIAS_DISENO).
