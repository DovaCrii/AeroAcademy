# Operación · AeroAcademy

Guía para quien instala y mantiene el servicio en la VM. Todo el acceso es **solo por la tailnet** (`tailscale serve`; nunca `funnel`).

## Instalar o actualizar

En una VM Debian/Ubuntu, con el repositorio clonado:

```bash
sudo ./deploy/install.sh mi-vm.tu-tailnet.ts.net
```

El script es **idempotente**: sirve para instalar y para actualizar.

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
