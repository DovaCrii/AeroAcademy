# Centro de administración · plan

Rama `centro-de-administracion` (desde `main`, `df9042a`). Plan del `disenador` (Opus 5.5 medio) para un implementador
`bloque-dev` (Sonnet 5.5 medio) y el `verificador` (Haiku 5.5 medio). **No implementa nada**: las preguntas de la
sección 6 son de la dueña y no se deciden aquí.

## 0. Estado de la implementación (2026-10-20)

Decisión registrada como **D42** en `docs/DECISIONES.md` (respuestas de la dueña a Q1–Q11). Implementado en el árbol de
trabajo de la rama `centro-de-administracion` (sin commit ni push todavía):

- [x] **P0-1 · Centro con Situación y enlaces** (`/administracion/`, `apps/core/admin_*.py`, `admin.css`, `tests/test_admin_center.py`).
- [x] **P0-2 · Cuentas** (`/administracion/cuentas/` y acciones POST: aprobar, rechazar, rol, suspender, reactivar,
  enlace personal, enlace del equipo; `tests/test_admin_accounts.py`).
- [x] **P1-1 · Servidor** (salud, respaldo, versión, puerta pública, cursos privados; `deploy/install.sh` escribe
  `.deployed-version`; `tests/test_admin_server.py`).
- [x] **P1-2 · Registro de tareas** (`core.TaskRun`, `taskruns.record_run` en `check_expirations`, `teo_seguimiento`,
  `revisar_enlaces`, `reindex_assistant`, `cargar_cursos_privados`, `seed_catalog`; `tests/test_taskruns.py`).
- [x] **P1-3 · Por dónde entra cada cuenta** (`accounts.LoginTrace` + señal `user_logged_in`; `tests/test_login_trace.py`).
- [x] **P1-4 · Bitácora de solo lectura** (`/administracion/bitacora/`; `tests/test_admin_log.py`).
- [ ] **P2-1 · Menú** (`navigation.py` y `base.html`): **pendiente**. Otro cambio está editando el menú de usuario
  («Salir» para todas las sesiones). Mientras tanto el Centro se abre por URL (`/administracion/`) y con un enlace en
  las cabeceras de `/moderacion/` y `/equipo/personas/`. Al hacerlo: «Centro de administración» en el menú de usuario
  (lead y admin, fuera de la puerta pública), «Administración» en «Más» reemplazando a «Moderación» y
  `NavItem.tailnet_only` (arregla H2).
- [ ] **P2-2 · Opcionales:** 403 → 404 en las pantallas de lead/admin de otros dueños (Q3, aprobado: toca
  `team/views.py`, `community/moderation_views.py` y `credentials/views.py` y sus pruebas, PR aparte). La huella del
  respaldo (Q6) se descartó y el archivo de versión (Q7) ya está hecho.

**Diferencias con el diseño de arriba (decididas por la dueña o por límites reales):**

- Q1: el responsable ve solo reportes y certificados por revisar, y la bitácora; **Cuentas, vencimientos del equipo,
  enlace del equipo y Servidor son solo del admin** (el diseño le daba además la lista de cuentas).
- Las consultas se miden **sin la cabecera de toda página** (sesión, persona, anillo de XP y campana: ~10 consultas que
  ponen los procesadores de contexto en cualquier pantalla; la prueba las descuenta con `tests/conftest.own_queries`).
  El Centro propio, con todos sus bloques, usa 9 consultas (topes de prueba: 12 y 15), las Cuentas 3 (tope 8) y la
  bitácora 2 (tope 6); en todos los casos **no crecen** con los datos (prueba con 1 y con 40–120).
- La lista de cuentas va paginada de 50 y usa la inicial del nombre en lugar de la ilustración del avatar (el avatar
  cuesta consultas por persona).
- Los enlaces recién generados viven en la **sesión** de quien los generó hasta su primera lectura (como ya hace
  `/equipo/personas/`); nunca en la base de personas ni en la bitácora.
- Registrar la vía de entrada suma 2 consultas a la **primera petición de cada sesión** (la entrada: un UPDATE y, la
  primera vez de la persona, un INSERT; sin transacción propia). Por eso se subieron 2 consultas los topes de
  `tests/test_credentials.py::test_query_counts_stay_flat` (25 → 27) y `tests/test_forum.py::test_list_query_count_is_flat`
  (34 → 36): ambas miden la primera petición de un cliente nuevo. Las demás peticiones no cambian.
- La acción «Rechazar» sigue siendo **suspender** a una pendiente (igual que en `/moderacion/`).

## 1. Pedido

- **2026-10-19.** La dueña mostró el «Centro de administración» de AeroControl (Situación con 4 contadores, Trabajos
  programados, Salud, Último respaldo, enlaces agrupados con icono + título + explicación + flecha y un botón
  «Administración técnica avanzada» que abre el admin de Django). En AeroAcademy quien administra hoy salta entre
  `/equipo/personas/`, `/moderacion/`, `/certificados/revisar/`, `/seguridad/2fa/`, `/admin/` y comandos en la VM.
  Quiere **un solo lugar, más amigable y simple, visible solo para quien administra**.
- **Aclaración 2026-10-20.** «Que **todo** se maneje y se entienda ahí», con dos prioridades:
  1. **Estado del servidor:** salud del servicio y de la base, últimas ejecuciones de tareas, último respaldo, versión
     desplegada, si la puerta pública está encendida y almacenamiento.
  2. **Sobre todo, el manejo de cuentas:** ver de un vistazo quién está pendiente, activa, suspendida o sin rol;
     aprobar, cambiar rol, suspender, generar o revocar el enlace del equipo y los enlaces personales; saber quién
     entra por Tailscale y quién con contraseña; y entender el estado de cada cuenta en lenguaje simple.
  Orden pedido: **Situación y Cuentas primero**, lo demás debajo. Se mantienen las reglas de seguridad.

