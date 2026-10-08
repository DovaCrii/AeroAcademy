---
name: nueva-insignia
description: Agrega insignias, títulos o accesorios de avatar a la capa de juego de AeroAcademy con su regla, rareza, sprite 8-bit y prueba. Usar al pedir una insignia nueva, un título, un desbloqueable o al ajustar el XP.
---

# Nueva insignia, título o desbloqueable

Leer `docs/GAMIFICACION.md`: vocabulario, XP, rarezas y tipos de regla.

## Insignia

1. Definir el nombre (lenguaje de ingeniería + D&D, en español, breve), la descripción (una frase que diga **cómo** se gana) y la rareza:
   - `common`: primeros pasos;
   - `rare`: constancia o una colección pequeña;
   - `epic`: una reliquia o una campaña;
   - `legendary`: una campaña larga completa o un logro excepcional.
2. Elegir el tipo de regla que ya existe: `count`, `path_complete`, `distinct_vendors`, `streak`, `credential_kind` o `manual`. Si ninguno sirve, proponer el tipo nuevo en DECISIONES antes de implementarlo.
3. Agregar la insignia **al final** de `seed/insignias.json`.
4. Sprite: skill `sprite-8bit` (subagente `artista-pixel`), 16×16 en el estilo de los existentes (marco de la rareza: común `#8D9CAD`, rara `#1E8CFF`, épica `#8B5CF6`, legendaria `#FFC21A`); guardarlo en `apps/core/static/game/badges/` con el nombre del campo `sprite`.
5. Validar: `uv run python manage.py seed_catalog --dry-run` falla si la regla es desconocida, le faltan campos, el slug se repite o no existe el sprite. Eventos de `count`: son los `kind` de `XPEvent` (`milestone`, `note`, `accepted_answer`, `free_course_promoted`, `profile_completed`); un módulo nuevo los entrega con `game.award(person, source, kind)`.
6. Prueba (en `tests/test_game.py`): un caso que la otorga, un caso al límite que no la otorga y, si depende de credenciales, la revocación al rechazar.

## Título

- Agregarlo a `seed/titulos.json` con `min_level` o `badge`, y `character_class` si es variante de clase.
- Mantener la progresión: un título nuevo de nivel no debe quedar en el mismo nivel que otro general.

## Accesorio de avatar

- Las piezas del avatar piden una insignia en `engine.UNLOCKS` (`apps/gamification/avatar/`); `clean_config(unlocked=)` valida en el servidor.
- Usar la skill `sprite-8bit` y `tools/audit_avatar.py`.

## Antitrampa (D13)

Nada que se pueda repetir sin evidencia da XP grande. Si la insignia depende de acciones repetibles, ponerle tope diario o exigir una credencial verificada.
