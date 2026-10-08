# Pendientes y estado (tras los bloques 0 a 16)

Todos los bloques de `docs/PLAN.md` están construidos. Esto es lo que queda, ordenado por lo que importa para salir a producción y para el **bot de ayuda y seguimiento (Teo)**.

## Teo: ayuda y seguimiento

| Estado | Qué |
|---|---|
| ✔ Hecho | Preguntas con contexto del equipo (FTS5), citas con enlaces, límite diario, respaldo si falla la API, resumen de hilos, consulta al foro con la pregunta prellenada |
| ✔ Hecho | **Buscador de ayuda sin modelo** (`/ayuda/?q=`): funciona aunque Teo duerma; 11 guías |
| ✔ Hecho | **Seguimiento semanal** (`teo_seguimiento`, lunes 09:00): aviso en la campana a quien lleva 7 días sin avanzar con su próxima misión, y resumen a los responsables. Local: no usa la API |
| ✔ Hecho | `manage.py teo_probar`: prueba la conexión con NVIDIA y explica el fallo |
| ✔ Hecho | Atuendo de Teo por mundo (5 sprites) y expresión «celebra» al subir de nivel |
| ✔ Hecho | Recomendar recursos por habilidad y producto (entran al índice) |
| ⏳ Tuyo | **Probar con tu clave real** y elegir `NIM_MODEL` según cómo salga el español (`teo_probar`) |
| ⏳ Tuyo | Rotar la clave que se pegó antes en el chat |
| Siguiente ronda | Mostrar a Teo celebrando también al ganar una insignia; respuestas con botones («¿Qué me falta?», «¿Cómo subo un certificado?») |
| Siguiente ronda | Teo cita documentos no restringidos de la biblioteca |
| Siguiente ronda | Recordatorio al responsable por cada credencial en revisión > 7 días |
| Siguiente ronda | Correo (hoy solo el gancho `email-hook` en el log) |

## Para producción

| Estado | Qué |
|---|---|
| ✔ Hecho | `tools/preflight.py` (producción real con base temporal, 25 páginas, secretos, LF, pruebas) |
| ✔ Hecho | `tools/fusionar_cadena.py` y `docs/FUSIONES.md` (la persona fusiona) |
| ✔ Hecho | `deploy/install.sh` con `deploy/centro.env`, temporizadores de respaldo, vencimientos y seguimiento de Teo |
| ⏳ Tuyo | Fusionar la cadena (#1 → #21 y el PR de producción) |
| ⏳ Tuyo | Correr `install.sh` en la VM por primera vez (no se ha ejecutado en una VM real) |
| ⏳ Tuyo | Probar una restauración de respaldo antes de confiar en él |
| Siguiente ronda | Alertas: un aviso si el respaldo o un temporizador falla |

## Producto (no bloquea la salida)

- Fuente Press Start 2P (A10: necesita tu permiso para descargarla; hoy se usa una monoespaciada).
- `htmx.min.js` (A11: hoy `enhance.js` hace el trabajo; ver D23).
- URLs de Bentley marcadas `verify_url`: confirmarlas con una cuenta Bentley.
- Rutas nuevas (Trimble, Esri, drones/RPA) y sus mundos `survey`, `mechanical`, `aero` (los sprites de Teo ya existen).
- Exportar la hoja profesional a PDF; vista previa de PDF e imágenes de documentos; historial de ediciones de artículos; matriz exportable.
- Accesorios de avatar por nivel y expediciones del equipo (insignia *Gremio Unido*).
