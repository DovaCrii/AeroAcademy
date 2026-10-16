# Operación · AeroAcademy

Guía para quien instala y mantiene el servicio en la VM. El acceso es **solo por la tailnet** (`tailscale serve`) salvo que se encienda la puerta pública con Funnel (D36, ver `docs/PRODUCCION.md` §6).

## Instalar o actualizar

En una VM Debian/Ubuntu, con el repositorio clonado:

```bash
sudo ./deploy/install.sh mi-vm.tu-tailnet.ts.net
```

El script es **idempotente**: sirve para instalar y para actualizar.

**Para actualizar usa un solo comando** (con reversa automática): `sudo aeroacademy actualizar` en la VM, o `./tools/desplegar.ps1` desde tu computador. Hace `git pull --ff-only`, deja una instantánea del código (`/opt/aeroacademy.prev`) y un respaldo de SQLite (`/var/backups/centro/pre-actualizar-*.sqlite3`, los últimos 5), corre este instalador con tu entorno (`sudo PUBLIC_FUNNEL=1 aeroacademy actualizar` pasa el indicador del Funnel; sin indicarlo se conserva el estado actual), comprueba `/healthz` y, si falla, restaura el código (y la base solo si hubo migraciones). Opciones: `--solo-comprobar`, `--sin-pull`; `sudo aeroacademy revertir` vuelve atrás a mano. Detalle en `docs/PRODUCCION.md` §3.

1. Instala dependencias y `uv`, crea el usuario de sistema `centro` y copia la aplicación a `/opt/aeroacademy`.
2. La primera vez crea `/etc/centro/env` con una `SECRET_KEY` aleatoria (permisos 640). Ahí se completan:
   - `ALLOWED_HOSTS`: el nombre MagicDNS de la VM (el script lo rellena si lo pasas como argumento).
   - `BOOTSTRAP_ADMINS`: tu correo de Tailscale; quien figure ahí queda como administrador al entrar.
   - `NIM_API_KEY` (opcional): la clave de NVIDIA para Teo, creada en build.nvidia.com. **Nunca en el repositorio.**
3. Corre `collectstatic`, `migrate`, `seed_catalog` y `reindex_assistant`.
4. Instala y activa `centro.service` (gunicorn en `127.0.0.1:8010`; el 8000 es de AeroControl) y dos tareas diarias:
   - `centro-backup.timer` (03:30): respaldo de la base y de los archivos privados.
   - `centro-expiry.timer` (07:00): `manage.py check_expirations`, que avisa de credenciales por vencer o vencidas y apaga las insignias que exigen vigencia.
5. Comprueba `http://127.0.0.1:8010/healthz` y publica desde un **nodo Tailscale propio** (`aeroacademy.<tailnet>.ts.net`), sin tocar lo que ya sirva la VM.

Después de editar `/etc/centro/env`: `sudo systemctl restart centro`.

## Primera persona administradora

Entra por la URL de la tailnet con el correo que pusiste en `BOOTSTRAP_ADMINS`. Quedas como administradora y aprobada. Las demás personas entran como **pendientes** y las apruebas en **Moderación**.

## Cómo dar de alta cuentas

Hay tres formas de que una persona tenga cuenta. En la app, **Equipo → Personas** (`/equipo/personas/`, solo admin y solo por la tailnet) trae estos mismos pasos en una caja. Los comandos se corren en la VM con `sudo aeroacademy <comando>`; todos dejan constancia en la bitácora de **Moderación** (como «consola», sin el enlace ni su secreto).

1. **Agrega o aprueba el correo.**
   - `sudo aeroacademy aprobar <correo> [--rol member|lead|admin]` aprueba a la persona (y la crea si aún no entró). Sin correo, lista quién espera aprobación.
   - Varias a la vez: `sudo aeroacademy importar_equipo equipo.csv --dry-run` y, si está bien, sin `--dry-run`. En la app: **Equipo → Agregar personas**.
2. **Genera el enlace.**
   - **Personal** (un uso, vence en 7 días, para una persona ya aprobada): `sudo aeroacademy enlace_registro <correo>`, o el botón **Generar enlace de registro** de su fila. Sirve también para restablecer una contraseña olvidada: no hay correo automático, el enlace nuevo invalida el anterior.
   - **Del equipo** (uno para todos): `sudo aeroacademy enlace_equipo --dias 14` (7, 14 o 30) y `sudo aeroacademy enlace_equipo --revocar`. Generar otro revoca el anterior. Quien no esté en la lista queda **pendiente** hasta que la apruebes.