## 2. Inventario medido (código de `main` a 2026-10-20)

### 2.1 Pantallas y acciones de administración que ya existen

| Ruta | Vista | Quién | Respuesta si no corresponde | Puerta pública |
|---|---|---|---|---|
| `/moderacion/` | `community.moderation_views.dashboard`: personas pendientes (con correo), n.º en la cola de certificados, reportes abiertos (máx. 50), anuncios, bitácora (50) | lead + admin | **403** (`PermissionDenied`) | 404 (prefijo) |
| `POST /moderacion/personas/<pk>/aprobar/` · `/rechazar/` | aprueba (rol member/lead, disciplinas, clase) · rechaza = **suspende** | lead (lead solo da `member`) | 403 | 404 |
| `POST /moderacion/reportes/<pk>/resolver/` | ocultar o descartar | lead | 403 | 404 |
| `POST /moderacion/anuncios/nuevo/` · `/<pk>/retirar/` | anuncios | lead | 403 | 404 |
| `/equipo/personas/` | `team.views.people`: plantel por área (`onboarding.roster`, excluye suspendidas), enlace del equipo vigente (solo admin), textos de invitación | lead + admin | 403 | 404 |
| `POST /equipo/personas/<pk>/` | `person_update`: rol, disciplinas, cargo (lead solo toca miembros y no da roles) | lead | 403 | 404 |
| `POST /equipo/personas/<pk>/invitada/` | marca «invitada a Tailscale» | lead | 403 | 404 |
| `POST /equipo/personas/<pk>/enlace/` | enlace personal de registro/restablecimiento (D34, se muestra una vez vía sesión) | admin | 403 | 404 |
| `POST /equipo/personas/enlace-equipo/` · `/revocar/` | enlace del equipo (D35) | admin | 403 | 404 |
| `/equipo/personas/agregar/` | importar CSV (simular/importar) | admin | 403 | 404 |
| `/certificados/revisar/` y `POST /certificados/<pk>/revisar/` | cola de revisión | lead (`can_review`) | 403 | **abierta** (D39, riesgo aceptado) |
| `/certificados/vencimientos/?equipo=1` | vencimientos del equipo (`WARNING_DAYS` = 60) | lead ve el equipo; miembro, lo suyo | — | abierta |
| `/seguridad/2fa/` | TOTP propio | cualquiera con sesión | — | 404 (prefijo y vista) |
| `/admin/` | Django admin; `PersonAdmin` con acciones aprobar, **suspender**, member/lead/admin | `is_staff` (= admin) | login del admin | 404 |
| `/healthz` | `SELECT 1` → `{"ok": true}` | solo desde el proxy local | 403 | idem |

**Hallazgos del inventario** (se listan, no se arreglan fuera de alcance):

- H1. Las vistas de lead/admin responden **403**, no 404 como pide `AGENTS.md` («lo restringido responde 404»).
- H2. En la puerta pública, `navigation.py` muestra «Moderación» en «Más» a un lead: el enlace lleva a un 404.
  `NavItem` no sabe de puertas.
- H3. **Suspender a una persona aprobada y reactivar a una suspendida solo se puede en `/admin/`** (acción de
  `PersonAdmin`) o rechazando a una pendiente. No hay botón en la interfaz propia.
- H4. `onboarding.roster()` excluye a las suspendidas: hoy no hay ninguna pantalla propia que las liste.
- H5. No queda registro de **por dónde** entró alguien (Tailscale o contraseña): la sesión lo sabe
  (`BACKEND_SESSION_KEY`), la base no. Sí se sabe si **tiene contraseña** (`has_usable_password()`), `last_login`,
  si tiene TOTP confirmado (`TotpDevice.confirmed_at`) y si fue marcada «invitada a Tailscale» (`TeamMember`).
- H6. `/certificados/revisar/` está abierta en la puerta pública (decisión D39); el Centro no debe cambiar eso.

### 2.2 Comandos de gestión y tareas programadas

| Comando | Qué hace | Programado | Rastro que la app puede leer hoy |
|---|---|---|---|
| `check_expirations` | avisos de vencimiento + recálculo | `centro-expiry.timer` diario 07:00 | ninguno fiable (solo avisos si hubo vencimientos) |
| `teo_seguimiento` | avisos semanales de Nala | `centro-teo.timer` lunes 09:00 | ninguno fiable |
| `deploy/backup.sh` | `sqlite3 .backup` + `tar` de `media/`, retención 30 días | `centro-backup.timer` diario 03:30 | **los archivos** `db-AAAA-MM-DD.sqlite3` y `media-AAAA-MM-DD.tar.gz` en `/var/backups/centro` |
| `avisar_fallo <unidad>` | lo llama systemd (`OnFailure=`): aviso `task_failed` a los leads, clave `fallo:<unidad>:<fecha>` | al fallar cualquier unidad | **sí**: `Notification(kind="task_failed")` por unidad y día |
| `revisar_enlaces [--externos]` | CSV en `private/` | a mano (A14) | ninguno en la base |
| `reindex_assistant`, `seed_catalog`, `cargar_cursos_privados`, `cargar_dgac`, `puesta_en_marcha`, `aprobar`, `enlace_equipo`, `enlace_registro`, `importar_equipo`, `teo_probar`, `import_legacy` | carga y mantenimiento a mano | no | ninguno |

### 2.3 Qué puede leer la app de forma segura (sin entrar a la VM)

