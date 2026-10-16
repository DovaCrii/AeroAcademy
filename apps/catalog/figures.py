"""Kit de figuras: cada ruta usa una figura y un vocabulario de su tema (docs/MEJORAS_UX.md P1-9, docs/MUNDOS.md).

Una *figura* es la metáfora con la que se dibuja el avance de una ruta (corte de edificio, pipeline de IA, perfil
topográfico…). Cada una trae sus rótulos (`labels`): línea de la portada, escala, nombres de ejes, títulos de sección y
pie de lámina. Las plantillas de los mundos leen `fig.labels.*` en lugar de texto fijo.

La figura de una ruta sale de su JSON (`"figure"` en `seed/rutas/<slug>.json`, o en `private/cursos/<slug>/ruta.json`)
y se lee al dibujar, como `guide` y `slides`: no hay campo en la base ni migración. Sin campo, o con uno que no sirve
para el tipo de ruta, se usa la figura por defecto de su disciplina.
"""

from dataclasses import dataclass, field

from . import guides, software

# Palabras del vocabulario de arquitectura: fuera de una figura que las trae, no deben aparecer (`FORBIDDEN`).
ARCH_WORDS = (
    "cota",
    "lámina",
    "dibujo y modelado",
    "+3,50",
    "pilar",
    "estaca",
    "planta y perfil",
    "corte a-a",
)

STRUCTURED, EXTERNAL = "structured", "external_track"
BOTH = (STRUCTURED, EXTERNAL)

# Texto que toda figura debe poder mostrar; cada una sobrescribe lo suyo.
BASE_LABELS = {
    "kicker": "Herramienta transversal",  # línea sobre el título de la portada
    "scene": "terrain",  # nube de puntos de fondo: `building` o `terrain`
    "scale": "ESCALA 1:100",  # regla de la portada
    "sheet_label": "Hoja",  # pie de lámina: etiqueta y valor
    "sheet": "H-101",
    "mark": "H-201",  # círculo de la sección «Niveles»
    "content": "Avance por etapa",  # pie de lámina: «Contenido»
    "unit_label": "Ritmo",
    "unit_value": "A tu ritmo",
    "figure_title": "Recorrido",  # título de la sección de la figura
    "levels_title": "Etapas",
    "levels_sub": "Elige una etapa para ver sus recursos y misiones.",
    "browser": "Explorador · Etapas",
    "item": "Etapa",  # singular y plural de la unidad que dibuja la figura
    "items": "etapas",
    "done_label": "etapas completas",
    "zero": "",  # cota cero (solo el corte de edificio)
    # Rutas externas (mundo civil): vocabulario de la portada, la cinta y la leyenda
    "ext_lead": "es una estación del recorrido; cada acreditación suma al avance. Lo verificado es tu avance.",
    "ext_levels": "Capítulos",
    "ext_verified": "Cursos verificados",
    "ext_relics": "Acreditaciones",
    "ext_meta_levels": "capítulos completos",
    "ext_meta_relics": "acreditaciones obtenidas",
    "ext_legend": (("ok", "Verificado"), ("pend", "En revisión"), ("none", "Por hacer")),
}


STACK_TEMPLATE = "worlds/figures/stack.html"
# Figuras ya dibujadas; el resto usa la pila de capas con su propio vocabulario (se agregan de a dos, ver MUNDOS).
DRAWN = {
    "building",
    "building-lod",
    "road-profile",
    "flight-plan",
    "stack",
    "pipeline-ai",
    "data-flow",
    "survey-profile",
    "survey-gis",
    "capture-twin",
    "plant-iso",
    "doc-flow",
}


@dataclass(frozen=True)
class Figure:
    key: str
    accent: str  # clave de acento (`software.ARQ`…): colores de la portada y la banda
    labels: dict
    template: str = ""  # figura para rutas estructuradas (vacío: la genérica `stack`)
    external_template: str = ""  # si es distinta para rutas externas (cursos como estaciones)
    kinds: tuple = BOTH
    vocab: frozenset = field(
        default_factory=frozenset
    )  # palabras de ARCH_WORDS que esta figura sí usa
    layout: str = "stack"  # geometría que calcula `figure_layout.layout`

    @property
    def drawn(self):
        return self.key in DRAWN

    def template_for(self, kind):
        if not self.drawn:
            return STACK_TEMPLATE
        if kind == EXTERNAL and self.external_template:
            return self.external_template
        return self.template or STACK_TEMPLATE


def _labels(**kw):
    return {**BASE_LABELS, **kw}


def _lod(i):
    return f"LOD {(100, 200, 300, 350, 400, 500)[min(i, 5)]}"


def _building_elev(i):
    return f"+{i * 3.5:.2f}".replace(".", ",")


