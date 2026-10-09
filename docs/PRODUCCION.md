# Salida a producción

Servidor: la VM `p340` de la tailnet (`ssh levdigital01@100.121.16.118`), **compartida con AeroControl y otras apps**. Lo sube la persona; el agente deja todo listo y comprobado, pero no entra al servidor.
Complementa `docs/OPERACION.md` (operación diaria) y `docs/FUSIONES.md` (cómo llegar a `main`).

## Cómo convive con lo que ya corre en la VM

`tailscale serve status` en `p340` muestra los **tres** puertos HTTPS posibles (443, 8443 y 10000) ocupados, y los tres con **Funnel encendido** (públicos a internet). AeroAcademy guarda certificados y datos personales y entra con la identidad de Tailscale, que **no llega por Funnel**: por eso **no** se publica en ninguno de esos puertos.

En cambio tiene un **nodo Tailscale propio** en la misma VM: otra instancia de `tailscaled` (`tailscaled-aeroacademy.service`, modo userspace, con su estado y su socket) que aparece en tu tailnet como `aeroacademy` y sirve en **su propio** 443, solo tailnet. No se toca nada de AeroControl ni de las demás apps.

| | AeroControl y otras apps | AeroAcademy |
|---|---|---|
| Dirección | `https://p340.tailccd107.ts.net` (:443, :8443, :10000 con Funnel) | `https://aeroacademy.tailccd107.ts.net` (solo tailnet) |
| gunicorn | `127.0.0.1:8000` (8001, 8002, 8092) | `127.0.0.1:8010` |
| Código | `/opt/aerocontrol` | `/opt/aeroacademy` |
| Configuración | `/etc/aerocontrol.env` | `/etc/centro/env` |
| Datos | `/srv/aerocontrol-data` | `/var/lib/centro` |
| Servicios | `aerocontrol.service` | `centro.service`, `centro-*.timer`, `tailscaled-aeroacademy.service` |
| Usuario | `levdigital01` | `centro` (de sistema, sin acceso) |

El instalador **no toca** el puerto 8000 ni lo que ya publique el nodo principal; si el 8010 estuviera ocupado, se detiene y te dice qué variable cambiar.

## 0. En tu computador

```bash
git switch main && git pull
python tools/preflight.py        # debe terminar en «Todo en verde»
```

`deploy/centro.env` (ignorado por git, **no se sube a GitHub**) ya tiene tu configuración. Revisa:
`ALLOWED_HOSTS=aeroacademy.tailccd107.ts.net`, `PUBLIC_HTTPS_PORT=443`, `BOOTSTRAP_ADMINS=` (tu correo **de Tailscale**), `NIM_API_KEY=` (tu clave) y `SECRET_KEY=` vacía (el instalador genera una).

## 1. En la VM, en bloques cortos (mira la salida de cada uno)

**A. Código** (si ya clonaste, solo actualiza)
```bash
ssh levdigital01@100.121.16.118
cd ~/AeroAcademy 2>/dev/null && git pull || git clone https://github.com/DovaCrii/AeroAcademy.git ~/AeroAcademy
cd ~/AeroAcademy && git log --oneline -1
```

**B. Configuración** (desde tu computador, otra terminal, en la carpeta del proyecto)
```bash
scp deploy/centro.env levdigital01@100.121.16.118:~/AeroAcademy/deploy/centro.env
```
Hazlo **antes** del bloque C: si el instalador corre sin ese archivo crea un `/etc/centro/env` vacío (no pasa nada grave: con `centro.env` presente, el instalador lo reemplaza y guarda el anterior como `env.bak`).

**C. Instalar** (en la VM; pide tu contraseña de `sudo`)
```bash
cd ~/AeroAcademy && sudo ./deploy/install.sh
```
En un momento aparece **«Abre el enlace que aparece abajo»** con una dirección `https://login.tailscale.com/a/...`: ábrela en tu navegador, inicia sesión con tu cuenta de Tailscale y aprueba el equipo `aeroacademy`. (Alternativa sin enlace: crea una *auth key* en la consola de Tailscale y corre `AEROACADEMY_TS_AUTHKEY=tskey-... sudo -E ./deploy/install.sh`.)
Debe terminar en «servicio OK en 127.0.0.1:8010» y `Dirección: https://aeroacademy.tailccd107.ts.net`.
Prerrequisito: MagicDNS y **HTTPS Certificates** activos (ya lo están si AeroControl sirve por HTTPS).

**D. Comprobar**
```bash
systemctl is-active centro tailscaled-aeroacademy aerocontrol   # los tres: active
systemctl list-timers 'centro-*' --no-pager                      # respaldo, vencimientos, seguimiento de Teo
tailscale --socket=/run/tailscale-aeroacademy/tailscaled.sock serve status   # https://aeroacademy… → 127.0.0.1:8010
tailscale serve status                                           # lo de AeroControl, sin cambios
```