La app corre como el usuario `centro` (`centro.service`, `ProtectSystem=strict`: todo el sistema de archivos es de
**solo lectura** salvo `/var/lib/centro`, que se puede leer y escribir). `install.sh` crea `/var/backups/centro` con
dueño `centro`, así que el proceso **puede listar y leer** los respaldos (sin escribirlos).

| Dato | ¿Posible hoy? | Cómo (consulta o lectura acotada) |
|---|---|---|
| Personas pendientes / activas / suspendidas / inactivas | Sí | `Person` agrupado por `status` (1 consulta con `Count` condicional) |
| «Sin rol» | Sí | aprobadas **sin grupo** (`groups__isnull=True`): cuentan como miembro pero nadie les asignó rol (p. ej. creadas en `/admin/`) |
| Sin disciplina | Sí | aprobadas sin `disciplines` |
| Aprobadas que nunca entraron | Sí | `last_login IS NULL` |
| Con contraseña / sin contraseña | Sí | `password` no empieza por `!` (= `has_usable_password`), en consulta |
| Entró por Tailscale o por contraseña | **No** | requiere registrar el método (P1-3, modelo nuevo) |
| TOTP activado | Sí | `TotpDevice.confirmed_at` |
| Reportes abiertos | Sí | `Report.status=open` count |
| Certificados por revisar | Sí | `review_queue().count()` |
| Credenciales que vencen en 30 días / vencidas | Sí | `expiry.expiring(days=30).count()`, `expiry.expired().count()` |
| Enlace del equipo vigente, vencimiento, usos | Sí | `team_link.active_link()` (nunca el token) |
| Cursos privados cargados | Sí | carpetas con `ruta.json` en `PRIVATE_COURSES_DIR` frente a slugs en `LearningPath` (solo cuentas, sin rutas) |
| Base de datos responde, modo WAL, tamaño | Sí | `SELECT 1`, `PRAGMA journal_mode`, `os.path.getsize` |
| Almacenamiento: espacio libre del disco de datos, `media/` escribible | Sí | `shutil.disk_usage(MEDIA_ROOT)`, `os.access(W_OK)` |
| Caché de límites de intentos funciona | Sí | `cache.set/get` de una clave fija (es la que protege `/entrar/`) |
| Nala configurada | Sí | `assistant.client.is_configured()` (sin llamar a la API) |
| Último respaldo diario | Sí | nombre, fecha, tamaño y antigüedad del `db-*.sqlite3` y `media-*.tar.gz` más recientes; n.º retenidos; último `pre-actualizar-*` |
| Huella sha256 del respaldo | Posible, caro | hay que leer el archivo entero: solo con caché por (nombre, tamaño, mtime) y mostrando 12 caracteres (P2, pregunta Q6) |
| Fallas de tareas programadas | Sí | `Notification(kind="task_failed")` del propio admin, la más reciente por unidad |
| **Última ejecución correcta** de cada tarea | **No** | requiere registrar ejecuciones (P1-2, modelo nuevo) |
| Versión desplegada | Parcial | `/opt/aeroacademy` se copia sin `.git`. `actualizar.sh` deja `/opt/aeroacademy.prev.info` con `commit_after` y `taken_at` (solo tras la primera actualización). Lo robusto es que el instalador escriba un archivo de versión (cambio de despliegue: Q7) |
| Puerta pública encendida | Parcial | el proceso de la tailnet no ve la configuración de Funnel. Sí puede comprobar que **el servicio** `centro-public` responde: `GET http://127.0.0.1:8011/healthz` con 0,5 s de espera y caché de 60 s. Si el Funnel está publicado en Tailscale **no** es verificable desde la app y se dice así |
| Bitácora de moderación | Sí | `ModerationLog` (actor, acción, objeto, resumen, fecha) |
| Estado de `systemctl`, `journalctl` | **No** | ni se intenta: exigiría privilegios |

**Estimación de lo que no existe:**

- **Registro de ejecuciones** (`TaskRun`: nombre, último inicio, último fin, resultado, resumen de ≤ 200 caracteres
  solo con cifras): modelo + migración + un decorador para los comandos + pruebas. ~150 líneas + ~120 de pruebas,
  **un PR chico**. `backup.sh` no escribe en la base: su rastro son sus archivos (no hace falta tocarlo).
- **Registro del método de entrada** (`LoginTrace`, 1:1 con `Person`, **sin tocar `Person`**: última entrada por
  Tailscale, última con contraseña, última por la puerta pública), alimentado por la señal `user_logged_in` (se dispara
  una vez por sesión, tanto con `RemoteUserMiddleware` como con `/entrar/`). ~100 líneas + pruebas, **un PR chico**.

## 3. Diseño recomendado

### 3.1 Ruta, acceso y quién ve qué

- **Ruta:** `/administracion/` (centro) y `/administracion/cuentas/` (manejo de cuentas), más
  `/administracion/bitacora/` (P1). Nombres de URL en inglés: `core:admin_center`, `core:admin_accounts`,
  `core:admin_log` (ver 5.0).
- **Fuera de la puerta pública:** se agrega `"/administracion/"` a `PUBLIC_BLOCKED_PREFIXES` **y** la vista
  comprueba `request.public_door` (doble llave, como `/seguridad/2fa/`).
- **404, no 403**, para quien no tiene acceso (miembro, pendiente o puerta pública). Mismo texto que cualquier 404.

| Bloque | admin | lead (recomendado, Q1) | miembro |
|---|---|---|---|
| Situación: cuentas pendientes, reportes, certificados por revisar, vencimientos | sí | sí (ya los ve hoy) | 404 |
| Situación: servidor (salud, tareas, respaldo, versión, puerta pública) | sí | no | 404 |
| Cuentas: listado con estado | sí, todas | sí, solo lectura de estados + aprobar/rechazar pendientes como `member` (lo que hoy hace en `/moderacion/`) | 404 |
| Cuentas: cambiar rol, suspender, reactivar, enlaces personales, enlace del equipo | sí | no | 404 |
| Servidor, Sistema, `/admin/`, bitácora | sí | bitácora sí (ya la ve en `/moderacion/`) | 404 |

