# Guía para compañeros: crear o mejorar contenido con Claude Code

Para quien no es desarrollador pero quiere agregar o mejorar contenido (cursos, textos, rutas, documentos) en un
proyecto de la suite Aero. Claude Code hace el trabajo técnico; tú decides y revisas. Nada llega a producción sin que una
persona revise y fusione.

## 1. Instalar (una vez)

1. Instala Git y Claude Code (instrucciones en code.claude.com/docs) e inicia sesión con tu cuenta de trabajo.
2. Instala GitHub CLI (`gh`) y ejecuta `gh auth login` con tu usuario.
3. Clona el proyecto: `git clone <URL-del-repositorio>`.

## 2. Abrir el proyecto

```bash
cd <carpeta-del-proyecto>
git switch main && git pull
claude
```

Claude lee `CLAUDE.md` y `AGENTS.md` solo; ahí están las reglas del proyecto.

## 3. Pedir un plan antes de cambiar nada

Escribe qué quieres en lenguaje normal y pide plan primero. Ejemplo:

> Quiero agregar un curso corto de «Introducción a nubes de puntos». Antes de editar nada, muéstrame un plan:
> qué archivos tocarías, qué texto escribirías y cómo lo probamos.

Lee el plan. Si algo no te cuadra, corrígelo en el chat. Solo cuando estés de acuerdo di «adelante».

## 4. Trabajar en una rama

Pide: «crea una rama `contenido-<tema>` y trabaja ahí». Nunca trabajes directo sobre `main`.
Avanza en pasos chicos y pide que corra las pruebas después de cada uno.

## 5. Revisar el diff

Antes de entregar pide: «muéstrame el diff y resume qué cambió». Revísalo tú:
¿cambió solo lo que pediste? ¿hay datos que no deberían estar? Pide la revisión de privacidad
(«usa la skill revision-privacidad»).

## 6. Abrir el PR

Pide: «sube la rama y abre el PR con la plantilla». Espera el CI (la marca verde en GitHub).
Un PR en rojo no está listo: pídele a Claude que lo arregle. Luego Claude lo fusiona cuando el CI esté en verde; **tú no despliegas** a menos que te lo pidan.

## Nunca pegues ni subas (ni en el chat de Claude ni en archivos)

- Claves de API, tokens, contraseñas, archivos `.env`.
- Certificados digitales, llaves privadas (`.pem`, `.pfx`, `.key`).
- Datos de clientes: nombres, planos, nubes de puntos, bases de datos, contratos, informes con identificación.
- Datos personales: RUT, correos o teléfonos reales, direcciones, fotos de personas.
- Capturas de pantalla con barras de URL, sesiones abiertas o nombres de usuario.

Si necesitas un ejemplo, usa datos inventados (`persona@example.com`). Si pegaste algo sensible por error, **avisa de inmediato**
antes de seguir: puede haber que cambiar una clave.

## Si algo sale mal

No pasa nada: todo está en una rama. Di «deshaz el último cambio» o simplemente cierra la rama sin fusionar y pide ayuda.
Nunca uses `push --force`, nunca borres el repositorio ni cambies sus ajustes.
