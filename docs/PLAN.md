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

## Bloque 5 · Repositorio de credenciales + Ruta Bentley (mundo Civil) `[ ]`
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

## Bloque 13 · Motor de juego `[ ]`
- App `gamification`: XPEvent, Badge, PersonBadge, Title, AvatarItem (MODELO_DATOS).
- `services.award()` / `revoke()` invocados desde los services de `progress`, `credentials` y `community` (sin signals ocultos).
- Motor de reglas de insignias: `count`, `path_complete`, `distinct_vendors`, `streak`, `credential_kind`, `manual`.
- Cálculo de nivel y título según GAMIFICACION; racha semanal.
- Cabecera: nivel en Press Start 2P, barra de XP y título; *toast* de insignia y modal de subida de nivel (respeta `prefers-reduced-motion`).

**Acepta si:** marcar y desmarcar no duplica XP; rechazar o editar una credencial verificada revoca su XP e insignia; cada tipo de regla tiene prueba; el nivel coincide con la tabla de GAMIFICACION.

## Bloque 14 · Hoja de personaje `[ ]`

> **Adelanto:** el generador de avatares pixel-art ya existe (`apps/gamification/avatars.py`, con pruebas) y su
> galería está en `design/avatares/`. Este bloque lo conecta: componente `{% avatar person size=32 %}`,
> editor de la hoja y validación de piezas desbloqueadas con `clean_config(..., unlocked=...)`. Ver `docs/AVATARES_PIXEL.md`.
- Perfil editable: titular, bio, disciplina, clase, título elegido (solo entre desbloqueados), enlaces y avatar 8-bit por capas (solo items desbloqueados).
- Vista profesional y vista de juego (GAMIFICACION): atributos en hexágono, vitrina de insignias, árbol de habilidades por vendor, línea de actividad.
- Directorio del equipo con tarjetas de personaje.

**Acepta si:** solo el dueño edita su hoja; no se puede elegir un título o un accesorio bloqueado (validación en el servidor); los atributos coinciden con las credenciales verificadas; no hay desborde a 390 px.

## Bloque 12 · Portada Academia `[~]`

> **12a · Bienvenida: hecha (2026-10-08).** Ventana de inicio según `design/academia/index.html`: hero con las
> cinco disciplinas, saludo con el nombre, 7 módulos (con estado según su bloque), rutas por disciplina desde la
> base, banda del equipo, **auspicio de Suite Aero** y valores. El auspicio también va en el pie de todas las páginas.
> Pruebas en `tests/test_welcome.py`. **12b (pendiente):** XP y nivel en la cabecera, misión sugerida, Teo,
> tablón del gremio y contadores vivos, cuando existan los bloques 13, 15 y 16.
- Portada según `design/academia/index.html`:
  - disciplinas con fotos;
  - módulos enlazando a cada app;
  - rutas por vendor y disciplina;
  - banda del equipo y valores.
- Suma: XP y nivel de la persona, **misión sugerida**, Teo (estático hasta el Bloque 15), **tablón del gremio** y contadores reales (consultas abiertas, credenciales por vencer, certificados por revisar para el lead).

**Acepta si:** coincide visualmente con la referencia en escritorio y no desborda a 390 px; la misión sugerida corresponde al avance real.

## Bloque 4 · Notas del equipo `[ ]`
- Notas por ruta, nivel y recurso; respuestas; borrado lógico solo por el autor.
- Cada mundo muestra la nota con su forma propia (nube de revisión, estaca anotada…).
- Bitácora con filtros (tipo, ruta, nivel). XP por nota útil (límite diario).

**Acepta si:** pruebas de permisos (no borrar notas ajenas); texto escapado (sin HTML inyectado); el límite diario de XP se respeta.

## Bloque 10 · Foro y consultas `[ ]`
- Hilos y posts por categoría y disciplina; consultas con respuesta aceptada; consultas sin respuesta en la portada.
- Las notas de rutas (Bloque 4) se muestran también en el foro, en la categoría de la ruta.
- XP por respuesta aceptada; insignias de comunidad.

**Acepta si:** solo el autor o un lead aceptan la respuesta; texto escapado; paginación de hilos.

## Bloque 16 · Moderación y notificaciones `[ ]`
- Pantalla **Moderación**: personas por aprobar, certificados por revisar, reportes y bitácora (MODERACION.md).
- Foro: fijar, cerrar, ocultar, mover, reportar.
- App `notifications`: campana con contador, lista y marcar como leída; anuncios globales; `notify()` con canal `in_app`.
- Expedición del equipo (meta mensual) con barra común en la portada.

**Acepta si:** un miembro no puede moderar (403); cada acción de moderación queda en ModerationLog; los anuncios llegan a todos los `approved`; las notificaciones de la tabla de MODERACION se generan.

## Bloque 15 · Teo (asistente) `[ ]`
- App `assistant` según BOT.md: widget HTMX con sprite, `/teo/ask`, índice FTS5 (`rebuild_teo_index`), cliente `httpx` a NIM, lista blanca de contexto, límite diario y modo dormido.
- Sprites de Teo: base, 4 expresiones y atuendos de los mundos existentes (skill `sprite-8bit`).
- Botones "Resumir con Teo" en hilos y "Abrir consulta" cuando no sabe.

**Acepta si:** las pruebas con `httpx.MockTransport` pasan (ok, timeout, 401, 429); **ningún** campo de `credentials` ni `login` aparece en el payload; con `BOT_ENABLED=False` el sitio funciona igual; el log no guarda texto.

## Bloque 6 · Vencimientos y exportación de evidencia `[ ]`
- Indicadores `expires_soon` / `is_expired` en listados, tablero y hoja de personaje (las *Alas* se apagan al vencer).
- Exportación:
  - selección por personas, plataformas, tipos o habilidades;
  - genera un ZIP con los archivos + `evidencia.xlsx` (persona, credencial, tipo, emisor, ID, emisión, vencimiento, URL, estado);
  - limpieza de los ZIP a las 24 h.

**Acepta si:** la XLSX abre en Excel con columnas y fechas tipadas; solo los leads exportan; los archivos del ZIP coinciden con la selección.

## Bloque 7 · Tablero del equipo `[ ]`
- Avance por ruta y persona, últimas notas, credenciales recientes, por vencer y vencidas.
- Matriz de competencias (personas × habilidades) desde credenciales verificadas y rutas completadas.
- Kit y plan de implementación compartidos (SharedItem/SharedCheck) con Gantt, como en el prototipo.

**Acepta si:** el tablero carga en < 1 s con 30 personas y 300 credenciales de prueba (factory-boy).

## Bloque 9 · Documentos `[ ]`
- `library`: documentos con versiones, filtros por disciplina, tipo y etiqueta; descarga por vista con permiso.

**Acepta si:** subir una versión nueva deja una sola vigente y conserva el historial; un documento restringido → 403 a miembros.

## Bloque 11 · Conocimiento y mejoras `[ ]`
- Artículos (Markdown sanitizado) y propuestas de mejora con etapas Idea → Plan → Ejecución → Resultado.
- Acción "convertir consulta resuelta en artículo". Los artículos entran al índice de Teo.

**Acepta si:** el Markdown sale sin HTML peligroso; hay tablero de mejoras por etapa.

## Bloque 8 · Despliegue y migración `[ ]`
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
