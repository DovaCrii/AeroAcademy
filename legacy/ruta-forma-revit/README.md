# Ruta Forma + Revit · servidor del equipo

Guía de aprendizaje interactiva (Forma + Revit) con avance por persona, notas del equipo y casillas compartidas.
Corre en una VM propia y se publica **solo dentro de la tailnet**. La identidad de cada persona la entrega
Tailscale, así que no hay usuarios ni contraseñas que administrar.

```
navegador (tailnet) ──HTTPS──> tailscale serve ──> 127.0.0.1:8080 (FastAPI) ──> SQLite
                                 └ agrega Tailscale-User-Login / -Name / -Profile-Pic
```

## Estructura

| Ruta | Qué es |
|---|---|
| `static/index.html` | La guía completa (HTML + CSS + JS, sin build) |
| `static/fonts/Archivo.woff2` | Tipografía local (OFL), para que no dependa de Google Fonts |
| `app/main.py` | API: `/api/me`, `/api/state`, `/api/progress`, `/api/notes`, `/api/shared/{key}` |
| `deploy/install.sh` | Instala o actualiza en la VM (idempotente) |
| `deploy/forma-ruta.service` | Servicio systemd |
| `deploy/backup.sh` | Respaldo de la base SQLite |

## 1. Requisitos en la VM

- Ubuntu/Debian con Tailscale instalado y la VM unida a la tailnet.
- En la consola de Tailscale: **MagicDNS** y **HTTPS Certificates** activados (DNS → HTTPS Certificates).

## 2. Subir e instalar (desde tu PC)

```bash
# copiar el proyecto a la VM por SSH (usa el nombre MagicDNS o la IP 100.x de la VM)
rsync -av --exclude data ./forma-ruta/ usuario@nombre-vm:/tmp/forma-ruta/

# instalar
ssh usuario@nombre-vm "sudo bash /tmp/forma-ruta/deploy/install.sh"
```

Al terminar, `tailscale serve status` muestra la URL, del tipo `https://nombre-vm.tu-tailnet.ts.net/`.
Compártela con el equipo: solo funciona para quienes estén en la tailnet.

## 3. Actualizar

Edita `static/index.html` (contenido, niveles, enlaces) o `app/main.py`, y repite el paso 2.
Los datos viven en `/var/lib/forma-ruta/ruta.db` y no se tocan al actualizar.

## 4. Operación

```bash
sudo systemctl status forma-ruta          # estado
sudo journalctl -u forma-ruta -f          # logs
sudo /opt/forma-ruta/deploy/backup.sh     # respaldo manual
# respaldo diario a las 02:00
echo "0 2 * * * root /opt/forma-ruta/deploy/backup.sh" | sudo tee /etc/cron.d/forma-ruta-backup
```

## 5. Probar en tu PC sin Tailscale

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
RUTA_DEV_USER=tu@correo.cl uvicorn app.main:app --port 8080
# abre http://127.0.0.1:8080
```

`RUTA_DEV_USER` simula una identidad. **No lo uses en la VM**: ahí la identidad debe venir de Tailscale.

## Fotos propias (recomendado)

La portada y las tres bandas muestran una nube de puntos generada. Para usar fotos reales del equipo,
copia JPG en `static/img/` con estos nombres y se aplican solas (si falta alguna, se mantiene la nube):

| Archivo | Dónde aparece | Sugerencia |
|---|---|---|
| `portada.jpg` | Portada CC 410 | Ortofoto o vista de nube de puntos de un levantamiento, 2400 px de ancho |
| `captura.jpg` | Banda D1 "De la nube al modelo" | Dron o escáner en terreno |
| `equipo.jpg` | Banda D2 "Un equipo, un flujo" | Equipo trabajando o modelo BIM en pantalla |
| `terreno.jpg` | Banda D3 "Preparar el estándar" | Modelo de terreno o plano |

Usa imágenes propias o con permiso; el lado izquierdo queda oscurecido para que el texto se lea.

## Seguridad

- El servicio escucha solo en `127.0.0.1`; nadie llega a él si no es a través de `tailscale serve`.
- No uses `tailscale funnel`: expondría la guía a internet sin identidad.
- Dispositivos con *tags* no envían identidad de usuario; entra desde un equipo con usuario de la tailnet.
- Cada persona solo puede borrar sus propias notas. El avance personal se guarda por usuario.

## Cómo se comporta la página

La misma `index.html` funciona en tres modos y elige sola:
1. **Servidor del equipo** (esta VM): todo compartido, sincroniza cada 8 s.
2. **claude.ai**: si se publica como artifact, usa el almacenamiento de claude.ai.
3. **Local**: abierta como archivo, guarda solo en el navegador.