Una sola función decide: `admin_center.access(user, request) -> "admin" | "lead" | None`; `None` → `Http404`.
Si la dueña prefiere **solo admin** (Q1), basta con que esa función devuelva `None` para el lead.

### 3.2 Cómo se llega

- Menú de usuario (chip con avatar): «**Centro de administración**» (lead y admin, solo en la tailnet), justo
  sobre «Mi cuenta». Es la entrada principal: 2 clics desde cualquier página.
- «Más» (y hamburguesa): «**Administración**» reemplaza a «Moderación» (que queda como enlace dentro del Centro y
  sigue en su URL). Se oculta en la puerta pública (arregla H2).
- Enlace «Ir al Centro de administración» en la cabecera de `/moderacion/` y `/equipo/personas/` (sin tocar
  `base.html`), para quien llega por costumbre.

### 3.3 Esquema de la pantalla `/administracion/` (orden pedido: Situación y Cuentas primero)

```
┌ Cabecera de siempre (base.html) ─────────────────────────────────────────────────────────────┐
│ page-head  «Centro de administración»                                                        │
│            «Las cuentas, el servidor y las herramientas del equipo, en un solo lugar.»       │
│            chip: «Puerta de la tailnet» · «Datos al 20/10 09:14»                             │
├ 1. SITUACIÓN (tarjetas-contador; cada una es un enlace a donde se resuelve) ─────────────────┤
│ [ 3 ]  personas esperando aprobación      → /administracion/cuentas/?estado=pendiente        │
│ [ 1 ]  reportes del foro sin resolver     → /moderacion/#m-reports                           │
│ [ 2 ]  certificados por revisar           → /certificados/revisar/                           │
│ [ 4 ]  credenciales vencen en 30 días     → /certificados/vencimientos/?equipo=1             │
│ [ ✓ ]  servidor: todo en orden  | [ ! 2 avisos ] → #servidor               (solo admin)      │
│ [ 9 d] enlace del equipo vigente, vence en 9 días · 5 inscripciones → #enlace (solo admin)   │
│   Contador en 0 = tarjeta tranquila («Nada pendiente»); > 0 = borde ámbar y texto de acción.  │
├ 2. CUENTAS ───────────────────────────────────────────────────────────────────────────────────┤
│ Resumen en una línea de chips-filtro (enlaces GET, sin JS):                                  │
│  Pendientes 3 · Activas 18 · Nunca entraron 2 · Suspendidas 1 · Sin rol 0 · Sin disciplina 4 │
│ «Pendientes de aprobar» (máx. 5 filas; nombre, «pidió acceso hace 2 días», botones Aprobar   │
│  como miembro / Rechazar = POST con CSRF a las URL que ya existen) + «Ver todas las cuentas →»│
│ Bloque «Enlace del equipo» (admin): estado en palabras, Generar (7/14/30) · Revocar          │
│  (POST a las URL existentes; el enlace se muestra una sola vez, como hoy)                    │
├ 3. SERVIDOR (admin) id="servidor" ────────────────────────────────────────────────────────────┤
│ Salud ............ ✓ Base de datos responde (modo WAL, 48 MB)                                │
│                    ✓ Archivos privados: se puede escribir · disco con 71 % libre             │
│                    ✓ Límite de intentos de entrada (caché) funciona                          │
│                    ✓ Nala configurada  /  · Nala dormida (sin clave)                         │
│ Tareas ........... Respaldo diario (03:30) ✓ hoy 03:30 · Vencimientos (07:00) ✓ hoy 07:00    │
│                    Seguimiento de Nala (lunes 09:00) ✓ lun 19/10 · Revisión de enlaces: a mano│
│                    (estado «Sin registro todavía» hasta P1-2; «Falló el 18/10» si hay aviso) │
│ Último respaldo .. db-2026-10-20 · hoy 03:30 · 48 MB  |  media-2026-10-20 · 312 MB           │
│                    30 respaldos guardados · último previo a actualizar: 18/10                │
│ Versión .......... a1b2c3d instalada el 18/10 (o «No se puede saber desde la app», Q7)       │
│ Puerta pública ... Servicio en marcha / apagado (el Funnel se revisa en la VM)               │
├ 4. CONTENIDO · 5. COMUNIDAD · 6. CREDENCIALES · 7. SISTEMA (listas de enlaces) ───────────────┤
│ fila = doodle (icono) · título · una línea de explicación · flecha «→»                       │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Secciones de enlaces** (cada fila 1 clic desde el Centro). «Existe» = la URL ya está; «Nuevo» = hay que crearla.

| Sección | Fila | Destino | Estado | Rol |
|---|---|---|---|---|
| Cuentas y accesos | Todas las cuentas | `/administracion/cuentas/` | Nuevo | lead/admin |
| | Agregar personas (CSV) | `/equipo/personas/agregar/` | Existe | admin |
| | Plantel e invitaciones por área | `/equipo/personas/` | Existe | lead/admin |
| | Mi segundo factor (2FA) | `/seguridad/2fa/` | Existe | lead/admin |
| Contenido | Rutas | `/rutas/` | Existe | todos |
| | Catálogo | `/catalogo/` | Existe | todos |
| | Cursos privados: «3 de 3 cargados» / «carpeta no instalada» | dato en la fila + ayuda «se cargan con `cargar_cursos_privados`» | Nuevo (solo dato) | admin |
| Comunidad | Moderación (reportes, foro) | `/moderacion/` | Existe | lead/admin |
| | Anuncios | `/moderacion/#m-ann` (ancla a confirmar en la plantilla) | Existe | lead/admin |
| Credenciales | Por revisar | `/certificados/revisar/` | Existe | lead/admin |
| | Vencimientos del equipo | `/certificados/vencimientos/?equipo=1` | Existe | lead/admin |
| | Exportar evidencia | `/certificados/exportar/` | Existe | lead/admin (confirmar permiso de la vista) |
| Sistema | Bitácora (solo lectura) | `/administracion/bitacora/` | Nuevo | lead/admin |
| | Comprobación de enlaces | dato «última: 12/10, 0 rotos» (con P1-2) + cómo correrla | Nuevo (solo dato) | admin |
| | **Administración técnica avanzada** | `/admin/` (botón secundario al pie, con aviso «para casos que no estén aquí») | Existe | admin |

