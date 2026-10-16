from datetime import timedelta
from pathlib import Path

from django.db.models import Count, F, Q
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Discipline, Platform, Product, Resource
from apps.catalog.software import DISCIPLINE_SLUG_BY_KEY, PRODUCT_TILE, discipline_key, route_icon
from apps.community import forum
from apps.credentials.models import WARNING_DAYS, Credential
from apps.gamification import game
from apps.gamification.models import Badge
from apps.notifications import services as notifications
from apps.paths import services as path_services
from apps.paths.models import LearningPath

from . import dashboard
from .modules import DISCIPLINE_VISUALS, MODULES, VALUES
from .suite import SPONSOR_TEXT, SUITE_AERO


def _visible_paths(person):
    qs = LearningPath.objects.select_related("vendor").prefetch_related("disciplines", "products")
    return qs if person.is_lead else qs.filter(is_published=True)


_SOFTWARE_DIR = Path(__file__).resolve().parent / "static" / "core" / "img" / "software"
FEATURED_PRODUCTS = 2
FEATURED_RESOURCES = 6
MY_PATHS_LIMIT = 4


def _software_icons():
    return {p.stem for p in _SOFTWARE_DIR.glob("*.svg")} if _SOFTWARE_DIR.is_dir() else set()


def _path_icon(path, icons):
    """Icono propio de la ruta (img/software/ruta-<slug>.svg); si no, la ficha del primer producto que tenga una."""
    own = route_icon(path.slug)
    if own in icons:
        return own
    for product in path.products.all():
        for stem in sorted(icons):
            if product.slug == stem or product.slug.startswith(stem + "-"):
                return stem
    for (
        product
    ) in path.products.all():  # productos con otro nombre que su ficha (power-bi → powerbi)
        tile = PRODUCT_TILE.get(product.slug)
        if tile in icons:
            return tile
    return ""


def _overview(person, paths, pcts):
    """Mi avance: rutas por empezar / en progreso / completadas y credenciales por vencer (consultas acotadas)."""
    icons = _software_icons()
    rows = [
        {"path": p, "pct": pcts[p.pk], "icon": _path_icon(p, icons)} for p in paths[:MY_PATHS_LIMIT]
    ]
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


def main_discipline_slug(path):
    """Disciplina principal de una ruta: la de `software.discipline_key` si la ruta la tiene; si no, su primera."""
    own = sorted(path.disciplines.all(), key=lambda d: d.order)
    wanted = DISCIPLINE_SLUG_BY_KEY.get(discipline_key(path), "")
    if any(d.slug == wanted for d in own):
        return wanted
    return own[0].slug if own else ""


def _start_block(person, paths):
    """Primer bloque bajo el héroe: «Continuar donde quedaste» (la ruta con avance tocada más recientemente) o,
    sin avance, «Empieza aquí» (la ruta 101 de su disciplina). Dos consultas fijas más las disciplinas de la persona."""
    from apps.progress.models import MilestoneCheck, QuizAnswer

    doing = [p for p in paths if 0 < p.pct < 100]
    if doing:
        ids = [p.pk for p in doing]
        last = {}
        for pid, when in MilestoneCheck.objects.filter(
            person=person, milestone__path__in=ids
        ).values_list("milestone__path_id", "checked_at"):
            last[pid] = max(last.get(pid, when), when)
        for pid, when in QuizAnswer.objects.filter(
            person=person, question__path__in=ids
        ).values_list("question__path_id", "answered_at"):
            last[pid] = max(last.get(pid, when), when)
        best = max(
            doing,
            key=lambda p: (p.pk in last, last[p.pk].timestamp() if p.pk in last else 0, p.pct),
        )
        return {"kind": "continue", "path": best}
    mine = {d.pk for d in person.disciplines.all()}
    starters = [p for p in paths if p.slug.endswith("-101") and p.pct == 0]
    starters.sort(key=lambda p: not ({d.pk for d in p.disciplines.all()} & mine))
    if starters:
        return {"kind": "start", "path": starters[0]}
    todo = [p for p in paths if p.pct == 0]
    return {"kind": "start", "path": todo[0]} if todo else None


def home_context(person):
    """Todo lo que necesita la ventana de bienvenida."""
    paths = list(_visible_paths(person))
    pcts = game.path_percents(person, paths)  # consultas fijas, no una tanda por ruta
    path_services.attach_ctas(person, paths, pcts)  # p.cta / p.pct para la tarjeta única
    main = {
        p.pk: main_discipline_slug(p) for p in paths
    }  # cada ruta se muestra una vez, en su disciplina principal
    disciplines = []
    for d in Discipline.objects.all():
        visual = DISCIPLINE_VISUALS.get(d.slug, {"icon": "i-arq", "img": "", "label": d.name})
        disciplines.append(
            {
                "slug": d.slug,
                "label": visual["label"],
                "icon": visual["icon"],
                "img": visual["img"],
                "paths": [p for p in paths if main[p.pk] == d.slug],
                "also": [p for p in paths if main[p.pk] != d.slug and d in p.disciplines.all()],
            }
        )
    if not disciplines:  # sin semillas todavía: se muestran las cuatro disciplinas base
        disciplines = [
            {"slug": s, "label": v["label"], "icon": v["icon"], "img": v["img"], "paths": []}
            for s, v in DISCIPLINE_VISUALS.items()
        ]
    disciplines.sort(key=lambda d: d["slug"] != "transversal")  # la base de todo va primero

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
        "start_block": _start_block(person, paths),
        "announcements": notifications.active_announcements(),
        "mission": dashboard.suggested_mission(person, pcts),
        "board": dashboard.guild_board(person),
        "counters": dashboard.counters(person),
        "first_steps": dashboard.first_steps(person),
        "overview": _overview(person, paths, pcts),
        "badges": _badges(person),
        "featured": _featured(),
        "team_talk": forum.team_conversations(show_hidden=person.is_lead),
    }
