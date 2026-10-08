from django.urls import reverse

from apps.catalog.models import Discipline, Resource
from apps.paths.models import LearningPath

from . import dashboard
from .modules import DISCIPLINE_VISUALS, MODULES, VALUES
from .suite import SPONSOR_TEXT, SUITE_AERO


def _visible_paths(person):
    qs = LearningPath.objects.select_related("vendor").prefetch_related("disciplines")
    return qs if person.is_lead else qs.filter(is_published=True)


def home_context(person):
    """Todo lo que necesita la ventana de bienvenida."""
    paths = list(_visible_paths(person))
    disciplines = []
    for d in Discipline.objects.all():
        visual = DISCIPLINE_VISUALS.get(d.slug, {"icon": "i-arq", "img": "", "label": d.name})
        disciplines.append(
            {
                "slug": d.slug,
                "label": visual["label"],
                "icon": visual["icon"],
                "img": visual["img"],
                "paths": [p for p in paths if d in p.disciplines.all()],
            }
        )
    if not disciplines:  # sin semillas todavía: se muestran las cuatro disciplinas base
        disciplines = [
            {"slug": s, "label": v["label"], "icon": v["icon"], "img": v["img"], "paths": []}
            for s, v in DISCIPLINE_VISUALS.items()
        ]

    modules = [
        {**m, "url": reverse(m["url_name"]) if m["url_name"] else None, "live": bool(m["url_name"])}
        for m in MODULES
    ]
    return {
        "disciplines": disciplines,
        "modules": modules,
        "values": VALUES,
        "stats": {
            "paths": len(paths),
            "resources": Resource.objects.count(),
            "vendors": len({p.vendor_id for p in paths}),
        },
        "suite": SUITE_AERO,
        "sponsor_text": SPONSOR_TEXT,
        "first_path": paths[0] if paths else None,
        "mission": dashboard.suggested_mission(person),
        "board": dashboard.guild_board(person),
        "counters": dashboard.counters(person),
    }