### 3.4 Pantalla `/administracion/cuentas/` (la prioridad 2 de la dueña)

- **Filtros** por GET (`?estado=pendiente|activa|nunca|suspendida|sin-rol|sin-disciplina&q=`; `q` ≤ 100 caracteres,
  busca en nombre y correo). Sin JS. Orden: pendientes primero, luego por nombre.
- **Una fila por persona** (en 375 px pasa a tarjeta): avatar chico, nombre, correo (solo aquí y solo para lead/admin,
  que ya lo ven hoy), rol en palabras («Miembro», «Responsable», «Admin», «Admin fija» si está en `BOOTSTRAP_ADMINS`),
  y **el estado en una frase**, calculado en el servicio (no en la plantilla):

| Caso | Frase |
|---|---|
| Pendiente | «Pidió acceso hace 2 días. Todavía no puede entrar: apruébala o recházala.» |
| Aprobada, nunca entró, sin contraseña | «Aprobada, aún no entra. Necesita Tailscale o un enlace personal para crear su contraseña.» |
| Aprobada, nunca entró, con contraseña | «Aprobada y con contraseña, pero aún no entra.» |
| Activa | «Entró hace 3 días.» + con P1-3: «por Tailscale» / «con contraseña» / «desde internet (puerta pública)» |
| Activa, lead/admin con TOTP | se agrega el chip «2FA activo» |
| Suspendida | «Sin acceso. Sus datos y certificados se conservan.» |
| Inactiva (`is_active=False`) | «Cuenta desactivada en la administración técnica.» |
| Sin rol | «Sin rol asignado: cuenta como miembro.» |

- **Chips de acceso:** «Contraseña: sí/no», «Tailscale: invitada» (de `TeamMember`), «Último acceso por …» (P1-3).
- **Acciones por fila** (`<form method="post">` con CSRF; cada una con su confirmación en texto, sin JS):

| Acción | Endpoint | ¿Existe? | Quién |
|---|---|---|---|
| Aprobar (rol, disciplinas) / Rechazar | nuevos en `/administracion/cuentas/<pk>/aprobar|rechazar/`, que llaman a `accounts.approve`/`set_role`/`suspend` + `moderation.log` igual que la vista actual | Servicio sí, vista nueva | lead (solo `member`) / admin |
| Cambiar rol | nuevo `/administracion/cuentas/<pk>/rol/` → `onboarding.update_person(role=…)` (ya valida «no tu propio rol», «admin fija») | Servicio sí | admin |
| **Suspender** (aprobada) | nuevo `/administracion/cuentas/<pk>/suspender/` → `accounts.suspend` + log `suspend_person`; prohibido sobre sí misma y sobre admin fija | **Nuevo** (hoy solo en `/admin/`, H3) | admin |
| **Reactivar** (suspendida) | nuevo `/administracion/cuentas/<pk>/reactivar/` → `accounts.approve` + log `reactivate_person` | **Nuevo** (H3) | admin |
| Enlace personal (registro o restablecer contraseña) | nuevo `/administracion/cuentas/<pk>/enlace/` → `onboarding.create_signup_link`; se muestra **una vez** (clave de sesión propia del Centro, como hace `people`) | Servicio sí | admin |
| Enlace del equipo: generar / revocar | nuevos `/administracion/enlace-equipo/` y `/revocar/` → `team_link.generate/revoke` | Servicio sí | admin |

  Se crean vistas finas propias (no se editan las de `team`/`community`, que siguen funcionando igual) para que
  vuelvan al Centro sin tocar redirecciones ajenas y para no cruzar dueños de archivos. Todas: `require_POST`, 404 si
  no hay acceso, redirección fija (sin `next`), mensaje en español con `messages`.

### 3.5 Estilo

- Identidad general (tokens de `tokens.css`, claro y oscuro), **papel recortado** del estilo principal: Situación como
  fila de tarjetas `.card` con contador grande en `--font-mono`, borde `--amber` cuando hay algo pendiente, `--ok` con
  ✓ cuando no; las secciones de enlaces como hojas `.sheet` con filas de icono `{% doodle %}` existente
  (`equipo`, `foro`, `certificados`, `catalogo`, `rutas`, `documentos`, `conocimiento`) y flecha. Sin colores nuevos:
  si hiciera falta un token, se agrega su par a `contrast.py` en el mismo PR.
- Estados del servidor **siempre con texto + símbolo** (✓ / ! / ·), nunca solo color.
- 375 px: tarjetas en una columna, filas de cuentas como tarjetas apiladas, botones de ≥ 44 px.
- CSS en un archivo nuevo `apps/core/static/core/admin.css` cargado con `{% block extra_head %}` (no se toca
  `base.html` ni `components.css`).

## 4. Seguridad y privacidad (aplica a todas las tareas)

1. `/administracion/` en `PUBLIC_BLOCKED_PREFIXES` + chequeo en la vista. Prueba: con la puerta pública, admin → 404
   en cada URL del Centro (GET y POST).
