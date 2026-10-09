from datetime import timedelta
from pathlib import Path

from django.db.models import Count, F, Q
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Discipline, Platform, Product, Resource
from apps.credentials.models import WARNING_DAYS, Credential
from apps.gamification import game
from apps.gamification.models import Badge
from apps.notifications import services as notifications
from apps.paths.models import LearningPath

from . import dashboard
from .modules import DISCIPLINE_VISUALS, MODULES, VALUES
from .suite import SPONSOR_TEXT, SUITE_AERO


def _visible_paths(person):
    qs = LearningPath.objects.select_related("vendor").prefetch_related("disciplines")
    return qs if person.is_lead else qs.filter(is_published=True)


_SOFTWARE_DIR = Path(__file__).resolve().parent / "static" / "core" / "img" / "software"
FEATURED_PRODUCTS = 2
FEATURED_RESOURCES = 6
MY_PATHS_LIMIT = 4


def _software_icons():
    return {p.stem for p in _SOFTWARE_DIR.glob("*.svg")} if _SOFTWARE_DIR.is_dir() else set()


def _overview(person, paths, pcts):
    """Mi avance: rutas por empezar / en progreso / completadas y credenciales por vencer (consultas acotadas)."""
    rows = [{"path": p, "pct": pcts[p.pk]} for p in paths[:MY_PATHS_LIMIT]]
    today = timezone.localdate()
    expiring = list(
        Credential.objects.filter(
            owner=person,
            status=Credential.Status.VERIFIED,
            expires_on__isnull=False,
            expires_on__gte=today,
            expires_on__lte=today + timedelta(days=WARNING_DAYS),
        ).order_by("expires_on")[:5]
    )
    return {
        "todo": [r for r in rows if r["pct"] == 0],
        "doing": [r for r in rows if 0 < r["pct"] < 100],
        "done": [r for r in rows if r["pct"] >= 100],
        "expiring": expiring,
    }


def _badges(person):
    agg = Badge.objects.filter(retired=False).aggregate(
        total=Count("pk", distinct=True),
        earned=Count("holders", filter=Q(holders__person=person), distinct=True),
    )
    total, earned = agg["total"], agg["earned"]
    return {"earned": earned, "total": total, "left": max(total - earned, 0)}


def _featured():
    """Destacados: pocos productos (o, sin productos enlazados, plataformas) con sus primeros recursos.
    El catálogo completo vive en /catalogo/."""
    icons = _software_icons()
    groups = [
        {
            "key": p.pk,
            "name": p.name,
            "sub": p.vendor.name,
            "n": p.n,
            "icon": p.slug if p.slug in icons else "",
        }
        for p in Product.objects.select_related("vendor")
        .annotate(n=Count("resources"))
        .filter(n__gt=0)
        .order_by("-n", "vendor__order", "order")[:FEATURED_PRODUCTS]
    ]
    if groups:
        qs = Resource.objects.filter(products__in=[g["key"] for g in groups]).annotate(
            gid=F("products")
        )
    else:  # el catálogo aún no enlaza recursos con productos: se agrupa por plataforma
        groups = [
            {"key": p.pk, "name": p.name, "sub": p.get_kind_display(), "n": p.n, "icon": ""}
            for p in Platform.objects.annotate(n=Count("resources"))
            .filter(n__gt=0)
            .order_by("-n", "name")[:FEATURED_PRODUCTS]
        ]
        qs = Resource.objects.filter(platform__in=[g["key"] for g in groups]).annotate(
            gid=F("platform")
        )
    for g in groups:
        g["resources"] = []
    by_key = {g["key"]: g for g in groups}
    for r in qs.order_by("-is_official", "title"):
        bucket = by_key[r.gid]["resources"]
        if len(bucket) < FEATURED_RESOURCES:
            bucket.append(r)
    return groups


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

    pcts = {p.pk: game.path_percent(person, p) for p in paths}
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
        "announcements": notifications.active_announcements(),
        "mission": dashboard.suggested_mission(person, pcts),
        "board": dashboard.guild_board(person),
        "counters": dashboard.counters(person),
        "first_steps": dashboard.first_steps(person),
        "overview": _overview(person, paths, pcts),
        "badges": _badges(person),
        "featured": _featured(),
    }
