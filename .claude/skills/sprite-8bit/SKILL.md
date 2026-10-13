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
| Nala | 48×48 | `idle`, `neutral`, `happy`, `thinking`, `celebra`, `sleep` + un atuendo por mundo |

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

- **Nala es la perra real del dueño: una golden retriever ADULTA**, dibujada **de frente, sentada y tierna** (proporción chibi: cabeza ~50 % del alto, cuerpo pequeño). Rasgos golden: cráneo ancho y redondo, orejas triangulares suaves color albaricoque (`#B97A3A`) colgando a ambos lados con puntas plumosas, hocico crema con nariz negra y sonrisa suave, ojos grandes oscuros con brillo, golilla crema esponjosa en el pecho, patas delanteras juntas con patitas crema redondeadas y cola en plumero asomando a la derecha.
- **Grilla 48×48** (`viewBox="0 0 48 48"`, `width`/`height` 48; las plantillas fijan el tamaño con `<img width=…>`: 40–48 px en el widget, 96 px en home). Un `<path>` por color con corridas horizontales, `shape-rendering="crispEdges"`, < 8 KB por archivo.
- Paleta: contorno `#3A2410` (café oscuro, nunca negro), pelaje `#E7C27D`, crema `#F5E2B8`, sombra `#C9944E`, orejas `#B97A3A`, nariz y ojos `#1E1410`, brillo `#FFFFFF`, lengua `#E8788A`. Accesorios: casco `#FFC21A`, chaleco `#FF7A1A`, gafas `#4CC6FF`, acero `#8A99A8`.
- Método: formas rellenas simétricas (espejo en x) por capas (cola, cuerpo, ancas, golilla, patas, cabeza con orejas) y contorno automático en los píxeles transparentes vecinos; la cabeza se dibuja en su propia capa y se inclina con un cizallado por filas. Símbolos (`?`, `z`, chispas) en ámbar `#FFC21A` con sombra café de 1 px (legibles en claro y oscuro). Revisar siempre a 48 y 192 px sobre `#041126` y `#FAF8F3`.
- Poses: `idle` (sonrisa, cola media), `neutral` (boca recta, cola baja), `happy` (lengua, ojos en arco, cabeza ladeada, cola en alto), `celebra` (salto, patas arriba, chispas), `thinking` (cabeza ladeada, pata en el mentón, `?`), `sleep` (echada, cabeza sobre las patas, ojos cerrados, tres `z`).
- Doodle: `core/static/core/img/doodles/nala.svg` (tinta `currentColor`, rellenos planos) es la misma perra, de frente y tierna.- Archivos en `core/static/game/teo/` (el nombre de archivo se mantiene): `idle`, `happy`, `celebra`, `neutral`, `thinking`, `sleep` y un atuendo por mundo.
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
