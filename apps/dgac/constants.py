"""Constantes de la sección DGAC / RPAS. Sin imports: las usan módulos que no deben depender de la app."""

# Ruta de entrenamiento. Su contenido (niveles, misiones, quiz) es de JEJ y se carga desde DGAC_DATA_DIR.
ROUTE_SLUG = "dgac-rpas"

# Rutas cuyo contenido es interno: no entran al índice de búsqueda ni al contexto que viaja al modelo externo de Nala.
PRIVATE_PATH_SLUGS = (ROUTE_SLUG,)

# Reglas de la prueba de conocimientos (decisión del dueño, igual que la de AeroControl).
QUESTIONS_PER_ATTEMPT = 25
PASS_PERCENT = 80
VALID_MONTHS = 12

# Credencial interna que se emite al aprobar (una por persona: aprobar de nuevo renueva la vigencia).
CREDENTIAL_ID = "DGAC-RPAS-INTERNO"
DEFAULT_DIPLOMA_TITLE = "Diploma interno RPAS"
DEFAULT_ISSUER = "Academia LEV Digital 101"

# Archivos que espera la carpeta de datos (ver docs en el informe y en `cargar_dgac`).
FILE_ROUTE = "ruta.json"
FILE_BANK = "banco.json"
FILE_OVERVIEW = "operaciones.json"
DIR_IMAGES = "infografias"