Abre `https://aeroacademy.tailccd107.ts.net` desde un equipo de la tailnet: entras con tu correo y quedas como administradora. Las demás personas quedan pendientes hasta que las apruebes en **Moderación**.

## 1b. Primer día: entrar, aprobar y dejarlo ordenado

El instalador deja el atajo `sudo aeroacademy <comando>` (corre `manage.py` como `centro` con `/etc/centro/env`).

**Quién eres para la academia.** La identidad es el **correo con que entras a Tailscale** (arriba a la derecha en la consola de Tailscale), no otro. Si la pantalla dice «Esperando aprobación» con tu correo, ese correo no está en `BOOTSTRAP_ADMINS`. Arréglalo desde la VM sin reinstalar:
```bash
sudo aeroacademy aprobar                                  # quién espera aprobación
sudo aeroacademy aprobar tu@correo --rol admin            # aprobar y dar rol (member | lead | admin)
```
Sirve también **antes** de que alguien entre: queda aprobado y al llegar entra directo. Para que un correo nuevo (p. ej. `tu.correo@empresa.cl`) pueda entrar, primero tiene que estar en la tailnet: consola de Tailscale → **Users → Invite users**, o comparte solo el equipo `aeroacademy` (**Machines → aeroacademy → Share**) con quien no deba ver el resto de la tailnet.

**Dejarlo ordenado.** El instalador corre `puesta_en_marcha`: fija en el foro el hilo «Bienvenida… cómo empezar» (una sola vez) y muestra una lista de lo que falta (admins que aún no entran, pendientes, rutas publicadas, Teo). Puedes repetirlo cuando quieras:
```bash
sudo aeroacademy puesta_en_marcha
```
Cada persona ve en la portada **Primeros pasos** (hoja de personaje, primera misión, primer certificado, presentarse en el foro) hasta completarlos.

**Ícono y acceso directo.** El sitio trae ícono y manifiesto de app: en Chrome/Edge, menú → **Instalar AeroAcademy** (o «Crear acceso directo»); en el celular, **Agregar a pantalla de inicio**. Abre como app, con el ícono de la academia, siempre que el equipo esté conectado a Tailscale.

## 1c. Incorporar a alguien del equipo (cada vez)

1. **Acceso a la red:** en la consola de Tailscale, **Users → Invite users** con su correo (ve toda la tailnet), o **Machines → aeroacademy → Share** (solo ve la academia). La persona instala Tailscale en su equipo y entra con ese correo.
2. **Aprobar:** cuando abra `https://aeroacademy.tailccd107.ts.net` queda «pendiente» y te llega un aviso en la campana; apruébala en **Moderación** o desde la VM: `sudo aeroacademy aprobar su@correo` (con `--rol lead` si revisará certificados). Se puede aprobar antes de que entre.
3. **Su primer día:** ve «Primeros pasos» en la portada y el hilo de bienvenida fijado en el foro; que instale la academia como app (menú del navegador → Instalar).
**Alta masiva (varias personas a la vez).** Prepara un CSV con `correo, nombre, rol, área/disciplina, cargo` (rol `member|lead|admin`, vacío = member; varias disciplinas separadas con `|`). Dos formas, las dos idempotentes (repetir actualiza, no duplica) y con validación (correos, roles y disciplinas desconocidos se informan fila por fila):
- **Desde la app** (responsables): **Equipo → Agregar personas** (`/equipo/personas/agregar/`). Pega las filas o sube el archivo, pulsa **Simular** y, si está bien, **Importar**. Un lead solo da el rol member; lead y admin los da un admin.
- **Desde la VM:** `sudo aeroacademy importar_equipo equipo.csv --dry-run` y luego sin `--dry-run`.

Después, en **Equipo → Gestionar personas** (`/equipo/personas/`) cada persona tiene su lista: *invitada a Tailscale* (la marcas tú, la academia no puede consultarlo) · aprobada · ya entró · primeros pasos (0-4), con el **texto de invitación** listo para copiar (enlace, pasos de Tailscale e instalación como app; sin claves). Ahí mismo se cambia el área (disciplinas), cargo y rol, y todo queda en la bitácora de Moderación. Quien entre con un nombre distinto en Tailscale verá su nombre de Tailscale: ese manda al iniciar sesión.

4. **Salida:** en el admin, marca a la persona como inactiva o suspéndela en Moderación, y quítale el acceso en Tailscale.

## 2. Nala (la asistente)

```bash
sudo aeroacademy teo_probar
```