2. 404 para miembro, pendiente, suspendida y anónimo (anónimo: la redirección a `/bienvenida/` de siempre).
3. Solo lectura salvo las acciones de 3.4, todas POST con CSRF y con las mismas reglas de servicio que hoy.
4. **Nada de secretos:** ni token del enlace del equipo (solo estado, vencimiento y usos), ni `SECRET_KEY` ni
   `NIM_API_KEY` (de Nala solo «configurada» o «dormida»); ni secretos TOTP ni códigos de recuperación; ni huellas
   completas (máx. 12 caracteres si se aprueba Q6).
5. **Sin rutas del servidor en pantalla:** de los respaldos se muestra solo el **nombre de archivo** (basename), fecha y
   tamaño; nunca `/var/backups/...`, `MEDIA_ROOT`, `DATABASE_PATH` ni `PRIVATE_COURSES_DIR`. Prueba que busca `/var/`,
   `/opt/` y `private` en el HTML.
6. **Sin contenido de credenciales:** el Centro muestra solo **cuentas** de credenciales (sin títulos, dueños ni
   archivos). Nada del Centro va a Nala, al índice ni a logs (el Centro no registra nada salvo `moderation.log` de las
   acciones). Los resúmenes de `TaskRun` solo llevan cifras (sin nombres ni correos).
7. **Correos de otras personas:** solo en `/administracion/cuentas/` (necesario para identificar la cuenta, y ya
   visibles hoy para lead/admin en `/moderacion/` y `/equipo/personas/`). En `/administracion/` no aparecen correos.
8. Texto de usuarios escapado (nombres, motivos en la bitácora): prueba con `<script>` en `display_name`.
9. **Consultas acotadas:** el Centro hace un número fijo de consultas que no crece con los datos; las cuentas, un
   número fijo con `select_related`/`prefetch_related`; la bitácora, paginada (50).
10. Lecturas de disco y red **acotadas y a prueba de fallas:** cada comprobación de salud con `try/except` que
    devuelve «No se pudo comprobar» (nunca un 500); la sonda a `127.0.0.1:8011` con espera de 0,5 s y caché de 60 s;
    el listado de respaldos con `os.scandir` limitado a los patrones conocidos.

## 5. Plan de implementación (un implementador `bloque-dev`, Sonnet 5.5 medio; PR chicos en orden)

### 5.0 Dónde vive el código

Recomendado: **módulo dentro de `apps/core`** (no una app nueva, que obligaría a tocar `ARQUITECTURA.md`):
`apps/core/admin_center.py` (servicios: `access`, `situation`, `accounts_rows`, `server_status`, `backups`…),
`apps/core/admin_views.py`, `apps/core/admin_urls.py` (incluido desde `config/urls.py` **antes** de `apps.core.urls`),
plantillas `apps/core/templates/core/admin/*.html`, `apps/core/static/core/admin.css`, pruebas
`tests/test_admin_center*.py`. Los modelos nuevos (`TaskRun`, `LoginTrace`) en `apps/core/models.py` y
`apps/accounts/models.py` respectivamente (**modelos nuevos; los existentes no se tocan**).

**Dueños de archivos:** este trabajo es dueño de todo lo anterior. **No toca** `apps/team/views.py`,
`apps/community/moderation_views.py`, `apps/credentials/views.py` ni sus URL. `base.html` y `navigation.py` solo en
el último PR (P2-1), después de que se fusione el trabajo del otro agente sobre el menú de usuario.

### P0 (lo que pidió primero: Situación + Cuentas)

**P0-1 · Centro con Situación y enlaces** (rama `bloque-admin-1-centro`)
- Archivos: `config/settings/base.py` (solo `PUBLIC_BLOCKED_PREFIXES`), `config/urls.py` (un `include`),
  `apps/core/admin_center.py`, `admin_views.py`, `admin_urls.py`, `templates/core/admin/center.html`,
  `static/core/admin.css`, `tests/test_admin_center.py`; un enlace «Ir al Centro» en
  `apps/community/templates/community/moderation.html` y `apps/team/templates/team/people.html` (solo plantilla).
- Enfoque: `access()`; `situation()` con los contadores de 2.3 (pendientes, reportes, por revisar, vencen en 30,
  vencidas, enlace del equipo, estados de cuentas); secciones de enlaces de 3.3 (solo las que ya existen; las nuevas
  aparecen al llegar su PR). El bloque «Servidor» aún no.
- Criterios: (a) admin 200; lead 200 sin bloques de admin; miembro, pendiente y suspendida 404; puerta pública 404
  para admin y lead. (b) **≤ 12 consultas** con 1 o con 40 personas/reportes/credenciales (misma cifra: prueba con
  `django_assert_max_num_queries` en dos tamaños). (c) cada contador > 0 enlaza a su pantalla y en 0 dice «Nada
  pendiente». (d) el HTML no contiene correos, el token del enlace, `/var/`, `/opt/` ni `private`. (e) funciona sin JS,
  375 px, claro y oscuro.

**P0-2 · Cuentas: listado, estado en palabras y acciones** (rama `bloque-admin-2-cuentas`, apilada sobre P0-1)
- Archivos: `admin_center.py` (`accounts_rows`, `account_sentence`), `admin_views.py` (lista + POST de 3.4),
  `admin_urls.py`, `templates/core/admin/accounts.html`, el bloque «Cuentas» de `center.html`, `admin.css`,
  `tests/test_admin_accounts.py`.
