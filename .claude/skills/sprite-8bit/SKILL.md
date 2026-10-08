---
name: sprite-8bit
description: Dibuja sprites pixel-art como SVG para AeroAcademy (avatares por capas, insignias, Teo y sus atuendos) con la grilla y paleta del proyecto. Usar al crear o modificar cualquier sprite 8-bit.
---

# Sprites 8-bit en SVG

## Grilla

| Tipo | Tamaño | Escala de visualización |
|---|---|---|
| Insignia | 32×32 | × 2 o × 3 |
| Insignia mini (listas) | 16×16 | |
| Avatar | 32×32 | por capas: base → outfit → accessory → frame |
| Teo | 32×32 | expresiones: `neutral`, `feliz`, `pensando`, `celebra` |

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

## Teo

- Cuerpo: un teodolito con un anteojo horizontal como "ojos" y una base trípode de tres patitas.
- Casco amarillo arriba y una hélice cian de dos aspas sobre el casco.
- **Atuendos por mundo** (capa `accessory`, misma grilla):

  | Mundo | Atuendo |
  |---|---|
  | `architecture` | Lápiz tras la oreja |
  | `civil` | Chaleco reflectante |
  | `survey` | Sombrero de explorador |
  | `mechanical` | Llave inglesa |
  | `aero` | Gafas de piloto |

## Entrega

1. Guardar en `core/static/game/` (`badges/`, `avatar/<layer>/` o `teo/`).
2. Revisar a × 1, × 2 y × 3 sobre fondo claro y oscuro: legible, sin píxeles sueltos y con contorno continuo.
