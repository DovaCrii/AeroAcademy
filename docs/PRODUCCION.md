# Salida a producción

Servidor: la VM de la tailnet (`ssh levdigital01@100.121.16.118`). **Lo sube la persona**; el agente deja todo listo y comprobado, pero no entra al servidor.
Complementa `docs/OPERACION.md` (operación diaria) y `docs/FUSIONES.md` (cómo llegar a `main`).

## 0. Antes de subir (en tu computador)

1. Fusiona la cadena de PR (`docs/FUSIONES.md`):
   ```bash
   python tools/fusionar_cadena.py            # plan
   python tools/fusionar_cadena.py --ejecutar
   git switch main && git pull
   ```
2. Comprueba que `main` está listo para producción:
   ```bash
   python tools/preflight.py
   ```
   Corre el lint, las migraciones, la configuración **real** de producción con una base temporal (recorre 25 páginas), la búsqueda de secretos, los finales de línea de los scripts y toda la suite de pruebas. Si termina en verde, se puede subir.
3. Prepara tu configuración (solo pegas lo que falta):
   ```bash
   cp deploy/centro.env.plantilla deploy/centro.env
   # edita deploy/centro.env y completa las líneas «PEGA»:
   #   ALLOWED_HOSTS     → nombre MagicDNS de la VM (tailscale status)
   #   BOOTSTRAP_ADMINS  → tu correo de Tailscale
   #   NIM_API_KEY       → tu clave de NVIDIA (opcional; sin ella Teo queda durmiendo)
   ```
   `deploy/centro.env` está en `.gitignore`: **no se sube a GitHub**.

## 1. En la VM

Requisitos: Debian/Ubuntu, usuario con `sudo`, Tailscale conectado con **MagicDNS** y **HTTPS Certificates** activos (consola de Tailscale → DNS).

```bash
ssh levdigital01@100.121.16.118
git clone https://github.com/DovaCrii/AeroAcademy.git && cd AeroAcademy
```

Desde tu computador, copia la configuración (otra terminal):

```bash
scp deploy/centro.env levdigital01@100.121.16.118:~/AeroAcademy/deploy/centro.env
```

Instala (de vuelta en la VM):

```bash
sudo ./deploy/install.sh
```

El script instala `uv`, crea el usuario `centro`, copia la app a `/opt/aeroacademy`, deja la configuración en `/etc/centro/env` (permisos 640, con una `SECRET_KEY` aleatoria si estaba vacía), migra, carga las semillas, activa el servicio y los cuatro temporizadores (respaldo, vencimientos, seguimiento de Teo) y publica con `tailscale serve`. Es **idempotente**: para actualizar, `git pull` y volver a correrlo.

## 2. Comprobar

```bash
systemctl status centro                     # activo
systemctl list-timers 'centro-*'            # 3 temporizadores
curl -s -H "Host: $(grep ^ALLOWED_HOSTS= /etc/centro/env | cut -d= -f2 | cut -d, -f1)" http://127.0.0.1:8000/healthz   # {"ok": true}
tailscale serve status                      # https://<tu-vm>.ts.net → 127.0.0.1:8000
```

Abre `https://<nombre-magicdns>` desde otro equipo de la tailnet: entras con tu correo y quedas como administradora. Las demás personas quedan pendientes hasta que las apruebes en **Moderación**.

## 3. Teo

Si pegaste la clave:

```bash
sudo -u centro bash -c 'set -a; . /etc/centro/env; set +a; cd /opt/aeroacademy; exec .venv/bin/python manage.py teo_probar'
```

Muestra el modelo, la latencia y una respuesta de prueba, o explica el fallo (clave, límite, red o modelo). Si el español no sale bien, cambia `NIM_MODEL` en `/etc/centro/env` (catálogo en build.nvidia.com), `sudo systemctl restart centro` y repite. **La clave nunca va al repositorio ni a un chat**; si se expuso antes, créala de nuevo y revoca la vieja.

## 4. Datos del prototipo (opcional)

Si el equipo ya usaba `forma-ruta`: ver «Importar los datos del prototipo» en `docs/OPERACION.md` (siempre primero con `--dry-run`).

## 5. Si algo sale mal

| Síntoma | Qué mirar |
|---|---|
| `install.sh` dice que falta `ALLOWED_HOSTS` | Completa la línea en `/etc/centro/env` y vuelve a correrlo |
| El servicio no responde | `journalctl -u centro -n 100` |
| 401 «Se requiere identidad de Tailscale» | Se entró por `127.0.0.1` o por la IP, no por la URL de `tailscale serve` |
| 400 «Invalid HTTP_HOST» | El nombre usado no está en `ALLOWED_HOSTS` |
| 403 al entrar | La petición no viene del proxy local (`TRUSTED_PROXY_IPS`) o la persona está suspendida |
| Teo «durmiendo» | Falta `NIM_API_KEY` o `BOT_ENABLED=false` |
| Quieres volver atrás | `docs/OPERACION.md` → Respaldos → Restaurar |

## Lista de salida

- [ ] Cadena fusionada y `python tools/preflight.py` en verde.
- [ ] `deploy/centro.env` completo y copiado a la VM.
- [ ] `sudo ./deploy/install.sh` terminó con «servicio OK».
- [ ] Entras por la URL de la tailnet como administradora.
- [ ] `teo_probar` en verde (o Teo durmiendo a propósito).
- [ ] `systemctl list-timers 'centro-*'` muestra los temporizadores.
- [ ] Hiciste un primer respaldo a mano: `sudo -u centro /opt/aeroacademy/deploy/backup.sh`.
- [ ] Probaste restaurarlo en una copia (una vez, antes de confiar en él).
