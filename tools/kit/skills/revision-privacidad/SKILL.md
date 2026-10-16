---
name: revision-privacidad
description: Revisa que un cambio no exponga secretos, datos de clientes ni datos personales antes de publicarlo en un repositorio {{VISIBILIDAD}}. Usar antes de cada push o PR y al agregar archivos, imágenes, ejemplos o datos de prueba.
---

# Revisión de privacidad (repositorio {{VISIBILIDAD}})

Reparto: **Haiku 5.5 medio** corre el escáner y lista; **Opus 5.5 medio** lee el diff y decide. Si algo dudoso toca
datos de clientes o personales, se pregunta a la persona.

1. **Diff completo:** `git status`, `git diff --stat` y `git diff` contra la base (incluye archivos nuevos y binarios).
2. **Busca en lo que se agrega:**
   - claves y tokens (`nvapi-`, `sk-`, `AKIA`, `ghp_`, `PRIVATE KEY`), contraseñas, `.env`, `.pem`, `.pfx`, `.key`;
   - correos reales, RUT, teléfonos, direcciones, nombres de clientes o de personas;
   - datos de proyectos (nubes de puntos, planos, bases de datos, exportaciones, precios, procedimientos internos);
   - capturas con barras de URL, usuarios o rutas personales; fotos con personas o datos identificables.
3. **Corre** `python tools/kit/privacy_scan.py`. Un hallazgo se corrige quitando el dato, no relajando la regla. Solo un
   falso positivo claro va a `.privacy-scan.json`, con la razón en el PR.
4. **Dónde va lo sensible:** `private/` (ignorado por git), variables de entorno o un gestor de secretos. Ejemplos con
   `persona@example.com`.
5. **Si algo ya se subió:** avisa de inmediato; rotar la clave y decidir con la persona cómo limpiar el historial. No
   reescribas ramas compartidas.
6. **Informe:** qué revisaste, qué encontraste, qué corregiste.