Muestra modelo, latencia y una respuesta de prueba, o explica el fallo (clave, límite, red o modelo). Teo pide a los modelos «de razonamiento» (Nemotron 3, Qwen 3) que no piensen en voz alta (`enable_thinking: false`) y descarta el razonamiento que se cuele; si un modelo solo devuelve razonamiento, pasa al siguiente de `NIM_MODEL_FALLBACKS`. Si la respuesta de prueba sale en inglés o con pasos («Here's a thinking process…»), corre `sudo aeroacademy teo_probar --buscar` y usa los modelos que marque. Si el español no sale bien, cambia `NIM_MODEL` en `/etc/centro/env` y `sudo systemctl restart centro`. El seguimiento semanal corre solo los lunes 09:00; para verlo ya: `manage.py teo_seguimiento` en el mismo comando.

**La clave nunca va al repositorio.** Si se expuso (por ejemplo, pegada en un chat), créala de nuevo en build.nvidia.com, cámbiala en `deploy/centro.env` y vuelve a copiarlo y a correr el instalador (o edita `/etc/centro/env` y `sudo systemctl restart centro`), y revoca la vieja.

## 3. Actualizar después

```bash
cd ~/AeroAcademy && git pull && git log --oneline -1 && sudo ./deploy/install.sh
```
Es idempotente: reinstala la configuración de `deploy/centro.env` conservando la `SECRET_KEY`, no toca los datos, migra, recoge estáticos, reinicia y reutiliza el nodo ya dado de alta (no vuelve a pedir el enlace).

## 4. Datos del prototipo (opcional)

Ver «Importar los datos del prototipo» en `docs/OPERACION.md` (primero con `--dry-run`).

## 5. Si algo sale mal

| Síntoma | Qué mirar |
|---|---|
| El instalador pidió `ALLOWED_HOSTS` o creó un env vacío | Faltó copiar `deploy/centro.env` (bloque B): cópialo y vuelve a correr el bloque C |
| «el puerto 8010 ya lo usa otro servicio» | `AEROACADEMY_PORT=8011 sudo -E ./deploy/install.sh` |
| No aparece el enlace de inicio de sesión | `sudo journalctl -u tailscaled-aeroacademy -n 50`; usa la *auth key* (bloque C) |
| El nodo `aeroacademy` no abre por HTTPS | En la consola de Tailscale: DNS → HTTPS Certificates activado; Machines → `aeroacademy` aprobada (si tu tailnet exige aprobación de equipos) |
| El servicio no responde | `journalctl -u centro -n 100` |
| 401 «Se requiere identidad de Tailscale» | Se entró por la IP o por `127.0.0.1`, o por una dirección de Funnel; usa `https://aeroacademy.tailccd107.ts.net` |
| 400 «Invalid HTTP_HOST» | El nombre usado no está en `ALLOWED_HOSTS` (el instalador lo ajusta al nombre real del nodo) |
| 403 «CSRF» al enviar un formulario | `PUBLIC_HTTPS_PORT` debe ser `443` en `/etc/centro/env` |
| Teo «durmiendo» | Falta `NIM_API_KEY` o `BOT_ENABLED=false` |
| Te quedas en «Esperando aprobación» | Tu correo de Tailscale no está en `BOOTSTRAP_ADMINS`: `sudo aeroacademy aprobar <correo> --rol admin` y recarga |
| Teo responde en inglés o muestra «thinking process» | Actualiza (`git pull` + instalador) y `sudo aeroacademy teo_probar --buscar` |
| Quieres quitar la publicación | `sudo tailscale --socket=/run/tailscale-aeroacademy/tailscaled.sock serve reset` (solo afecta al nodo propio) |
| Volver atrás | `docs/OPERACION.md` → Respaldos → Restaurar |

## Lista de salida

- [ ] `python tools/preflight.py` en verde sobre `main`.
- [ ] `deploy/centro.env` revisado y copiado a la VM **antes** de instalar.
- [ ] `sudo ./deploy/install.sh` terminó con «servicio OK» y `Dirección: https://aeroacademy…`.
- [ ] `aerocontrol` sigue `active` y su dirección sigue funcionando.
- [ ] Entras por `https://aeroacademy.tailccd107.ts.net` como administradora (si no: `sudo aeroacademy aprobar <tu correo de Tailscale> --rol admin`).
- [ ] `sudo aeroacademy puesta_en_marcha` sin avisos «!» que no esperabas; el hilo de bienvenida está fijado en el foro.
- [ ] El equipo está invitado a la tailnet (o tiene compartido el equipo `aeroacademy`) y aprobado.
- [ ] `teo_probar` en verde (o Teo durmiendo a propósito).
- [ ] Un respaldo a mano: `sudo -u centro /opt/aeroacademy/deploy/backup.sh`.
- [ ] Probaste restaurarlo en una copia (una vez, antes de confiar en él).