- Criterios: (a) filtros por estado devuelven exactamente esas personas (incluidas suspendidas, H4). (b) **≤ 8
  consultas** con 5 o con 60 personas. (c) cada acción: POST con CSRF (GET → 405), 404 si no hay acceso, y las reglas
  de siempre: lead aprueba solo como miembro y no cambia roles ni suspende; nadie se suspende ni se quita el rol a sí
  misma; la admin fija no se suspende ni cambia de rol. (d) suspender corta el acceso (la persona recibe la pantalla
  de suspendida en la siguiente petición) y reactivar lo devuelve; ambas dejan `ModerationLog`. (e) enlace personal y
  del equipo se muestran **una sola vez** y nunca quedan en la base ni en la bitácora (prueba que busca el token).
  (f) `<script>` en `display_name` sale escapado. (g) acciones repetidas no duplican avisos ni registros indebidos
  (aprobar dos veces → la segunda 404 porque ya no está pendiente, como hoy).

### P1 (estado del servidor)

**P1-1 · Salud, respaldo, versión y puerta pública** (rama `bloque-admin-3-servidor`)
- Archivos: `config/settings/base.py` (`BACKUP_DIR = env("BACKUP_DIR", "/var/backups/centro")`,
  `PUBLIC_DOOR_PORT = env("AEROACADEMY_PUBLIC_PORT", 8011)`, `VERSION_FILE`, todos con valor por defecto y sin tocar
  `deploy/`), `admin_center.py` (`server_status`, `latest_backups`, `deployed_version`, `public_door_up`), bloque
  «Servidor» de `center.html`, `tests/test_admin_server.py`.
- Criterios: (a) con `tmp_path` y archivos falsos `db-…`/`media-…`/`pre-actualizar-…` muestra el más reciente, el
  tamaño y el n.º retenido; sin carpeta → «No hay respaldos a la vista»; respaldo de > 36 h → aviso «!». (b) solo
  basenames en el HTML. (c) cada comprobación que lanza excepción → «No se pudo comprobar», 200. (d) la sonda de la
  puerta pública se simula (`monkeypatch`) y se cachea; nunca bloquea más de 0,5 s. (e) la versión sale de
  `VERSION_FILE` si existe, si no de `*.prev.info` (`commit_after`), si no «No se puede saber desde la app».
  (f) el contador «servidor» de Situación suma los avisos. (g) consultas del Centro siguen ≤ 15.

**P1-2 · Registro de ejecuciones de tareas** (rama `bloque-admin-4-tareas`)
- Archivos: `apps/core/models.py` + migración (`TaskRun`), `apps/core/taskruns.py` (decorador o context manager
  `record_run("check_expirations")` que guarda inicio, fin, `ok` y un resumen solo con cifras; un fallo de registro
  nunca hace fallar la tarea), los `handle()` de `check_expirations`, `teo_seguimiento`, `revisar_enlaces`,
  `reindex_assistant`, `cargar_cursos_privados`, `seed_catalog` (una línea cada uno), bloque «Tareas» de
  `center.html`, `tests/test_taskruns.py`.
- Tabla fija de tareas esperadas en código (nombre visible, horario de `deploy/*.timer`, tolerancia): respaldo
  (su evidencia es el archivo, P1-1), vencimientos (26 h), Nala (8 días), revisar enlaces (manual).
- Estado: «✓ hoy 07:00» / «! atrasada (última: …)» / «! falló el …» (si hay `task_failed` posterior al último éxito) /
  «· sin registro todavía».
- Criterios: (a) correr el comando crea o actualiza **una** fila (idempotente por nombre); con excepción queda `ok=False`
  y la excepción se propaga igual (systemd sigue viendo el fallo). (b) el resumen no lleva nombres ni correos (prueba).
  (c) la vista lee todas las tareas en 1 consulta. (d) migración aplicable desde cero.

**P1-3 · Por dónde entra cada cuenta** (rama `bloque-admin-5-entradas`)
- Archivos: `apps/accounts/models.py` (modelo **nuevo** `LoginTrace`, sin tocar `Person`) + migración,
  `apps/accounts/signals.py` (receptor de `user_logged_in`: según `BACKEND_SESSION_KEY` y `request.public_door`
  actualiza `last_tailscale_at` / `last_password_at` / `last_public_at`), `apps/accounts/apps.py` (`ready`),
  `admin_center.py` (frase y chips), `tests/test_login_trace.py`.
- Criterios: entrar por encabezado, por `/entrar/` y por la puerta pública marca el campo correcto; un fallo del
  receptor no impide entrar; sin IP ni agente de usuario guardados; la lista de cuentas sigue ≤ 8 consultas.

**P1-4 · Bitácora de solo lectura** (rama `bloque-admin-6-bitacora`)
- `/administracion/bitacora/`: `ModerationLog` paginado de 50, filtro por acción (lista blanca), sin formularios de
  cambio. Criterios: lead y admin 200, miembro 404, pública 404, ≤ 6 consultas en cualquier página, texto escapado.

### P2 (al final)

**P2-1 · Menú** (rama `bloque-admin-7-menu`; **último**, después de fusionar el trabajo del otro agente sobre el menú
de usuario y rebasar sobre `main`)
- Archivos: `apps/core/navigation.py` (campo `tailnet_only` en `NavItem`; «Administración» reemplaza a «Moderación» en
  `MORE_NAV`; `navigation()` filtra por `request.public_door` — arregla H2), `apps/core/templates/core/base.html`
  (una línea: «Centro de administración» en `.um-pop` para lead/admin fuera de la puerta pública), pruebas del menú.
- Criterios: (a) desde cualquier página, el Centro a **2 clics** (abrir menú de usuario → Centro) y **cada tarea de
  administración a ≤ 1 clic desde el Centro** (≤ 3 desde cualquier página); prueba que recorre los enlaces del Centro y
  verifica 200 como admin. (b) miembro no ve ninguna de las dos entradas; en la puerta pública nadie las ve.
  (c) no se rompe nada de lo que haya dejado el otro agente («Salir» para todas las sesiones, «Volver al inicio»).

