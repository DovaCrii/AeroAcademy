---
name: nueva-insignia
description: Agrega insignias, títulos o accesorios de avatar a la capa de juego de AeroAcademy con su regla, rareza, sprite 8-bit y prueba. Usar al pedir una insignia nueva, un título, un desbloqueable o al ajustar el XP.
---

# Nueva insignia, título o desbloqueable

Reparto (`orquestar`): **Opus 5.5 medio** decide nombre, rareza, regla y antitrampa; **Sonnet 5.5 medio**
(`curador-semillas` para la semilla, `artista-pixel` para el sprite) implementa; **Haiku 5.5 medio** valida.
Leer `docs/GAMIFICACION.md` (vocabulario, XP, rarezas, tipos de regla).

## Insignia

1. **Definir (Opus):** nombre breve (ingeniería + D&D, en español), descripción que diga **cómo** se gana y rareza:
   `common` primeros pasos · `rare` constancia o colección chica · `epic` reliquia o campaña · `legendary` campaña larga
   o logro excepcional.
2. **Regla existente:** `count`, `path_complete`, `distinct_vendors`, `streak`, `credential_kind` o `manual`. Un tipo
   nuevo se propone en `docs/DECISIONES.md` antes de implementarlo. Eventos de `count`: los `kind` de `XPEvent`; un
   módulo nuevo los entrega con `game.award(person, source, kind)`.
3. **Semilla:** al final de `seed/insignias.json`.
4. **Sprite:** skill `sprite-8bit` (marco por rareza ahí), en `apps/core/static/game/badges/` con el nombre de `sprite`.
5. **Validar:** `uv run python manage.py seed_catalog --dry-run` (falla con regla desconocida, campos faltantes, slug
   repetido o sprite inexistente).
6. **Prueba** en `tests/test_game.py`: la otorga, al límite no la otorga y, si depende de credenciales, se revoca al rechazar.

## Título

Al final de `seed/titulos.json` con `min_level` o `badge` (y `character_class` si es variante). Un título de nivel nuevo
no comparte nivel con otro general.

## Accesorio de avatar

Se desbloquea con una insignia en `engine.UNLOCKS` (`apps/gamification/avatar/`); `clean_config(unlocked=)` valida en el
servidor. Pieza con `artista-pixel` y `python tools/audit_avatar.py`.

## Antitrampa (D13)

Nada repetible sin evidencia da XP grande: tope diario o credencial verificada.