_F = "worlds/figures/"
FIGURES = {
    f.key: f
    for f in (
        Figure(
            "building",
            software.ARQ,
            _labels(
                kicker="Levantamiento digital",
                scene="building",
                scale="ESCALA 1:500",
                sheet_label="Lámina",
                sheet="A-101",
                mark="A-201",
                content="Corte A-A · avance personal y del equipo",
                unit_label="Escala",
                levels_title="Niveles",
                levels_sub="Elige un nivel en el navegador de proyecto, como en Revit.",
                browser="Project Browser · Levels",
                item="Nivel",
                items="niveles",
                done_label="niveles completos",
                zero="COTA ±0,00",
            ),
            template=_F + "building.html",
            kinds=(STRUCTURED,),
            vocab=frozenset({"cota", "lámina", "+3,50", "corte a-a"}),
            layout="building",
        ),
        Figure(
            "building-lod",
            software.ARQ,
            _labels(
                kicker="Levantamiento digital",
                scene="building",
                scale="ESCALA 1:500",
                sheet_label="Lámina",
                sheet="A-101",
                mark="A-201",
                content="Corte por nivel de desarrollo · avance personal y del equipo",
                unit_label="Escala",
                levels_title="Niveles",
                levels_sub="Cada nivel sube un grado de desarrollo (LOD): elígelo en el navegador de proyecto.",
                browser="Project Browser · Levels",
                item="Nivel",
                items="niveles",
                done_label="niveles completos",
                zero="LOD 100 · base",
            ),
            template=_F + "building.html",
            kinds=(STRUCTURED,),
            vocab=frozenset({"lámina", "corte a-a"}),
            layout="building",
        ),
        Figure(
            "road-profile",
            software.CIV,
            _labels(
                kicker="Topografía y diseño vial",
                scene="terrain",
                scale="ESCALA 1:1000",
                sheet_label="Lámina",
                sheet="C-101",
                mark="C-201",
                content="Planta-perfil · avance por kilómetro",
                unit_label="Escala",
                figure_title="Planta y perfil",
                levels_title="Kilómetros",
                levels_sub="Cada kilómetro es una etapa del camino: elígela en el Explorer, como en Civil 3D.",
                browser="Explorer · Etapas",
                item="Etapa",
                items="etapas",
                done_label="etapas completas",
                ext_lead="es una estaca; cada acreditación levanta un pilar del puente. El tramo pavimentado es tu avance verificado.",
                ext_levels="Corredores",
                ext_verified="Estacas verificadas",
                ext_relics="Pilares",
                ext_meta_levels="corredores completos",
                ext_meta_relics="pilares en pie",
                ext_legend=(
                    ("ok", "Verificado"),
                    ("pend", "En revisión"),
                    ("none", "Por hacer"),
                    ("relic", "Pilar = acreditación"),
                    ("road", "Tramo pavimentado"),
                ),
            ),
            template=_F + "road-profile.html",
            external_template=_F + "corridor.html",
            vocab=frozenset({"estaca", "pilar", "planta y perfil", "lámina"}),
            layout="road-profile",
        ),
        Figure(
            "survey-profile",
            software.TOP,
            _labels(
                kicker="Topografía",
                scale="DATUM · PR",
                sheet_label="Plano",
                sheet="T-101",
                mark="T-201",
                content="Perfil topográfico · avance por punto de control",
                figure_title="Perfil topográfico",
                levels_title="Puntos de control",
                levels_sub="Elige un punto de referencia (PR) del perfil para ver sus recursos y misiones.",
                browser="Cartas · Puntos de control",
                item="PR",
                items="puntos de control",
                done_label="puntos levantados",
                axis="COTA",
                base="DATUM",
                ext_lead="es un punto de control del perfil; cada acreditación fija un vértice. Lo verificado es tu avance.",
                ext_levels="Puntos",
                ext_meta_levels="puntos levantados",
            ),
            template=_F + "survey-profile.html",
            vocab=frozenset({"cota", "lámina"}),
            layout="survey",
        ),
        Figure(
            "survey-gis",
            software.TOP,
            _labels(
                kicker="Topografía y datos espaciales",
                scale="CRS · CAPAS",
                sheet_label="Mapa",
                sheet="G-101",
                mark="G-201",
                content="Capas del mapa · avance por capa",
                figure_title="Capas del mapa",
                levels_title="Capas",
                levels_sub="Elige una capa del mapa para ver sus recursos y misiones.",
                browser="Catálogo · Capas",
                item="Capa",
                items="capas",
                done_label="capas cargadas",
                axis="VALOR",
                base="CRS",
                ext_levels="Capas",
                ext_meta_levels="capas cargadas",
            ),
            template=_F + "survey-profile.html",
            layout="survey",
        ),
        Figure(
            "pipeline-ai",
            software.IAD,
            _labels(
                kicker="Inteligencia artificial",
                scale="VENTANA · TOKENS",
                sheet_label="Pipeline",
                sheet="P-101",
                mark="P-201",
                content="Pipeline · avance por capa",
                figure_title="Pipeline",
                levels_title="Capas",
                levels_sub="Elige una capa del pipeline para ver sus recursos y misiones.",
                browser="Pipeline · Capas",
                item="Capa",
                items="capas",
                done_label="capas completas",
                window="VENTANA DE CONTEXTO",
                chips=("DATOS", "MODELO", "AGENTE"),
            ),
            template=_F + "pipeline-ai.html",
            layout="pipeline",
        ),
        Figure(
            "data-flow",
            software.IAD,
            _labels(
                kicker="Análisis de datos",
                scale="DATASET · PANEL",
                sheet_label="Notebook",
                sheet="N-101",
                mark="N-201",
                content="Flujo de datos · avance por etapa",
                figure_title="Flujo de datos",
                levels_title="Etapas",
                levels_sub="Elige una etapa del flujo, de la ingesta al informe.",
                browser="Datos · Etapas",
                item="Etapa",
                items="etapas",
                done_label="etapas completas",
                chips=("INGESTA", "LIMPIEZA", "ANÁLISIS", "INFORME"),
            ),
            template=_F + "data-flow.html",
            layout="cylinders",
        ),
        Figure(
            "capture-twin",
            software.CAP,
            _labels(
                kicker="Captura y gemelo digital",
                scale="NUBE → GEMELO",
                sheet_label="Escena",
                sheet="R-101",
                mark="R-201",
                content="Captura de realidad · avance por fase",
                figure_title="Del escaneo al gemelo",
                levels_title="Fases",
                levels_sub="Elige una fase de la captura: del escaneo al gemelo con sensores.",
                browser="Realidad · Fases",
                item="Fase",
                items="fases",
                done_label="fases completas",
                chips=("CAPTURA", "NUBE", "MALLA", "iMODEL", "SENSOR"),
                ext_lead="es una fase de la captura; cada acreditación suma al gemelo. Lo verificado es tu avance.",
                ext_levels="Fases",
                ext_verified="Cursos verificados",
                ext_meta_levels="fases completas",
            ),
            template=_F + "capture-twin.html",
            layout="tiles",
        ),
        Figure(
            "plant-iso",
            software.MEC,
            _labels(
                kicker="Plantas y tuberías",
                scale="ISO 30°",
                sheet_label="Isométrico",
                sheet="I-101",
                mark="I-201",
                content="P&ID → isométrico · avance por tramo",
                figure_title="Isométrico de tuberías",
                levels_title="Tramos",
                levels_sub="Elige un tramo de la línea para ver sus recursos y misiones.",
                browser="Líneas · Tramos",
                item="Tramo",
                items="tramos",
                done_label="tramos completos",
                chips=("P&ID", "ISO"),
                ext_lead="es un tramo de la línea; cada acreditación abre una válvula. Lo verificado es tu avance.",
                ext_levels="Tramos",
                ext_meta_levels="tramos completos",
            ),
            template=_F + "plant-iso.html",
            layout="iso",
        ),
        Figure(
            "doc-flow",
            software.TRA,
            _labels(
                kicker="Gestión documental",
                scale="VERSIÓN · ESTADO",
                sheet_label="Registro",
                sheet="D-101",
                mark="D-201",
                content="Flujo de documentos · avance por documento",
                figure_title="WIP → Compartido → Publicado",
                levels_title="Documentos",
                levels_sub="Elige un documento del flujo para ver sus recursos y misiones.",
                browser="Documentos · Estados",
                item="Documento",
                items="documentos",
                done_label="documentos publicados",
                lanes=("WIP", "Compartido", "Publicado"),
                ext_lead="es un documento del flujo; cada acreditación lo lleva de WIP a publicado. Lo verificado es tu avance.",
                ext_levels="Documentos",
                ext_meta_levels="documentos publicados",
            ),
            template=_F + "doc-flow.html",
            layout="lanes",
        ),
        Figure(
            "viz-scene",
            software.ARQ,
            _labels(
                kicker="Visualización",
                scale="CÁMARA · LUZ",
                sheet_label="Escena",
                sheet="V-101",
                mark="V-201",
                content="Escena y render · avance por toma",
                figure_title="Escena y render",
                levels_title="Tomas",
                levels_sub="Elige una toma de la escena para ver sus recursos y misiones.",
                browser="Escena · Tomas",
                item="Toma",
                items="tomas",
                done_label="tomas renderizadas",
                chips=("ESCENA", "CÁMARA", "LUZ", "RENDER"),
                ext_lead="es una toma de la escena; cada acreditación la lleva a render. Lo verificado es tu avance.",
                ext_levels="Tomas",
                ext_meta_levels="tomas renderizadas",
            ),
            template=_F + "viz-scene.html",
            layout="frames",
        ),
        Figure(
            "building-model",
            software.ARQ,
            _labels(
                kicker="Modelo de edificio",
                scene="building",
                scale="ESCALA 1:200",
                sheet_label="Modelo",
                sheet="M-101",
                mark="M-201",
                content="Modelo por disciplinas · avance por modelo",
                figure_title="Modelo por disciplinas",
                levels_title="Modelos",
                levels_sub="Elige un modelo para ver sus recursos y misiones; entre todos forman la coordinación.",
                browser="Modelo · Disciplinas",
                item="Modelo",
                items="modelos",
                done_label="modelos completos",
                ext_lead="es un modelo del edificio; cada acreditación lo suma a la coordinación. Lo verificado es tu avance.",
                ext_levels="Modelos",
                ext_meta_levels="modelos completos",
            ),
            template=_F + "building-model.html",
            layout="iso-stack",
        ),
        Figure(
            "drafting-sheet",
            software.TRA,
            _labels(
                kicker="Dibujo técnico",
                scale="ESCALA 1:50",
                sheet_label="Lámina",
                sheet="D-101",
                mark="D-201",
                content="Lámina con capas, bloques y XREF · avance por capa",
                figure_title="Lámina de dibujo",
                levels_title="Capas",
                levels_sub="Elige una capa de la lámina para ver sus recursos y misiones.",
                browser="Administrador de capas",
                item="Capa",
                items="capas",
                done_label="capas completas",
            ),
            template=_F + "drafting-sheet.html",
            vocab=frozenset({"lámina"}),
            layout="sheet",
        ),
        Figure(
            "flight-plan",
            software.CAP,
            _labels(
                kicker="Captura / RPA",
                scale="ESCALA 1:2000",
                sheet_label="Hoja",
                sheet="WP-101",
                mark="WP",
                content="Waypoints · avance personal y del equipo",
                figure_title="Plan de vuelo",
                levels_title="Waypoints",
                levels_sub="Elige un waypoint en la lista.",
                browser="Plan de vuelo",
                item="Waypoint",
                items="waypoints",
                done_label="waypoints alcanzados",
            ),
            template=_F + "flight-plan.html",
            kinds=(STRUCTURED,),
            layout="flight-plan",
        ),
        Figure(
            "stack",
            software.TRA,
            _labels(
                kicker="Herramienta transversal",
                scale="PILA DE CAPAS",
                sheet_label="Hoja",
                sheet="H-101",
                mark="H-201",
                content="Pila de capas · avance por etapa",
                figure_title="Pila de capas",
            ),
            template=_F + "stack.html",
            layout="stack",
        ),
    )
}

