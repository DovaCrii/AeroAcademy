# Regla de fusiones

Complementa `docs/FLUJO_GITHUB.md`. **La persona fusiona; el agente no.** Esta regla dice cómo.

## Reglas

1. **Quién:** solo la persona dueña del repositorio. El agente construye, sube y deja el PR listo; nunca ejecuta `gh pr merge`.
2. **Orden:** de abajo hacia arriba en la cadena apilada. El PR #1 (`bloque-0-base`) apunta a `main`; cada PR siguiente apunta a la rama del anterior.
3. **Método:** siempre **merge commit** (`gh pr merge N --merge`). **Nunca** *squash* ni *rebase*: reescriben los commits de los que depende el PR de arriba y lo dejan con conflictos.
4. **No borrar la rama** al fusionar (`--delete-branch` apagado) hasta haber fusionado todos los de arriba.
5. **Antes de fusionar un PR:**
   - su CI está en verde;
   - no tiene conflictos;
   - se reapuntó a `main` (el script lo hace);
   - se leyó su cuerpo («lo pendiente» y los avisos).
6. **El PR de correcciones de revisión va al final** (#21 hoy), porque corrige código de los bloques de abajo.
7. **Si un PR falla o genera conflictos:** se detiene toda la cadena; se corrige en la rama de ese PR y se vuelve a empezar desde él. Nunca se fuerza.
8. **`main` siempre despliega:** después de la última fusión, `main` debe pasar `python tools/preflight.py` (ver `docs/PRODUCCION.md`).
9. **Prohibido para el agente** (sin pedido explícito de la persona): fusionar, `push --force`, borrar ramas remotas, cambiar la protección de `main`, publicar *releases*.

## Cómo fusionar la cadena

Desde la carpeta del proyecto, con `gh` autenticado:

```bash
python tools/fusionar_cadena.py            # plan y comprobaciones; no cambia nada
python tools/fusionar_cadena.py --ejecutar # fusiona en orden; pide escribir «FUSIONAR N»
python tools/fusionar_cadena.py --ejecutar --hasta 8   # solo hasta el PR #8
```

El script: ordena la cadena, comprueba CI y conflictos, reapunta cada PR a `main`, espera su CI y lo fusiona con merge commit. Se detiene en el primer problema.

Fusionar a mano es equivalente: `gh pr edit N --base main` → esperar el CI → `gh pr merge N --merge`, de #1 hacia arriba.

## Después de fusionar

1. `git switch main && git pull`.
2. `python tools/preflight.py` (debe terminar en verde).
3. Seguir `docs/PRODUCCION.md`.
4. Marcar en `docs/PLAN.md` lo que quedó pendiente para la siguiente ronda.
