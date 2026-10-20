# Salida a producción

Servidor: la VM `p340` de la tailnet (`ssh example@<IP-DE-LA-VM>`), **compartida con AeroControl y otras apps**. Lo sube la persona; el agente deja todo listo y comprobado, pero no entra al servidor.
Complementa `docs/OPERACION.md` (operación diaria) y `docs/FUSIONES.md` (cómo llegar a `main`).

## Cómo convive con lo que ya corre en la VM

`tailscale serve status` en `p340` muestra los **tres** puertos HTTPS posibles (443, 8443 y 10000) ocupados, y los tres con **Funnel encendido** (públicos a internet). AeroAcademy guarda certificados y datos personales y entra con la identidad de Tailscale, que **no llega por Funnel**: por eso **no** se publica en ninguno de esos puertos. Si se quiere acceso público, se hace con el **nodo propio** `aeroacademy` y una puerta endurecida distinta (D36, §6): nunca con el Funnel de AeroControl.

En cambio tiene un **nodo Tailscale propio** en la misma VM: otra instancia de `tailscaled` (`tailscaled-aeroacademy.service`, modo userspace, con su estado y su socket) que aparece en tu tailnet como `aeroacademy` y sirve en **su propio** 443, solo tailnet. No se toca nada de AeroControl ni de las demás apps.

| | AeroControl y otras apps | AeroAcademy |
|---|---|---|
| Dirección | `https://p340.tailccd107.ts.net` (:443, :8443, :10000 con Funnel) | `https://aeroacademy.tailccd107.ts.net` (solo tailnet) |
| gunicorn | `127.0.0.1:8000` (8001, 8002, 8092) | `127.0.0.1:8010` |
| Código | `/opt/aerocontrol` | `/opt/aeroacademy` |
| Configuración | `/etc/aerocontrol.env` | `/etc/centro/env` |
| Datos | `/srv/aerocontrol-data` | `/var/lib/centro` |
| Servicios | `aerocontrol.service` | `centro.service`, `centro-*.timer`, `tailscaled-aeroacademy.service` |
| Usuario | `example` | `centro` (de sistema, sin acceso) |

El instalador **no toca** el puerto 8000 ni lo que ya publique el nodo principal; si el 8010 estuviera ocupado, se detiene y te dice qué variable cambiar.

## 0. En tu computador

```bash
git switch main && git pull
python tools/preflight.py        # debe terminar en «Todo en verde»
```

`deploy/centro.env` (ignorado por git, **no se sube a GitHub**) ya tiene tu configuración. Revisa:
`ALLOWED_HOSTS=aeroacademy.tailccd107.ts.net`, `PUBLIC_HTTPS_PORT=443`, `BOOTSTRAP_ADMINS=` (tu correo **de Tailscale**), `NIM_API_KEY=` (tu clave) y `SECRET_KEY=` vacía (el instalador genera una).

## 1. Primera instalación en la VM, en bloques cortos (mira la salida de cada uno)

> Solo para instalar por primera vez. Para **actualizar** usa §3 (un comando).

**A. Código** (si ya clonaste, solo actualiza)
```bash
ssh example@<IP-DE-LA-VM>
cd ~/AeroAcademy 2>/dev/null && git pull || git clone https://github.com/DovaCrii/AeroAcademy.git ~/AeroAcademy
cd ~/AeroAcademy && git log --oneline -1
```