# Figura por defecto según la disciplina de la ruta (acento de `software.discipline_key`).
DEFAULT_BY_DISCIPLINE = {
    software.ARQ: "building",
    software.CIV: "road-profile",
    software.TOP: "survey-profile",
    software.MEC: "plant-iso",
    software.CAP: "capture-twin",
    software.TRA: "stack",
    software.IAD: "pipeline-ai",
}


def valid_figure(key, kind=None):
    """True si `key` es una figura conocida y (si se da `kind`) sirve para ese tipo de ruta."""
    fig = FIGURES.get(key) if isinstance(key, str) else None
    return fig is not None and (kind is None or kind in fig.kinds)


def figure_key(path):
    """Clave de la figura de una ruta: la de su JSON, y si falta o no sirve, la de su disciplina (o `stack`)."""
    named = guides.figure_name(path.slug)
    if valid_figure(named, path.kind):
        return named
    if path.world == "aero" and path.kind == STRUCTURED:
        return "flight-plan"
    default = DEFAULT_BY_DISCIPLINE.get(software.discipline_key(path), "stack")
    return default if valid_figure(default, path.kind) else "stack"


def for_path(path):
    """Figura de la ruta lista para las plantillas: {key, accent, template, labels, vocab}. Se guarda en la instancia."""
    cached = getattr(path, "_figure", None)
    if cached is not None:
        return cached
    fig = FIGURES[figure_key(path)]
    out = {
        "key": fig.key,
        "accent": fig.accent,
        "template": fig.template_for(path.kind),
        "labels": fig.labels,
        "vocab": fig.vocab,
        "layout": fig.layout if fig.drawn else "stack",
    }
    path._figure = out
    return out


def forbidden_words(key):
    """Palabras de arquitectura que NO deben aparecer en la figura `key` (lista `ARCH_WORDS` menos su vocabulario)."""
    return tuple(w for w in ARCH_WORDS if w not in FIGURES[key].vocab)


FORBIDDEN = {key: forbidden_words(key) for key in FIGURES}


def step_label(key):
    """Función que rotula la cota de cada piso en el corte del edificio (solo `building` y `building-lod`)."""
    return _lod if key == "building-lod" else _building_elev
