# Teo · el asistente de la academia

## Quién es

**Teo** es un teodolito 8-bit con patitas cortas, casco de obra amarillo y una pequeña hélice de dron en la cabeza.
Es curioso, amable y breve, y habla como un colega de terreno ("¡Buena medición!", "Vamos a cerrar esa poligonal").
Cambia de atuendo según el mundo en el que está la persona (ver VISION y MUNDOS).

Sprites: un sprite base de 32×32 y cuatro expresiones (*neutral*, *feliz*, *pensando*, *celebra*), más un accesorio por mundo.
Se hacen con la skill `sprite-8bit`. Nombre provisorio: **A6** en DECISIONES (alternativas: Nivo, Pixi).

## Qué hace

| Acción | Ejemplo | Fuente de datos |
|---|---|---|
| Próxima misión | "¿Qué me falta en la ruta Bentley?" | Avance de la persona (se calcula en el servidor; al modelo solo llegan títulos de misiones pendientes, nunca otros datos personales) |
| Cómo usar la academia | "¿Cómo subo un certificado?" | `docs` de ayuda dentro de `assistant/help/*.md` |
| Buscar | "¿Alguien dejó notas sobre *Corridor Modeling*?" | Índice FTS5 de notas, hilos, consultas y artículos (solo contenido visible para todo el equipo) |
| Explicar términos | "¿Qué es *Superelevation*?" | Glosarios de las rutas + conocimiento del modelo |
| Recomendar recursos | "Quiero aprender nubes de puntos" | Catálogo de recursos y rutas por habilidad |
| Resumir un hilo | Botón "Resumir con Teo" en hilos largos | Texto del hilo |

Teo responde **citando** las fuentes internas con enlaces (`[Ruta Bentley · Capítulo OpenRoads](/rutas/bentley-learn/#ord)`).
Si no sabe, lo dice y sugiere abrir una consulta en el foro, con un botón que la crea con el texto prellenado.

## Cómo funciona

```
widget HTMX (esquina, sprite de Teo) → POST /teo/ask → assistant.services.answer()
   1. límite por persona (BOT_DAILY_LIMIT, por defecto 40 al día)
   2. armado de contexto: búsqueda FTS5 en SQLite (rutas, recursos, glosarios, notas, hilos, artículos, ayuda)
      + resumen del avance de quien pregunta (solo títulos de misiones pendientes)
   3. filtro de privacidad (lista blanca de modelos y campos; ver abajo)
   4. httpx → https://integrate.api.nvidia.com/v1/chat/completions (compatible con OpenAI)
   5. respuesta en Markdown sanitizado + citas → parcial HTMX
```

- **Proveedor:** NVIDIA NIM ([build.nvidia.com](https://build.nvidia.com)). Tiene uso gratuito para desarrollo, con límites que hay que revisar al crear la clave.
- **Variables:**
  - `NIM_API_KEY` (empieza con `nvapi-`), solo en `/etc/centro/env` o `.env` local.
  - `NIM_BASE_URL`, por defecto `https://integrate.api.nvidia.com/v1`.
  - `NIM_MODEL`: elegir tras probar el español, p. ej. `meta/llama-3.3-70b-instruct` o un Nemotron *instruct*. Verificar el nombre exacto en el catálogo de NIM.
  - `BOT_ENABLED`, `BOT_DAILY_LIMIT` y `BOT_TIMEOUT_S` (por defecto 20).
- **Alternativa local:** como el cliente es compatible con OpenAI, se puede apuntar `NIM_BASE_URL` a un Ollama en la VM sin cambiar código.
- **Sin dependencias nuevas** más allá de `httpx` (D16). FTS5 viene con SQLite.

## Reglas de datos (obligatorias)

**Se envía** al proveedor:
- la pregunta;
- fragmentos de rutas, recursos, glosarios, notas, hilos y artículos visibles para todo el equipo;
- títulos de misiones pendientes de quien pregunta;
- su nombre visible.

**Nunca se envía:**
- nada de `credentials`: ni archivos, ni ID de credencial, ni URL de verificación, ni fechas;
- correos o logins de Tailscale;
- documentos restringidos de `library`;
- notas borradas;
- datos de otras personas que no estén en contenido público del foro.

Implementación:
- El armado de contexto usa una **lista blanca** de modelos y campos (`assistant/context.py`). Una prueba verifica que ningún campo de `credentials` ni de `Person.login` puede llegar al *payload*.
- El log guarda solo los metadatos: persona, fecha, tokens, latencia y si hubo error. **No** guarda el texto de la pregunta ni el de la respuesta.

## Prompt del sistema (base)

> Eres Teo, el asistente de la Academia LEV Digital 101 de AeroAcademy. Respondes en español, breve y cercano, como un
> colega de terreno. Los comandos de software van en inglés tal como aparecen en pantalla. Usa solo el CONTEXTO
> entregado para hablar de la academia, sus rutas, notas y foro, y cita con los enlaces dados. Si el contexto no
> alcanza, dilo y sugiere abrir una consulta. Nunca inventes URLs, cursos ni certificaciones. No pidas ni repitas
> datos personales.

## Fallos

- Con `BOT_ENABLED=False` o sin clave, el widget muestra a Teo "durmiendo" y enlaza a la ayuda y al foro. El sitio funciona igual.
- Con un error de la API o un *timeout*, Teo responde "Se me empañó el lente, intenta de nuevo en un rato" y se registra el error.
- Al superar el límite diario: "Por hoy medí suficiente, ¡mañana seguimos!"

## Pruebas

- Con `httpx.MockTransport`: respuesta normal, *timeout*, 401 y 429.
- Prueba de privacidad: se crea una credencial con un ID único y se verifica que no aparece en ningún *payload*.
- Prueba del límite diario y de `BOT_ENABLED=False`.
