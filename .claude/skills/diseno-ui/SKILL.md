---
name: diseno-ui
description: Método de diseño visual y UX de AeroAcademy con las skills externas fijadas (ui-ux-pro-max, frontend-design, web-design-guidelines) y el verificador de contraste - qué skill usar en cada fase, qué fuentes de verdad mandan y qué se comprueba antes del PR. Usar al mejorar el aspecto de una pantalla, revisar UX/UI, crear o rediseñar un mundo, figura, portada o componente, o auditar accesibilidad y contraste.
---

# Diseño UI y UX

Reparto (`orquestar`): **Opus 5.5 medio** (`disenador`) consulta, decide y escribe el plan; **Sonnet 5.5 medio**
(`bloque-dev`) implementa; **Haiku 5.5 medio** (`verificador`) corre la auditoría y el contraste y lista hallazgos.

## Fuentes de verdad (mandan sobre cualquier skill externa)

- `apps/core/static/core/tokens.css`: tokens de color, tipografía, forma y sombras, claro y oscuro.
- `docs/VISION.md`, `docs/MUNDOS.md`, `docs/REFERENCIAS_DISENO.md`, `docs/ICONOS.md`, `design/academia/index.html`.
- **No se crea** `design-system/MASTER.md` ni otro archivo de tokens: sería una segunda fuente de verdad.
  Por eso `ui-ux-pro-max` nunca se corre con `--persist` en este repo.
- Si una skill externa recomienda cambiar la paleta base, la tipografía o la gramática de un mundo, **no se aplica**:
  se anota como pregunta abierta en `docs/DECISIONES.md` con la recomendación.

## Qué skill para qué

| Fase | Skill | Uso en AeroAcademy |
|---|---|---|
| Entender / Diseñar | `ui-ux-pro-max` | Solo consulta: `python .claude/skills/ui-ux-pro-max/scripts/search.py "<consulta>" --domain ux` (también `typography`, `color`, `charts`, `motion`). No hay stack Django/CSS propio en su lista: `--stack html-tailwind` sirve **solo** como referencia de patrones HTML/CSS, traducidos a CSS propio. Nunca se agrega Tailwind. |
| Diseñar (pieza nueva) | `frontend-design` | Dirección estética de un mundo, figura, portada o hito visual. Subordinada a `tokens.css` y a `docs/MUNDOS.md`; aporta composición, jerarquía y movimiento, no reemplaza la identidad «Aerotop». |
| Verificar | `web-design-guidelines` | Sobre las plantillas y CSS tocados: `/web-design-guidelines apps/<app>/templates/**/*.html`. Las reglas pensadas para React se leen en su equivalente HTML. |
| Verificar | `scripts/contrast.py` | Contraste WCAG de los tokens en claro y oscuro (ver abajo). |

## Restricciones fijas (de `AGENTS.md`)

Sin framework JS ni build de frontend; todo funciona sin JS (`enhance.js` solo mejora); 375 px; claro y oscuro;
toda animación dentro de `prefers-reduced-motion: no-preference`; fuentes locales, sin CDN; texto de interfaz en español.

## Contraste: pares base

```bash
python .claude/skills/diseno-ui/scripts/contrast.py apps/core/static/core/tokens.css \
  --pair ink:bg --pair ink-2:sheet --pair amber-ink:bg --pair on-amber:amber \
  --pair on-btn:btn --pair level:bg --pair red:sheet
```

Umbral 4.5:1 (texto normal). Para texto grande, iconos y bordes de controles: `--min 3`. Al agregar un token de texto
o de fondo, se suma su par a esta lista en el mismo PR. `--auto` sirve para explorar; sus hallazgos se confirman con el
uso real antes de corregir. Colores sueltos (sprites, SVG): `--hex "#RRGGBB:#RRGGBB"`.

## Criterio de listo de un cambio visual

1. Plan en `docs/MEJORAS_<tema>.md` (hallazgos, P0/P1/P2, archivos, criterios) cuando el cambio no es trivial.
2. `contrast.py` con los pares base en verde y los nuevos agregados.
3. `web-design-guidelines` sin hallazgos nuevos en los archivos tocados (los preexistentes se listan, no se arreglan fuera de alcance).
4. Revisado sin JS, a 375 px y en claro y oscuro.
5. `uv run pytest`, `ruff`, `privacy_scan.py` en verde, como siempre.
