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
| ✔ Hecho | Atajos locales («¿Qué me falta?», «¿Qué vence pronto?», «Recomiéndame un curso», «¿Cómo subo un certificado?»), sin API |
| ✔ Hecho | Teo cita documentos no restringidos de la biblioteca |
| ✔ Hecho | El resumen semanal avisa de certificados en revisión hace más de 7 días |
| ✔ Hecho | Modelo vigente con respaldos automáticos y `teo_probar --buscar` (modelos que de verdad responden con tu cuenta) |
| Siguiente ronda | Mostrar a Teo celebrando también al ganar una insignia |
| Siguiente ronda | Correo (hoy solo el gancho `email-hook` en el log) |

## Para producción

| Estado | Qué |
|---|---|
| ✔ Hecho | `tools/preflight.py` (producción real con base temporal, 25 páginas, secretos, LF, pruebas) |
| ✔ Hecho | `tools/fusionar_cadena.py` y `docs/FUSIONES.md` (la persona fusiona) |
| ✔ Hecho | `deploy/install.sh` con `deploy/centro.env`, temporizadores de respaldo, vencimientos y seguimiento de Teo |
| ✔ Hecho | Cadena fusionada (#1 → #34) e instalada en p340 con nodo Tailscale propio (`https://aeroacademy.tailccd107.ts.net`) |
| ✔ Hecho | Alertas: aviso a los responsables si el respaldo o un temporizador falla (`centro-alerta@`) |
| ✔ Hecho | Primer día: `aprobar` y `puesta_en_marcha` desde la VM (`sudo aeroacademy …`), hilo de bienvenida fijado, «Primeros pasos» en la portada, ícono y manifiesto para instalar como app |
| ✔ Hecho | Teo sin razonamiento a la vista (`enable_thinking: false`, limpieza y paso al modelo siguiente) |
| ⏳ Tuyo | Entrar como admin (tu correo **de Tailscale** en `BOOTSTRAP_ADMINS`, o `sudo aeroacademy aprobar`); invitar a `cmunoz@jej.cl` y al equipo a la tailnet o compartirles el equipo `aeroacademy` |
| ⏳ Tuyo | Rotar la clave de NVIDIA (se pegó en el chat) |
| ⏳ Tuyo | Probar una restauración de respaldo antes de confiar en él |

## Producto (no bloquea la salida)

- Fuente Press Start 2P (A10: necesita tu permiso para descargarla; hoy se usa una monoespaciada).
- `htmx.min.js` (A11: hoy `enhance.js` hace el trabajo; ver D23).
- URLs de Bentley marcadas `verify_url`: confirmarlas con una cuenta Bentley.
- Rutas nuevas (Trimble, Esri, drones/RPA) y sus mundos `survey`, `mechanical`, `aero` (los sprites de Nala ya existen).
- Exportar la hoja profesional a PDF; vista previa de PDF e imágenes de documentos; historial de ediciones de artículos; matriz exportable.
- Accesorios de avatar por nivel y expediciones del equipo (insignia *Gremio Unido*).
- **Avatares y opciones de visualización (pedido 2026-10-09):** más piezas de avatar, vistas alternativas (compacta / juego / profesional) y preferencias de visualización por persona.
- Sprites de Nala: el teodolito (`teo-survey`) y el dron (`teo-aero`) se leen poco a 48 px; «pensando» se nota solo en los ojos.
