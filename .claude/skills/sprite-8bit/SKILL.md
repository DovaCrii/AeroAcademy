---
name: sprite-8bit
description: Dibuja sprites pixel-art de AeroAcademy - insignias SVG, Nala (la mascota) con sus poses y atuendos por mundo, y encarga las piezas de avatar 32×32 por capas - con la grilla y paleta del proyecto, legibles en claro y oscuro. Usar al crear o modificar cualquier sprite 8-bit.
---

# Sprites 8-bit

Reparto (`orquestar`): **Opus 5.5 medio** fija el encargo (qué piezas, contrato, criterios) y revisa las hojas;
**Sonnet 5.5 medio** (`artista-pixel`) dibuja; **Haiku 5.5 medio** corre los validadores.

**Avatares de personas:** no son SVG a mano. Arte ASCII por capas (32×32) en `apps/gamification/avatar/parts/`,
documentado en `docs/AVATARES_PIXEL.md`: encargo a `artista-pixel`, `python tools/validate_part.py <categoría>`,
`python tools/preview_avatar.py` y regenerar `design/avatares/galeria.html`. Esta skill cubre el resto.

## Grilla y técnica

| Tipo | Tamaño | Dónde |
|---|---|---|
| Insignia | 32×32 (mini 16×16) | `apps/core/static/game/badges/` |
| Nala | 48×48 | `apps/core/static/game/teo/teo-<pose|mundo>.svg` (el código conserva `teo`, D32) |

- `shape-rendering="crispEdges"`, un `<rect>`/`<path>` por color con corridas horizontales; < 8 KB por archivo.
- Colores con `var(--px-*)` y *fallback* fijo (`fill="var(--px-ink, #0A0E13)"`); sin degradados ni filtros (el brillo
  legendario es CSS aparte y desactivable). `role="img"` + `<title>` en español; `image-rendering: pixelated` en `<img>`.

## Paleta (máx. 12 colores por sprite)

`--px-ink #0A0E13` contorno · `--px-white #FFFFFF` brillo · `--px-blue #1E8CFF` y `--px-cyan #4CC6FF` marca/HUD ·
`--px-yellow #FFC21A` casco · `--px-orange #FF5A00` scan · `--px-red #E5322A` cota/alerta · `--px-green #13803C` ok ·
`--px-steel #8A99A8` metal · `--px-asphalt #2B2F36` asfalto · `--px-skin-1..4` piel.

Marco por rareza: común `#8D9CAD` · rara `#1E8CFF` · épica `#8B5CF6` · legendaria `#FFC21A`.

## Nala (D32)

- Golden retriever **adulta**, de frente, sentada y tierna (chibi: cabeza ~50 % del alto). Cráneo ancho, orejas
  albaricoque colgando con puntas plumosas, hocico crema, nariz negra, ojos grandes con brillo, golilla crema, patitas
  juntas, cola en plumero a la derecha.
- Paleta: contorno `#3A2410` (nunca negro), pelaje `#E7C27D`, crema `#F5E2B8`, sombra `#C9944E`, orejas `#B97A3A`,
  nariz y ojos `#1E1410`, brillo `#FFFFFF`, lengua `#E8788A`. Accesorios: casco `#FFC21A`, chaleco `#FF7A1A`, gafas
  `#4CC6FF`, acero `#8A99A8`. Símbolos (`?`, `z`, chispas) en `#FFC21A` con sombra café de 1 px.
- Método: capas simétricas (cola, cuerpo, ancas, golilla, patas, cabeza) con contorno automático; la cabeza se inclina con
  cizallado por filas.
- Poses: `idle`, `neutral`, `happy`, `celebra`, `thinking` (`?`), `sleep` (tres `z`).
- Atuendo por mundo: `architecture` casco y plano · `civil` casco y chaleco · `survey` teodolito · `mechanical` gafas
  y llave · `aero` gafas de piloto y dron. Figuras temáticas nuevas siguen la misma grilla.
- Doodle: `apps/core/static/core/img/doodles/nala.svg` (tinta `currentColor`), la misma perra.

## Entrega

Revisar a ×1, ×2 y ×3 (Nala a 48 y 192 px) sobre `#041126` y `#FAF8F3`: legible, sin píxeles sueltos, contorno continuo.
