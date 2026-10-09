"""Módulos de la portada (docs/VISION.md). Un módulo está "disponible" si tiene `url_name`."""

MODULES = [
    {
        "id": "rutas",
        "doodle": "rutas",
        "icon": "i-prog",
        "title": "Rutas",
        "subtitle": "Campañas por empresa de software, con su avance.",
        "description": "Una ruta por empresa y producto: Autodesk, Bentley, Trimble… Cada una con recursos "
        "oficiales, misiones y certificados, en el diseño de su especialidad.",
        "items": [
            "Pestañas por empresa de software y filtros por disciplina",
            "Rutas estructuradas y rutas con certificado externo",
            "Un mundo visual distinto por especialidad",
        ],
        "url_name": "paths:index",
        "block": "Bloques 2 y 3",
    },
    {
        "id": "catalogo",
        "doodle": "catalogo",
        "icon": "i-book",
        "title": "Catálogo",
        "subtitle": "Cursos, módulos, tutoriales y exámenes.",
        "description": "Todos los recursos de todas las plataformas en un solo buscador, con filtros por "
        "plataforma, tipo, gratuito y certificado.",
        "items": [
            "Búsqueda por título y descripción",
            "Filtros por plataforma, tipo y certificado",
        ],
        "url_name": "catalog:resources",
        "block": "Bloque 2",
    },
    {
        "id": "equipo",
        "doodle": "equipo",
        "icon": "i-team",
        "title": "Equipo",
        "subtitle": "Hojas de personaje: clase, nivel, título e insignias.",
        "description": "Directorio del equipo con la hoja de personaje de cada persona, en vista de juego o "
        "profesional, y la matriz de competencias.",
        "items": [
            "Clase, nivel, título e insignias",
            "Credenciales validadas por persona",
            "A quién preguntar por cada software",
        ],
        "url_name": "team:board",
        "block": "Bloques 7 y 14",
    },
    {
        "id": "cert",
        "doodle": "certificados",
        "icon": "i-cert",
        "title": "Certificaciones",
        "subtitle": "Tus certificados, con evidencia y vencimientos.",
        "description": "Repositorio de certificados: cursos, certificaciones oficiales y habilitaciones con "
        "vencimiento. El moderador los valida y desbloquean XP e insignias.",
        "items": [
            "Archivo privado, emisor, ID y URL de verificación",
            "Validación por el moderador",
            "Avisos de vencimiento y exportación para licitaciones",
        ],
        "url_name": "credentials:mine",
        "block": "Bloques 5 y 6",
    },
    {
        "id": "docs",
        "doodle": "documentos",
        "icon": "i-docs",
        "title": "Documentos",
        "subtitle": "Manuales, guías, planos tipo y normativas.",
        "description": "Biblioteca técnica con versiones, por disciplina y tipo de documento.",
        "items": ["Versión vigente e historial", "Plantillas y familias del estándar"],
        "url_name": "library:index",
        "block": "Bloque 9",
    },
    {
        "id": "foro",
        "doodle": "foro",
        "icon": "i-forum",
        "title": "Foro",
        "subtitle": "Conversa, pregunta y comparte con el equipo.",
        "description": "Hilos por categoría y disciplina, consultas con respuesta aceptada y las notas de "
        "cada ruta.",
        "items": ["Hilos y consultas", "Respuesta aceptada como solución", "Moderación del equipo"],
        "url_name": "community:forum",
        "block": "Bloques 4, 10 y 16",
    },
    {
        "id": "conoc",
        "doodle": "conocimiento",
        "icon": "i-know",
        "title": "Conocimiento",
        "subtitle": "Lecciones aprendidas y mejoras en marcha.",
        "description": "Base de conocimiento y tablero de mejoras: Ideas → Plan → Ejecución → Resultados.",
        "items": ["Lecciones aprendidas y procedimientos", "Propuestas de mejora con estado"],
        "url_name": "knowledge:index",
        "block": "Bloque 11",
    },
]

VALUES = [
    ("i-comm", "Una comunidad de profesionales"),
    ("i-book", "Información organizada"),
    ("i-share", "Colaboración sin límites"),
    ("i-badge", "Aprendizaje continuo"),
    ("i-chart", "Un solo lugar para avanzar"),
]

# Fotos por disciplina (core/static/core/img). Captura/RPA todavía no tiene foto propia.
DISCIPLINE_VISUALS = {
    "arquitectura": {"icon": "i-arq", "img": "arquitectura.jpg", "label": "Arquitectura"},
    "civil-estructural": {"icon": "i-civ", "img": "civil.jpg", "label": "Civil · Estructural"},
    "topografia": {"icon": "i-top", "img": "topografia.jpg", "label": "Topografía"},
    "mecanica": {"icon": "i-mec", "img": "mecanica.jpg", "label": "Mecánica"},
    "transversal": {"icon": "i-prog", "img": "", "label": "Transversal"},
    "captura-rpa": {"icon": "i-aero", "img": "", "label": "Captura · RPA"},
}