**B. Configuración** (desde tu computador, otra terminal, en la carpeta del proyecto)
```bash
scp deploy/centro.env example@<IP-DE-LA-VM>:~/AeroAcademy/deploy/centro.env
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
- **Desde la app** (solo admin, D34): **Equipo → Agregar personas** (`/equipo/personas/agregar/`). Pega las filas o sube el archivo, pulsa **Simular** y, si está bien, **Importar**.
- **Desde la VM:** `sudo aeroacademy importar_equipo equipo.csv --dry-run` y luego sin `--dry-run`.

Después, en **Equipo → Gestionar personas** (`/equipo/personas/`) cada persona tiene su lista: *invitada a Tailscale* (la marcas tú, la academia no puede consultarlo) · aprobada · ya entró · primeros pasos (0-4), con el **texto de invitación** listo para copiar (enlace, pasos de Tailscale e instalación como app; sin claves). Ahí mismo se cambia el área (disciplinas), cargo y rol, y todo queda en la bitácora de Moderación. Quien entre con un nombre distinto en Tailscale verá su nombre de Tailscale: ese manda al iniciar sesión.

**Entrar con contraseña (D34, solo admin).** Si su correo de Tailscale no coincide con el del equipo, o entra desde un equipo compartido (Tailscale no manda identidad), genera su **enlace de registro**: en **Equipo → Gestionar personas**, botón **Generar enlace de registro** de su fila (genera uno nuevo cada vez; el anterior deja de servir) (o, desde la VM, `sudo aeroacademy enlace_registro su@correo`). Vale 7 días y se usa una sola vez; viene dentro del texto de invitación de esa fila. La persona lo abre (con Tailscale conectado), elige nombre y contraseña (mín. 10 caracteres) y queda dentro; después entra por `/entrar/`. Solo se puede invitar a personas ya aprobadas. **Contraseña olvidada:** no hay correo automático; genera otro enlace (invalida el anterior) y mándalo por un canal privado. Tras 5 intentos fallidos con un mismo correo hay que esperar 15 minutos (el contador vive en la memoria de cada uno de los 3 procesos de gunicorn: en la práctica hasta 15 intentos, y reiniciar el servicio lo borra; es freno suficiente para una tailnet, no una defensa fuerte). Agregar personas, enlaces y cambios de rol son solo del admin; los responsables siguen viendo la lista y editando área y cargo.

**Enlace del equipo (D35, solo admin).** Lo más simple: un solo enlace para todos. En **Equipo → Gestionar personas**, tarjeta **Enlace de inscripción del equipo**: elige la vigencia (7, 14 o 30 días), **Generar enlace**, cópialo (se muestra una sola vez) y mándalo por un canal privado. O desde la VM: `sudo aeroacademy enlace_equipo --dias 14`; `sudo aeroacademy enlace_equipo --revocar` lo anula. Cada persona lo abre (con Tailscale conectado) y pone correo, nombre y contraseña: si ya la habías aprobado, queda dentro; si no estaba en la lista, queda **pendiente** y te llega el aviso en la campana (apruébala en Moderación; después entra por `/entrar/`). Si el correo ya tiene cuenta, es de un responsable o admin o está suspendido, la respuesta es siempre la misma («Si el correo es válido, ya quedó registrado o un administrador te contactará…»): así el enlace no sirve para averiguar qué correos tienen cuenta. Quien ya la tiene entra por `/entrar/`; responsables y admins usan su enlace personal. Generar otro enlace revoca el anterior; revócalo cuando todos se hayan inscrito. **Para probarlo con otra cuenta (D41):** pulsa «Salir» en el menú de tu cuenta, abre el enlace y, al terminar, «Salir» otra vez y «Entrar con Tailscale» en la portada para volver a tu sesión (sin ventana de incógnito).

4. **Salida:** en el admin, marca a la persona como inactiva o suspéndela en Moderación, y quítale el acceso en Tailscale.

## 2. Nala (la asistente)

```bash
sudo aeroacademy teo_probar
```

Muestra modelo, latencia y una respuesta de prueba, o explica el fallo (clave, límite, red o modelo). Teo pide a los modelos «de razonamiento» (Nemotron 3, Qwen 3) que no piensen en voz alta (`enable_thinking: false`) y descarta el razonamiento que se cuele; si un modelo solo devuelve razonamiento, pasa al siguiente de `NIM_MODEL_FALLBACKS`. Si la respuesta de prueba sale en inglés o con pasos («Here's a thinking process…»), corre `sudo aeroacademy teo_probar --buscar` y usa los modelos que marque. Si el español no sale bien, cambia `NIM_MODEL` en `/etc/centro/env` y `sudo systemctl restart centro`. El seguimiento semanal corre solo los lunes 09:00; para verlo ya: `manage.py teo_seguimiento` en el mismo comando.

**La clave nunca va al repositorio.** Si se expuso (por ejemplo, pegada en un chat), créala de nuevo en build.nvidia.com, cámbiala en `deploy/centro.env` y vuelve a copiarlo y a correr el instalador (o edita `/etc/centro/env` y `sudo systemctl restart centro`), y revoca la vieja.

## 3. Actualizar con un comando

Desde la **primera instalación** (§1) las actualizaciones son un solo comando, con reversa automática si algo falla.

**Desde tu computador (Windows, PowerShell 7, en la carpeta del proyecto):**
```powershell
./tools/desplegar.ps1                  # git al día → copia private/ si existe → ssh -t … sudo aeroacademy actualizar
./tools/desplegar.ps1 -DryRun          # muestra los comandos sin ejecutar nada
./tools/desplegar.ps1 -SoloComprobar   # solo mira la salud del servicio
./tools/desplegar.ps1 -Revertir        # vuelve a la versión anterior
./tools/desplegar.ps1 -SinPrivados -Preflight -PublicFunnel 1
```
La conexión sale de `AEROACADEMY_VM_HOST` y `AEROACADEMY_VM_USER` o de `deploy/vm.local.json` (ignorado por git; modelo en `deploy/vm.local.json.ejemplo`: `{"host": "<IP-DE-LA-VM>", "user": "example"}`). El host y el usuario reales **no van al repositorio**. Al final recuerda recargar el navegador con **Ctrl+F5**.

**Cursos privados de JEJ (clases internas).** Cada actualización los deja al día sin pasos manuales: `desplegar.ps1` copia `private/cursos/`, el instalador lo sincroniza con `/var/lib/centro/cursos` y corre `manage.py cargar_cursos_privados` justo después de `seed_catalog` (ver `docs/CURSOS.md`). Para sumar una clase semanal basta editar `private/cursos/<slug>/ruta.json` en tu computador y volver a correr `./tools/desplegar.ps1`. Si la carpeta no existe, el paso no hace nada.

Para no escribir la contraseña de SSH cada vez, crea una llave (equivalente a `ssh-copy-id` en Windows); la contraseña de `sudo` se sigue pidiendo en la VM, es lo esperado:
```powershell
ssh-keygen -t ed25519
Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub | ssh example@<IP-DE-LA-VM> "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

