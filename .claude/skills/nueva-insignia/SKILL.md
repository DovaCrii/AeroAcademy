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
4. Sprite: skill `sprite-8bit`, 32×32, con el marco del color de la rareza; guardarlo en `core/static/game/badges/<slug>.svg`.
5. Prueba: un caso que la otorga, un caso al límite que no la otorga y, si depende de credenciales, la revocación al rechazar.

## Título

- Agregarlo a `seed/titulos.json` con `min_level` o `badge`, y `character_class` si es variante de clase.
- Mantener la progresión: un título nuevo de nivel no debe quedar en el mismo nivel que otro general.

## Accesorio de avatar

- `AvatarItem` con `layer` y `unlock_rule` (mismo formato que las reglas de insignia).
- El sprite debe calzar en la grilla del avatar base de 32×32.

## Antitrampa (D13)

Nada que se pueda repetir sin evidencia da XP grande. Si la insignia depende de acciones repetibles, ponerle tope diario o exigir una credencial verificada.
