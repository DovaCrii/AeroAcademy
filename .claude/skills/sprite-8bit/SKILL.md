---
name: sprite-8bit
description: Dibuja sprites pixel-art como SVG para AeroAcademy (avatares por capas, insignias, Nala (la mascota) y sus atuendos) con la grilla y paleta del proyecto. Usar al crear o modificar cualquier sprite 8-bit.
---

# Sprites 8-bit en SVG

> **Avatares de personas:** no se dibujan a mano como SVG. Viven en `apps/gamification/avatar/parts/` como arte ASCII
> por capas (grilla **32×32**) y se documentan en `docs/AVATARES_PIXEL.md`. Para una pieza nueva: lanza el subagente
> `artista-pixel`, valida con `python tools/validate_part.py <categoría>`, míralo con `tools/preview_avatar.py` y regenera
> `design/avatares/galeria.html`. Esta skill cubre el resto: insignias, Nala y sprites sueltos.

## Grilla

| Tipo | Tamaño | Escala de visualización |
|---|---|---|
| Insignia | 32×32 | × 2 o × 3 |
| Insignia mini (listas) | 16×16 | |
| Avatar | 32×32 | por capas: base → outfit → accessory → frame |
| Nala | 32×32 | expresiones: `neutral`, `feliz`, `pensando`, `celebra` |

## Técnica

- `<svg viewBox="0 0 32 32" shape-rendering="crispEdges">` con un `<rect>` por píxel o por corrida horizontal, para que pese poco.
- Colores mediante `var(--px-*)` con *fallback* fijo, para que se adapten a los modos claro y oscuro:
  `fill="var(--px-ink, #0A0E13)"`.
- Sin degradados ni filtros. El brillo de las legendarias es una animación CSS aparte, desactivable.
- `role="img"` + `<title>` en español.
- Mostrar con `image-rendering: pixelated` si se usa como `<img>`.

## Paleta (máx. 12 colores por sprite)

| Token | Hex | Uso |
|---|---|---|
| `--px-ink` | `#0A0E13` | Contorno |
| `--px-white` | `#FFFFFF` | Brillo |
| `--px-blue` | `#1E8CFF` | Acento de marca |
| `--px-cyan` | `#4CC6FF` | Acento de marca, HUD |
| `--px-yellow` | `#FFC21A` | Casco, señalética |
| `--px-orange` | `#FF5A00` | Scan |
| `--px-red` | `#E5322A` | Cota, alerta |
| `--px-green` | `#13803C` | Ok, talud |
| `--px-steel` | `#8A99A8` | Metal |
| `--px-asphalt` | `#2B2F36` | Asfalto |
| `--px-skin-1..4` | | Tonos de piel del avatar |

Marco por rareza:

| Rareza | Color |
|---|---|
| Común | `#8D9CAD` |
| Rara | `#1E8CFF` |
| Épica | `#8B5CF6` |
| Legendaria | `#FFC21A` |

## Nala (D32)

- Cachorrita golden retriever sentada de frente: pelaje dorado `#E0A040`, hocico y pecho crema `#F6D9A0`, sombra ámbar `#B8661A`, contorno café `#2A1606`, lengua `#F27A93`; orejas caídas y cola esponjosa.
- Archivos en `core/static/game/teo/` (el nombre de archivo se mantiene): `idle`, `happy`, `celebra`, `neutral`, `thinking`, `sleep` y un atuendo por mundo.
- **Atuendos por mundo** (capa `accessory`, misma grilla):

  | Mundo | Atuendo |
  |---|---|
  | `architecture` | Casco amarillo y plano enrollado |
  | `civil` | Casco y chaleco reflectante |
  | `survey` | Teodolito en trípode a su lado |
  | `mechanical` | Gafas de seguridad y llave inglesa |
  | `aero` | Gafas de piloto y dron pequeño |

## Entrega

1. Guardar en `core/static/game/` (`badges/`, `avatar/<layer>/` o `teo/`).
2. Revisar a × 1, × 2 y × 3 sobre fondo claro y oscuro: legible, sin píxeles sueltos y con contorno continuo.