**Directo en la VM** (la primera vez, o si prefieres hacerlo a mano):
```bash
cd ~/AeroAcademy
sudo ./deploy/actualizar.sh        # la primera vez tras esta mejora; el instalador deja luego el atajo:
sudo aeroacademy actualizar        # equivale a lo anterior (`actualizar` y `revertir` son palabras reservadas del atajo)
sudo aeroacademy actualizar --solo-comprobar   # solo salud; no cambia nada
sudo aeroacademy actualizar --sin-pull         # usa el árbol de trabajo tal como está
sudo aeroacademy revertir          # vuelta manual a la versión anterior (equivale a actualizar.sh --revertir)
```
Cualquier otro `sudo aeroacademy <comando>` sigue siendo `manage.py <comando>`.

**Qué hace `actualizar`** (idempotente; imprime cada paso como `==> …`):
1. Precondiciones: root, repositorio sin cambios, `git fetch` y `git pull --ff-only`; muestra el commit actual, el nuevo y la lista de commits.
2. Instantánea del código instalado en `/opt/aeroacademy.prev` (sin `.venv`, estáticos ni datos) y respaldo consistente de SQLite (`sqlite3 .backup`) en `/var/backups/centro/pre-actualizar-<fecha UTC>.sqlite3` (se guardan los últimos 5).
3. Corre `deploy/install.sh` con **tu entorno**: `PUBLIC_FUNNEL`, `AEROACADEMY_PORT`, `AEROACADEMY_TS_AUTHKEY`… pasan tal cual (`sudo PUBLIC_FUNNEL=1 aeroacademy actualizar`, o `sudo -E aeroacademy actualizar` para llevar todo el entorno). Si la puerta pública (Funnel) ya está activa y no indicas `PUBLIC_FUNNEL`, se **conserva**; para apagarla, `PUBLIC_FUNNEL=0`.
4. Salud: `systemctl is-active centro` y `http://127.0.0.1:8010/healthz` (más el 8011 si `centro-public` está activa), con varios reintentos y espera creciente.

