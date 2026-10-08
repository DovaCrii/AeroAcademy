# Salida a producción

Servidor: la VM `p340` de la tailnet (`ssh levdigital01@100.121.16.118`), **compartida con AeroControl**. Lo sube la persona; el agente deja todo listo y comprobado, pero no entra al servidor.
Complementa `docs/OPERACION.md` (operación diaria) y `docs/FUSIONES.md` (cómo llegar a `main`).

## Cómo convive con AeroControl (no se pisan)

| | AeroControl | AeroAcademy |
|---|---|---|
| gunicorn | `127.0.0.1:8000` | `127.0.0.1:8010` |
| Dirección | `https://p340.tailccd107.ts.net` (raíz 443) | `https://p340.tailccd107.ts.net:8443` |
| Código | `/opt/aerocontrol` | `/opt/aeroacademy` |
| Configuración | `/etc/aerocontrol.env` | `/etc/centro/env` |
| Datos | `/srv/aerocontrol-data` | `/var/lib/centro` |
| Servicios | `aerocontrol.service` | `centro.service` + `centro-*.timer` |
| Usuario | `levdigital01` | `centro` (de sistema, sin acceso) |

`install.sh` **no toca** el puerto 8000 ni lo que ya publique `tailscale serve`: si el 8010 o el 8443 estuvieran ocupados por otra cosa, se detiene y te dice qué variable cambiar. AeroAcademy se publica **solo con `serve`** (nunca `funnel`): la identidad Tailscale que usa para entrar no llega por Funnel.

## 0. En tu computador (una vez)

```bash
git switch main && git pull
python tools/preflight.py        # debe terminar en «Todo en verde»
```

Tu configuración ya está en `deploy/centro.env` (ignorado por git; **no se sube a GitHub**). Revisa que tenga:

- `ALLOWED_HOSTS=p340.tailccd107.ts.net`
- `PUBLIC_HTTPS_PORT=8443`
- `BOOTSTRAP_ADMINS=` tu correo **de Tailscale** (el que usas al entrar; confírmalo con `tailscale status`)
- `NIM_API_KEY=` tu clave de NVIDIA (opcional)
- `SECRET_KEY=` vacía: el instalador genera una

## 1. En la VM (al estilo de AeroControl: bloques cortos, mirando cada salida)

**A. Código**
```bash
ssh levdigital01@100.121.16.118
git clone https://github.com/DovaCrii/AeroAcademy.git ~/AeroAcademy && cd ~/AeroAcademy && git log --oneline -1
```

**B. Configuración** (desde tu computador, otra terminal, en la carpeta del proyecto)
```bash
scp deploy/centro.env levdigital01@100.121.16.118:~/AeroAcademy/deploy/centro.env
```

**C. Instalar** (en la VM; pide tu contraseña de `sudo`)
```bash
cd ~/AeroAcademy && sudo ./deploy/install.sh
```
Debe terminar en «servicio OK en 127.0.0.1:8010» y mostrar `Dirección: https://p340.tailccd107.ts.net:8443`.
Prerrequisito: MagicDNS y **HTTPS Certificates** activos en la consola de Tailscale (DNS). Ya lo están si AeroControl sirve por HTTPS.

**D. Comprobar**
```bash
systemctl is-active centro && systemctl list-timers 'centro-*' --no-pager
tailscale serve status        # AeroControl en 443 y AeroAcademy en 8443, ambos presentes
systemctl is-active aerocontrol   # sigue active
```

Abre `https://p340.tailccd107.ts.net:8443` desde otro equipo de la tailnet: entras con tu correo y quedas como administradora. Las demás personas quedan pendientes hasta que las apruebes en **Moderación**.

## 2. Teo (el asistente)

```bash
sudo -u centro bash -c 'set -a; . /etc/centro/env; set +a; cd /opt/aeroacademy; exec .venv/bin/python manage.py teo_probar'
```

Muestra modelo, latencia y una respuesta de prueba, o explica el fallo (clave, límite, red o modelo). Si el español no sale bien, cambia `NIM_MODEL` en `/etc/centro/env` y `sudo systemctl restart centro`. El seguimiento semanal corre solo los lunes 09:00; para verlo ya: `manage.py teo_seguimiento` en el mismo comando.

**La clave nunca va al repositorio.** Si se expuso (por ejemplo, pegada en un chat), créala de nuevo en build.nvidia.com, cámbiala en `/etc/centro/env`, `sudo systemctl restart centro`, y revoca la vieja.

## 3. Actualizar después

```bash
cd ~/AeroAcademy && git pull && git log --oneline -1 && sudo ./deploy/install.sh
```
Es idempotente: no toca `/etc/centro/env` ni los datos; migra, recoge estáticos y reinicia. Termina verificando el hash.

## 4. Datos del prototipo (opcional)

Ver «Importar los datos del prototipo» en `docs/OPERACION.md` (primero con `--dry-run`).

## 5. Si algo sale mal

| Síntoma | Qué mirar |
|---|---|
| `install.sh`: «el puerto 8010 ya lo usa otro servicio» | `AEROACADEMY_PORT=8011 sudo -E ./deploy/install.sh` |
| `install.sh`: «el puerto HTTPS 8443 ya sirve otra cosa» | `AEROACADEMY_TS_PORT=10000 sudo -E ./deploy/install.sh` y pon `PUBLIC_HTTPS_PORT=10000` en `/etc/centro/env` |
| El servicio no responde | `journalctl -u centro -n 100` |
| 401 «Se requiere identidad de Tailscale» | Se entró por la IP o por `127.0.0.1`, no por `https://p340.tailccd107.ts.net:8443` |
| 400 «Invalid HTTP_HOST» | El nombre usado no está en `ALLOWED_HOSTS` |
| 403 «CSRF» al enviar un formulario | Falta `PUBLIC_HTTPS_PORT` en `/etc/centro/env` o no coincide con el puerto de `serve` |
| 403 al entrar | La persona está suspendida, o la petición no viene del proxy local |
| Teo «durmiendo» | Falta `NIM_API_KEY` o `BOT_ENABLED=false` |
| AeroControl dejó de responder | No debería pasar (no se toca): `systemctl status aerocontrol` y `tailscale serve status` |
| Volver atrás | `docs/OPERACION.md` → Respaldos → Restaurar; para quitar la publicación: `sudo tailscale serve --https=8443 off` |

## Lista de salida

- [ ] `python tools/preflight.py` en verde sobre `main`.
- [ ] `deploy/centro.env` revisado (host, puerto 8443, tu correo de Tailscale, clave) y copiado a la VM.
- [ ] `sudo ./deploy/install.sh` terminó con «servicio OK» y la dirección `:8443`.
- [ ] `aerocontrol` sigue `active` y su dirección sigue funcionando.
- [ ] Entras por `https://p340.tailccd107.ts.net:8443` como administradora.
- [ ] `teo_probar` en verde (o Teo durmiendo a propósito).
- [ ] Un respaldo a mano: `sudo -u centro /opt/aeroacademy/deploy/backup.sh`.
- [ ] Probaste restaurarlo en una copia (una vez, antes de confiar en él).
