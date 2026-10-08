# Moderación y avisos

El dueño del proyecto es el **Maestro del gremio**: rol `admin` + `lead` (D10). En el futuro se puede nombrar más leads.

## Alta de personas (D11)

1. Una persona entra por la tailnet y se crea su `Person` con `status = pending`.
2. Ve la página "Esperando aprobación", con Teo saludando, y no ve ningún contenido del equipo.
3. El moderador recibe una notificación y la ve en **Moderación → Personas por aprobar**, donde:
   - **aprueba**, y asigna rol, disciplina y clase sugerida;
   - o **rechaza**.
4. Al aprobar, la persona recibe un aviso de bienvenida y su primera misión: "Completa tu hoja de personaje", que otorga la insignia *Hoja Completa*.
5. `suspended` corta el acceso sin borrar datos. El historial y los certificados se conservan.

## Foro y consultas

Acciones del moderador sobre los hilos:
- **fijar**: queda arriba en su categoría;
- **cerrar**: no admite respuestas;
- **ocultar**: borrado lógico, con motivo;
- **mover** de categoría o disciplina;
- **editar el título**;
- **marcar la respuesta aceptada** si el autor no lo hace.

**Reportar:** cualquier miembro puede reportar un post o una nota indicando el motivo. Los reportes llegan a la cola del moderador.

**Bitácora de moderación:** cada acción queda registrada en un `ModerationLog` con actor, acción, objeto, motivo y fecha. Solo el moderador la ve.

**Normas del foro**, publicadas como hilo fijado al iniciar:
- Respeto, y preguntar sin miedo.
- Nada de datos personales ni de clientes en el foro.
- Términos de software en inglés, como aparecen en pantalla.
- Si te resolvieron la duda, marca la respuesta aceptada.

## Certificados

El moderador también valida credenciales (Bloque 5): **verificar** o **rechazar con comentario**. Es lo que libera el XP grande (D13).
Cola: **Moderación → Certificados por revisar**, ordenada por antigüedad.

## Notificaciones (dentro de la app)

La campana de la cabecera muestra un contador y una lista con estos eventos:

| Evento | Para |
|---|---|
| Persona nueva pendiente | Moderador |
| Credencial enviada a revisión | Moderador |
| Credencial verificada / rechazada | Dueño de la credencial |
| Insignia ganada / subida de nivel | Persona |
| Respuesta a mi hilo, nota o consulta | Autor |
| Mi respuesta fue aceptada | Autor de la respuesta |
| Credencial por vencer (60 días) / vencida | Dueño y moderador |
| Anuncio del moderador | Todos |

**Anuncios:** el moderador publica un anuncio (título, texto y fecha de expiración), que aparece como banda en la portada y como notificación a todos.
**Correo:** fuera del MVP. Se deja una función `notify()` con el canal `in_app` y un gancho para `email` (Bloque 8).

## Plantillas de anuncios

- **Expedición del mes:** "Este mes el gremio va por 6 trofeos Bentley. Barra común en la portada. ¡Todos suman!"
- **Ruta nueva:** "Se abrió la campaña *{ruta}* en el mundo {mundo}. Teo ya conoce el camino."
- **Recordatorio de vencimientos:** "Hay {n} credenciales que vencen en los próximos 60 días. Revisa tu hoja."