**Cómo decide la reversa.** Si el instalador o la salud fallan, restaura el **código** de la instantánea, reinicia y vuelve a comprobar. La **base de datos** solo se restaura si la actualización aplicó migraciones (compara el conteo de `django_migrations` antes y después): el código viejo no entiende una base migrada. Si no hubo migraciones, la base **no se toca**. Cuando restaura la base lo dice en grande: se pierde lo que se escribió en la academia entre el respaldo y la falla (minutos). Termina con código ≠ 0 y un resumen (qué falló, qué se restauró, `journalctl -u centro -n 200 --no-pager`). Códigos de salida: `1` falló y se restauró, `2` falló y la reversa también (intervención manual), `3` precondición no cumplida (no se cambió nada).

`revertir` (manual) usa la última instantánea; si esa actualización migró, **pregunta** antes de restaurar la base, o usa `--con-base` / `--sin-base`. No se revierte lo que el instalador haya cambiado en systemd o en Tailscale (unidades, publicación).

Límite: el script se probó con comandos simulados, no contra la VM real; la primera vez, mira la salida completa.

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
| 403 «Acceso no permitido» o te manda a «Bienvenida» | Se entró por la IP o por `127.0.0.1`, o por la dirección de Funnel del nodo principal (AeroControl), o sin Tailscale; usa `https://aeroacademy.tailccd107.ts.net` o entra con correo y contraseña en `/entrar/` |
| 400 «Invalid HTTP_HOST» | El nombre usado no está en `ALLOWED_HOSTS` (el instalador lo ajusta al nombre real del nodo) |
| 403 «CSRF» al enviar un formulario | `PUBLIC_HTTPS_PORT` debe ser `443` en `/etc/centro/env` |
| Teo «durmiendo» | Falta `NIM_API_KEY` o `BOT_ENABLED=false` |
| Te quedas en «Esperando aprobación» | Tu correo de Tailscale no está en `BOOTSTRAP_ADMINS`: `sudo aeroacademy aprobar <correo> --rol admin` y recarga |
| Teo responde en inglés o muestra «thinking process» | Actualiza (`git pull` + instalador) y `sudo aeroacademy teo_probar --buscar` |
| Quieres quitar la publicación | `sudo tailscale --socket=/run/tailscale-aeroacademy/tailscaled.sock serve reset` (solo afecta al nodo propio) |
| Volver atrás | `docs/OPERACION.md` → Respaldos → Restaurar |

## 6. Puerta pública con Funnel (D36, opcional)

Acceso gratuito sin instalar Tailscale. Dos puertas sobre el mismo código y la misma base:

| | Tailnet | Pública |
|---|---|---|
| Dirección | `https://aeroacademy.tailccd107.ts.net:8443` | `https://aeroacademy.tailccd107.ts.net` |
| Servicio | `centro.service` → `127.0.0.1:8010` | `centro-public.service` → `127.0.0.1:8011` |
| Entrada | identidad de Tailscale (o contraseña) | **solo** enlace/contraseña; sin `/admin/` ni moderación |
| Responsables y admins | sin cambios | contraseña, como el resto (TOTP opcional con `PUBLIC_REQUIRE_SECOND_FACTOR=1`, D39) |

