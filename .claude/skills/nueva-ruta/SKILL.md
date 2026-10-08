---
name: nueva-ruta
description: Crea o valida un JSON de ruta de aprendizaje en seed/rutas/ de AeroAcademy (structured o external_track) con vendor, productos, disciplinas, mundo y keys estables. Usar al agregar una ruta nueva (Autodesk, Bentley, Trimble, Esri…), sumar cursos o niveles, o revisar una ruta existente.
---

# Nueva ruta (o cambio de ruta)

Referencias de formato:
- `seed/rutas/forma-revit.json`: `structured`, mundo `architecture`.
- `seed/rutas/bentley-learn.json`: `external_track`, mundo `civil`.

Taxonomía en `docs/TAXONOMIA.md`.

## Pasos

1. **Preguntar o deducir:**
   - vendor y productos (deben existir en `seed/vendors.json`; si no, agregarlos al final);
   - disciplinas;
   - tipo de ruta;
   - mundo (por defecto, el `default_world` de la disciplina principal);
   - plataforma (`seed/plataformas.json`).
2. **Cabecera obligatoria:** `slug`, `title`, `program`, `platform`, `kind`, `vendor`, `products[]`, `disciplines[]`, `world`, `description`.
3. **Niveles (capítulos):**
   - Campos: `code`, `order`, `short`, `title`, `estimated_hours`, `audience`, `goal`, `resources[]`.
   - En `structured`: `milestones[]` (`nX-tY`), `quiz[]` (`nX-qY`) y `mastery_signals[]`.
   - En `external_track`: `external_courses[]` (`<code>-cY`) con `title`, `kind`, `url`, `duration_text`, `reward` (`trophy` | `relic`), `is_required` y `skills[]`. Opcionales: `contains[]`, `disciplines[]` y `verify_url`.
   - Un capítulo final de **Cursos libres** si `allow_free_courses`.
   - En el mundo `civil`, los títulos de capítulo llevan progresiva (`km 0+000 · …`).
4. **URLs:**
   - Abrir cada URL en el navegador y confirmar que el título coincide.
   - Si solo se llega al catálogo, poner esa URL con `"verify_url": true`.
   - Nunca inventar URLs ni nombres de cursos.
5. **Keys estables (D7):**
   - Si la ruta ya existe, **no renumerar**: agregar al final.
   - Si se quita un elemento, se marca `"retired": true`; no se borra.
6. **Términos de software** en inglés, tal como aparecen en pantalla; en el texto, marcarlos con `*término*`.
7. **Validar:**
   ```bash
   python -m json.tool seed/rutas/<slug>.json > NUL
   uv run python manage.py seed_catalog --dry-run   # valida rutas, insignias, títulos y foro; usar una base migrada
   ```
   Revisar además: keys únicas por ruta; productos, disciplinas y plataforma existentes; `world` válido (`architecture`, `civil`, `survey`, `mechanical`, `aero`).
8. **Si el mundo aún no existe**, avisar y sugerir la skill `nuevo-mundo`.