3. **Mándalo por un canal privado.** El enlace se muestra una sola vez; la base guarda solo su huella.
4. **La persona lo abre y crea su contraseña**, o entra directo si usa Tailscale con su correo del equipo (en ese caso no necesita contraseña ni enlace).

**Si el enlace vence o se pierde:** quien lo abre ve «Este enlace ya no sirve…» (código 400, el mismo mensaje para enlaces vencidos, usados, manipulados o reemplazados). Genera otro con el mismo comando.

**Respuesta del enlace del equipo:** si el correo ya tiene cuenta, es de un responsable o admin, o está suspendido, la persona ve el mismo mensaje genérico (no se revela qué cuentas existen). Si ya tiene cuenta, entra por `/entrar/`; si olvidó la contraseña, pide un enlace personal.

**Cuenta propia:** con sesión por contraseña, el menú del avatar trae **Mi cuenta** (con cambio de contraseña) y **Salir**. Quien entra por Tailscale no tiene contraseña que cambiar ni «Salir».

## Revisar enlaces

`sudo aeroacademy revisar_enlaces` recorre el sitio como admin (solo GET) y lista los enlaces internos rotos; con `--externos` revisa también las URLs de los recursos y de `seed/`. Escribe un CSV en `private/` (ignorado por git). Los «bloqueado» (403 o 429, p. ej. Autodesk) y los «sin_respuesta» (timeout) hay que confirmarlos en un navegador; solo «roto» (404 o 410) es un enlace caído. No lo corre el CI.

## Respaldos

`deploy/backup.sh` guarda cada día, en `/var/backups/centro`:

- `db-AAAA-MM-DD.sqlite3`: copia en caliente con `sqlite3 .backup` (segura con el servicio corriendo).
- `media-AAAA-MM-DD.tar.gz`: certificados y documentos privados.

Retención de 30 días. Los respaldos contienen **datos personales**: permisos 077 y, si los copias fuera de la VM, hazlo por un canal cifrado.

Restaurar:

```bash
sudo systemctl stop centro
sudo -u centro cp /var/backups/centro/db-AAAA-MM-DD.sqlite3 /var/lib/centro/db.sqlite3
sudo -u centro tar -C /var/lib/centro -xzf /var/backups/centro/media-AAAA-MM-DD.tar.gz
sudo systemctl start centro
```

## Importar los datos del prototipo (forma-ruta)

Si el equipo ya usaba el prototipo, copia su `ruta.db` a la VM y corre (primero en simulación):

```bash
manage() { sudo -u centro bash -c 'set -a; . /etc/centro/env; set +a; cd /opt/aeroacademy; exec .venv/bin/python manage.py "$@"' _ "$@"; }
manage import_legacy --db /ruta/ruta.db --dry-run
manage import_legacy --db /ruta/ruta.db
```

Importa personas (quedan aprobadas), avance y meta de certificación, notas (con su fecha original, sin XP ni avisos) y las casillas del kit y del plan. Es **idempotente**: correrlo de nuevo no duplica nada. Abre el `ruta.db` en solo lectura. Lo que no se pudo importar aparece como «omitido».

## Tareas útiles

| Qué | Comando (con el entorno de `/etc/centro/env`) |
|---|---|
| Recargar semillas (rutas, insignias, foro) | `manage.py seed_catalog` (con `--dry-run` para validar) |
| Reconstruir el índice de Teo | `manage.py reindex_assistant` |
| Avisos de vencimientos a mano | `manage.py check_expirations` |
| Ver el servicio | `systemctl status centro` · `journalctl -u centro -f` |
| Estado de las tareas | `systemctl list-timers 'centro-*'` |

## Semillas y lo creado en el admin

`seed_catalog` (que corre el instalador en cada actualización) **retira** las insignias, títulos y categorías del foro que no estén en `seed/`. Si creas alguno desde el admin de Django, agrégalo también a su JSON en `seed/` o se retirará en la próxima actualización.

## Seguridad en pocas líneas

- La identidad viene del encabezado de Tailscale y solo se acepta desde `127.0.0.1` (el proxy local). Cualquier otro origen recibe 403.
- Los certificados y documentos no tienen URL pública: se descargan solo por vistas con permiso, siempre como adjunto.
- `/healthz` responde sin identidad **solo** desde el proxy local.
- El log de Teo guarda solo metadatos; el contexto que se envía a NVIDIA sale de una lista blanca (ver `docs/BOT.md`).
- Correo: fuera del MVP; `notify()` deja un gancho (`email-hook`) que hoy solo escribe una línea en el log, sin el contenido.