**Antes de encender (una vez):**
1. Consola de Tailscale → *Access controls*: el nodo `aeroacademy` necesita el atributo `funnel` (en `nodeAttrs`, p. ej. `{"target": ["tag:aeroacademy"], "attr": ["funnel"]}` o `autogroup:member` si el nodo es tuyo) y HTTPS Certificates activo.
2. **Segundo factor (solo si lo vuelves a exigir con `PUBLIC_REQUIRE_SECOND_FACTOR=1`; apagado por defecto, D39).** Activa tu segundo factor por la tailnet, antes de abrir la puerta: entra a `https://aeroacademy.tailccd107.ts.net:8443/seguridad/2fa/` (o por el 443 de siempre, mientras no la enciendas), agrega la clave en tu app de autenticación, escribe el código y **guarda los 8 códigos de recuperación**. Cada lead/admin debe hacerlo; sin eso queda bloqueado en la puerta pública (no pierde nada: puede entrar por la tailnet).

**Encender** (en la VM; `AEROACADEMY_PUBLISH=node` es el valor por defecto):
```bash
cd ~/AeroAcademy && sudo PUBLIC_FUNNEL=1 aeroacademy actualizar   # actualiza y enciende la puerta (equivale a git pull + PUBLIC_FUNNEL=1 sudo -E ./deploy/install.sh)
```
El instalador: crea `centro-public.service`, fija `ACADEMY_URL` (los enlaces de invitación salen con la dirección pública), pasa `PUBLIC_HTTPS_PORT=8443`, y publica con `tailscale --socket=/run/tailscale-aeroacademy/tailscaled.sock serve --https=8443 …:8010` y `… funnel --bg --https=443 http://127.0.0.1:8011`. Es idempotente.

**Comprobar:**
```bash
systemctl is-active centro centro-public tailscaled-aeroacademy aerocontrol   # los cuatro: active
tailscale --socket=/run/tailscale-aeroacademy/tailscaled.sock serve status      # 443 con «Funnel on» → 8011; 8443 tailnet → 8010
tailscale serve status                                                          # lo de AeroControl, sin cambios
curl -sI https://aeroacademy.tailccd107.ts.net/admin/ | head -1                # 404
curl -sI https://aeroacademy.tailccd107.ts.net/bienvenida/ | grep -i strict-transport
```

**Cómo invitar:** en **Equipo → Gestionar personas** genera el enlace del equipo y mándalo; es `https://aeroacademy.tailccd107.ts.net/inscripcion/<token>/`. Cada persona pone correo, nombre y contraseña (D35), y entra cuando la apruebes en **Moderación** (desde la tailnet: en la pública no existe). Para una persona concreta ya aprobada, su enlace personal (D34) sale con la misma dirección pública. Quien ya tiene contraseña entra por `/entrar/`.

**Vuelta atrás (rollback):**
```bash
sudo PUBLIC_FUNNEL=0 aeroacademy actualizar     # (o PUBLIC_FUNNEL=0 sudo -E ./deploy/install.sh)
# apaga centro-public, borra la config de Funnel del nodo propio y vuelve a servir la tailnet en el 443
# A mano, si hiciera falta:
sudo systemctl disable --now centro-public
sudo tailscale --socket=/run/tailscale-aeroacademy/tailscaled.sock serve reset      # solo afecta al nodo propio
sudo tailscale --socket=/run/tailscale-aeroacademy/tailscaled.sock serve --bg --https=443 http://127.0.0.1:8010
```

**Si algo falla:** `journalctl -u centro-public -n 100`; un 403 de CSRF en la pública indica que `ALLOWED_HOSTS` no trae el nombre del nodo; «Bloqueado: falta segundo factor» es lo esperado para un lead/admin sin TOTP (actívalo por la tailnet). El HSTS de la pública dura un año: no hace falta tocarlo, pero un navegador que lo vio ya no acepta HTTP en ese nombre.

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
- [ ] Para actualizar después: `./tools/desplegar.ps1` (o `sudo aeroacademy actualizar`); sabes que `revertir` existe.