**P2-2 · Opcionales según respuestas:** huella corta del respaldo (Q6), 403 → 404 en las vistas de lead (Q3, toca
vistas de otros dueños: PR aparte), archivo de versión escrito por el instalador (Q7, cambio de `deploy/`).

### Qué comprueba el `verificador` (Haiku) en cada PR

`uv run pytest`, `ruff check` y `ruff format --check`, `python tools/kit/privacy_scan.py`, `contrast.py` con los
pares base, `revisar_enlaces` (recorre como admin: los enlaces del Centro no deben dar 404), y un inventario:
(1) toda URL nueva empieza por `/administracion/`; (2) `grep` de `PermissionDenied` en `admin_views.py` = 0
(debe ser `Http404`); (3) toda vista que no es GET lleva `require_POST`; (4) el HTML renderizado en las pruebas no
contiene `/var/`, `/opt/`, `nvapi`, `secret` ni tokens; (5) `base.html` y `navigation.py` sin cambios salvo en P2-1.
El `revisor-bloque` (Opus) revisa cada diff: permisos, consultas, sin JS, 375 px, claro y oscuro.

## 6. Riesgos y preguntas abiertas (para la dueña; cada una con recomendación, ninguna decidida)

| # | Pregunta | Recomendación |
|---|---|---|
| Q1 | ¿El lead entra al Centro con una vista parcial (sus colas: aprobar como miembro, reportes, certificados, vencimientos) o el Centro es **solo admin** y el lead sigue con `/moderacion/`? | Vista parcial: no le da nada que no tenga hoy y le ahorra saltos. Si se prefiere solo admin, es un cambio de una línea. |
| Q2 | ¿Suspender y reactivar desde el Centro (hoy solo en `/admin/`)? ¿Solo admin? | Sí, solo admin, con confirmación y registro en la bitácora; nunca sobre sí misma ni sobre la admin fija. |
| Q3 | Las pantallas actuales de lead/admin responden **403** a un miembro; la regla del repositorio pide **404**. ¿Se unifican? | Sí, en un PR aparte (P2-2): mismas URL, solo cambia el código de respuesta. |
| Q4 | «Sin rol»: en AeroAcademy toda persona es al menos miembro. ¿Mostramos «sin rol» (sin grupo asignado) **y** «sin disciplina»? | Ambos contadores; «sin disciplina» es el que de verdad afecta la matriz del equipo. |
| Q5 | Vencimientos: el Centro usa **30 días** (como AeroControl) y los avisos usan 60 (A3). ¿Está bien la diferencia? | Sí: 30 en el contador «urgente», el enlace lleva a la lista completa de 60. |
| Q6 | ¿Mostrar la huella sha256 del último respaldo? Calcularla obliga a leer el archivo entero. | No por ahora; si se quiere, 12 caracteres con caché por archivo (P2). Más útil: confirmar que hay **copia fuera de la VM** (hoy los respaldos están en el mismo disco: riesgo). |
| Q7 | Versión desplegada: ¿autorizas un cambio chico en `deploy/install.sh` para que escriba un archivo de versión (commit y fecha)? | Sí; mientras tanto se lee `aeroacademy.prev.info` y, si no existe, se dice «no se puede saber desde la app». |
| Q8 | Puerta pública: la app solo puede ver si **el servicio** de la puerta responde, no si el Funnel está publicado en Tailscale. ¿Basta con eso? | Sí, con el texto honesto «servicio en marcha; el Funnel se revisa en la VM». |
| Q9 | El Centro **no existe en la puerta pública** (como `/moderacion/`, D39). Quien administra desde internet no lo verá. ¿Confirmas? | Sí: es lo que protege las cuentas si se filtra una contraseña de admin. |
| Q10 | Registrar por dónde entra cada persona (Tailscale, contraseña o internet) implica guardar la fecha de la última entrada por cada vía. ¿De acuerdo? | Sí, solo fechas (sin IP ni navegador). |
| Q11 | ¿Correr las tareas desde el Centro (p. ej. «revisar enlaces ahora»)? | No: el proceso web no debe lanzar tareas largas; se muestra cómo correrlas. Se reevalúa si hace falta. |

**Riesgos:**
- R1. Duplicar lógica de vistas (aprobar, enlaces) en el Centro: se mitiga llamando a los **mismos servicios**; las
  vistas viejas no se tocan y siguen probadas.
- R2. Colisión con el trabajo del menú de usuario: `base.html`/`navigation.py` solo en P2-1, al final y rebasado.
- R3. Lecturas de disco o de la sonda lentas en la VM: espera corta, caché y «no se pudo comprobar».
- R4. Mostrar más correos juntos: solo en la página de cuentas, solo lead/admin y fuera de la puerta pública.
- R5. `ProtectSystem=strict` podría cambiar en el futuro y dejar de permitir leer `/var/backups/centro`: la pantalla
  lo diría («no hay respaldos a la vista») en vez de fallar.

**Qué NO se toca:** los modelos existentes (`Person`, `TeamSignupLink`, `TotpDevice`, `ModerationLog`, `Report`,
`Credential`, `Notification`); las URL y vistas actuales `/equipo/personas/…`, `/moderacion/…`,
`/certificados/revisar/`, `/certificados/vencimientos/`, `/seguridad/2fa/`, `/admin/`, `/healthz` (siguen
funcionando igual); `deploy/` y `docs/PRODUCCION.md` (solo si se aprueba Q7); `legacy/` y `design/`. Tras las
respuestas, la decisión se registra como **D41** en `docs/DECISIONES.md`.
