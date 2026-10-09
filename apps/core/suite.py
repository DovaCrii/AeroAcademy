"""Suite Aero: el software propio que auspicia la academia.

`app_url` es la aplicación en vivo (tailnet) de las activas; `url` es el repositorio público (Código). Los repositorios privados no llevan enlace. status: active (en uso) o soon (en desarrollo).

`logo` es el nombre del archivo en core/static/core/img/suite/: `<logo>.svg` (fondo claro) y `<logo>-oscuro.svg`
(fondo oscuro). Son las marcas originales de cada repositorio de DovaCrii (assets/*-mark.svg); si falta el
archivo se usa el ícono dibujado `icon`.
"""

GITHUB = "https://github.com/DovaCrii"
LIVE = "https://p340.tailccd107.ts.net"

SUITE_AERO = [
    {
        "name": "AeroControl",
        "logo": "AeroControl",
        "app_url": f"{LIVE}/",
        "icon": "s-control",
        "status": "active",
        "blurb": "Centro de operaciones RPA/UAS: flota, tripulación, cumplimiento y vuelo.",
        "url": f"{GITHUB}/AeroControl",
    },
    {
        "name": "AeroPlanner",
        "logo": "AeroPlanner",
        "app_url": None,
        "icon": "s-planner",
        "status": "soon",
        "blurb": "Planificación y simulación de misiones: del polígono al KMZ que vuela.",
        "url": None,
    },
    {
        "name": "AeroLink",
        "logo": "AeroLink",
        "app_url": None,
        "icon": "s-link",
        "status": "soon",
        "blurb": "Telemetría y evidencia de vuelo con hash verificable.",
        "url": None,
    },
    {
        "name": "AeroBim",
        "logo": "AeroBim",
        "app_url": f"{LIVE}:10000/",
        "icon": "s-bim",
        "status": "active",
        "blurb": "Visor y coordinador BIM en el navegador: IFC, nubes de puntos y BCF.",
        "url": f"{GITHUB}/AeroBim",
    },
    {
        "name": "AeroConvert",
        "logo": "AeroConvert",
        "app_url": f"{LIVE}:8443/",
        "icon": "s-convert",
        "status": "active",
        "blurb": "Conversor de formatos geoespaciales que explica por qué un archivo no abre.",
        "url": f"{GITHUB}/AeroConvert",
    },
]

SPONSOR_TEXT = (
    "Levantamiento Digital 101 cuenta con el auspicio de Suite Aero: software propio para operar, "
    "planificar y coordinar proyectos de captura, geoespacial y BIM."
)
