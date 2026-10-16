---
name: revision-privacidad
description: Revisa que un cambio no exponga secretos, datos de clientes ni datos personales antes de publicarlo en un repositorio público (incluye fotos privadas de cursos y semillas). Usar antes de cada push o PR y al agregar archivos, imágenes, ejemplos o datos de prueba.
---

# Revisión de privacidad (repositorio público)

Reparto: **Haiku 5.5 medio** (`verificador`) corre el escáner y lista; **Opus 5.5 medio** lee el diff y decide. Si algo
dudoso toca datos de clientes o personales, se pregunta a la persona; no se resuelve solo.

1. **Diff completo:** `git status`, `git diff --stat` y `git diff` contra la base (incluye archivos nuevos y binarios).
2. **Busca en lo que se agrega:**
   - claves y tokens (`nvapi-`, `sk-`, `AKIA`, `ghp_`, `PRIVATE KEY`), contraseñas, `.env`, `.pem`, `.pfx`, `.key`;
   - correos reales, RUT, teléfonos, direcciones, nombres de clientes o de personas;
   - datos de proyectos (nubes de puntos, planos, bases de datos, exportaciones, precios, procedimientos internos);
   - capturas con barras de URL, usuarios o rutas personales; fotos con personas o con datos de obra identificables.
3. **Cursos y semillas:** las fotos propias van como `"image": "priv:<archivo>"` y el archivo en
   `private/cursos/<slug>/fotos/` (fuera de git, instalado solo en la VM). Nada privado al índice del asistente.
4. **Corre** `python tools/kit/privacy_scan.py`. Un hallazgo se corrige quitando el dato, no relajando la regla. Solo un
   falso positivo claro (dominio ficticio, ruta de pruebas) va a `.privacy-scan.json`, con la razón en el PR.
5. **Dónde va lo sensible:** `private/`, variables de entorno o un gestor de secretos. Ejemplos con `persona@example.com`.
6. **Si algo ya se subió:** avisa de inmediato. Borrarlo en otro commit no lo saca del historial: hay que rotar la clave
   y decidir con la persona cómo limpiar. No reescribas ramas compartidas.
7. **Informe:** qué revisaste, qué encontraste, qué corregiste.
