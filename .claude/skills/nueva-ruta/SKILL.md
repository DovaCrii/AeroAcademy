---
name: nueva-ruta
description: Crea, amplía o valida una ruta de aprendizaje de AeroAcademy (seed/rutas/<slug>.json, structured o external_track) - cabecera, niveles, diapositivas (slides con diagram y fotos priv:), quiz, keys estables, icono único (ROUTE_ICON), mundo/figura, categoría del foro y enlaces verificados. Usar al agregar una ruta (Autodesk, Bentley, Trimble, Esri, cursos propios), sumar cursos o niveles, o revisar una existente.
---

# Nueva ruta (o cambio de ruta)

Reparto (`orquestar`): **Opus 5.5 medio** decide alcance, nivelación y fuentes y revisa el JSON; **Sonnet 5.5 medio**
(`curador-semillas`) lo escribe; **Haiku 5.5 medio** (`verificador`) valida enlaces y corre las comprobaciones.

Manda el código: esquema vigente en `apps/catalog/guides.py` y `seed/rutas/topografia-101.json`; plantilla, tabla de
campos y checklist de autoría en `docs/CURSOS.md` §5; taxonomía en `docs/TAXONOMIA.md`. Ejemplos:
`forma-revit.json` (`structured`), `bentley-learn.json` (`external_track`).

## Pasos

1. **Decidir (Opus):** vendor y productos (`seed/vendors.json`; si faltan, al final), disciplinas, `kind`, plataforma
   (`seed/plataformas.json`), `world` (`architecture`, `civil`, `survey`, `mechanical`, `aero`; por defecto el de la
   disciplina) y `figure`: la metáfora y el vocabulario con que se dibuja el avance de la ruta (`apps/catalog/figures.py`,\n   tabla en `docs/MUNDOS.md`; sin campo se usa la de su disciplina). Que el tema de la ruta no muestre vocabulario ajeno:\n   fuera de `building`, ni «COTA», ni «Lámina», ni «Dibujo y modelado». Mundo o figura inexistente: skill `nuevo-mundo`.
2. **Cabecera:** `slug`, `title`, `program`, `platform`, `kind`, `vendor`, `products[]`, `disciplines[]`, `world`, `figure`, `description`.
3. **Niveles:** `code`, `order`, `short`, `title`, `estimated_hours`, `audience`, `goal`, `resources[]`.
   - `structured`: `milestones[]` (`nX-tY`), `quiz[]` (`nX-qY`, ≥ 4–6 de escenario, respuesta en posición variada,
     `explanation` siempre), `mastery_signals[]`, `guide` y `slides[]` (6–10: concepto → cómo funciona → ejemplo de
     terreno → errores → resumen; `title`, `body`, `points`, `image`, `callout`, `terms`, `diagram`).
   - `diagram`: `nodes` ≤ 12 (`id` `[a-z0-9_-]`, `x`/`y` en % de 16:9), `edges` ≤ 16 (`flow: true` anima), `steps`
     opcionales. Debe leerse sin JS.
   - `image`: `core/img/…svg` propio o `priv:<archivo>` en `private/cursos/<slug>/fotos/` (nunca en git; skill
     `revision-privacidad`). Sin la foto instalada, la diapositiva muestra solo texto.
   - `external_track`: `external_courses[]` (`<code>-cY`) con `title`, `kind`, `url`, `duration_text`, `reward`
     (`trophy` | `relic`), `is_required`, `skills[]`; opcionales `contains[]`, `disciplines[]`, `verify_url`.
   - Capítulo final **Cursos libres** si `allow_free_courses`. En `civil`, títulos con progresiva (`km 0+000 · …`).
4. **Keys estables (D7):** `code`, `nX-tY`, `nX-qY` solo se agregan al final; lo que sale lleva `"retired": true`.
5. **Texto:** palabras propias, sin copiar; términos de software en inglés como en pantalla, marcados `*término*`;
   cursos generales sin marcas; líneas de diapositiva ≤ 70 caracteres.
6. **URLs:** abrir cada una y confirmar el título. Solo el catálogo: esa URL con `"verify_url": true`. Nunca inventar.
7. **Icono único:** `apps/core/static/core/img/software/ruta-<slug>.svg` propio, el slug en `ROUTE_ICON`
   (`apps/catalog/software.py`) y la fila en `docs/ICONOS.md` (encargo a `artista-pixel` si hace falta dibujarlo).
8. **Foro:** si la ruta abre un tema nuevo, su categoría al final de `seed/foro.json` (slugs estables).
9. **Validar (Haiku):**
   ```bash
   python -m json.tool seed/rutas/<slug>.json > NUL
   uv run python manage.py seed_catalog --dry-run      # base migrada nueva
   uv run pytest -q tests/test_slides.py tests/test_software_guides.py tests/test_catalog_paths.py tests/test_seed_game.py tests/test_figures.py
   uv run python manage.py revisar_enlaces --solo-externos
   ```
   Luego recorrer la ruta en el navegador: escritorio y 375 px, claro y oscuro, y sin JS.
