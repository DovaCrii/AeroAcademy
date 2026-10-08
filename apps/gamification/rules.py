"""Reglas de las insignias (docs/GAMIFICACION.md). Cada regla es una función pura de los datos de la persona."""

from datetime import date, timedelta

from apps.credentials.models import Credential

from .models import XPEvent

LEARNING_KINDS = {
    "milestone",
    "quiz",
    "credential",
    "note",
    "accepted_answer",
    "free_course_promoted",
}


class Facts:
    """Datos de una persona, consultados una sola vez y solo si alguna regla los pide."""

    def __init__(self, person, today=None):
        self.person = person
        self.today = today or date.today()
        self._credentials = None
        self._events = None

    @property
    def credentials(self):
        """Credenciales verificadas, con los vendors y productos que alcanzan."""
        if self._credentials is None:
            rows = (
                Credential.objects.filter(owner=self.person, status=Credential.Status.VERIFIED)
                .select_related("platform__vendor", "path__vendor", "resource__platform__vendor")
                .prefetch_related("resource__products__vendor")
            )
            self._credentials = [self._describe(c) for c in rows]
        return self._credentials

    @staticmethod
    def _describe(c):
        vendors, products = set(), set()
        if c.platform and c.platform.vendor_id:
            vendors.add(c.platform.vendor.slug)
        if c.path and c.path.vendor_id:
            vendors.add(c.path.vendor.slug)
        if c.resource_id:
            if c.resource.platform.vendor_id:
                vendors.add(c.resource.platform.vendor.slug)
            for product in c.resource.products.all():
                products.add(product.slug)
                vendors.add(product.vendor.slug)
        return {
            "kind": c.kind,
            "platform": c.platform.slug if c.platform else "",
            "vendors": vendors,
            "products": products,
            "expires_on": c.expires_on,
        }

    @property
    def events(self):
        if self._events is None:
            self._events = list(
                XPEvent.objects.filter(person=self.person).values("kind", "created_at")
            )
        return self._events

    def count(self, kind):
        return sum(1 for e in self.events if e["kind"] == kind)

    def active_weeks(self):
        weeks = set()
        for e in self.events:
            if e["kind"] in LEARNING_KINDS:
                iso = e["created_at"].date().isocalendar()
                weeks.add((iso[0], iso[1]))
        return weeks


def week_key(day):
    iso = day.isocalendar()
    return iso[0], iso[1]


def streak_length(weeks, today):
    """Semanas seguidas con aprendizaje, contadas hasta esta semana (o la pasada, si esta aún no tiene)."""
    here = week_key(today)
    cursor = today if here in weeks else today - timedelta(days=7)
    if week_key(cursor) not in weeks:
        return 0
    length = 0
    while week_key(cursor) in weeks:
        length += 1
        cursor -= timedelta(days=7)
    return length


def _matching(facts, rule):
    kinds = set(rule["kinds"]) if "kinds" in rule else None
    rows = []
    for c in facts.credentials:
        if kinds is not None and c["kind"] not in kinds:
            continue
        if rule.get("vendor") and rule["vendor"] not in c["vendors"]:
            continue
        if rule.get("platform") and rule["platform"] != c["platform"]:
            continue
        if rule.get("requires_valid") and c["expires_on"] and c["expires_on"] < facts.today:
            continue
        rows.append(c)
    return rows


def check(rule, facts, path_pct):
    """¿Se cumple la regla? `path_pct(slug)` da el avance de la persona en una ruta."""
    kind = rule.get("type")
    if kind == "count":
        return facts.count(rule["event"]) >= rule["min"]
    if kind == "path_complete":
        return path_pct(rule["path"]) >= 100
    if kind == "distinct_vendors":
        vendors = set()
        for c in facts.credentials:
            if c["kind"] in ("completion", "certification"):
                vendors |= c["vendors"]
        return len(vendors) >= rule["min"]
    if kind == "streak":
        return best_streak(facts.active_weeks()) >= rule["weeks"]
    if kind == "credential_kind":
        rows = _matching(facts, rule)
        wanted = rule.get("products_all")
        if wanted:
            have = set().union(*(c["products"] for c in rows)) if rows else set()
            return set(wanted) <= have
        return len(rows) >= rule["min"]
    return False  # `manual` y desconocidas: nunca se otorgan solas


def best_streak(weeks):
    """Racha más larga de la historia: una insignia de constancia no se pierde al cortarse la racha."""
    best = 0
    for year, week in weeks:
        if _prev_week(year, week) in weeks:
            continue
        length, cursor = 0, (year, week)
        while cursor in weeks:
            length += 1
            cursor = _next_week(*cursor)
        best = max(best, length)
    return best


def _prev_week(year, week):
    monday = date.fromisocalendar(year, week, 1) - timedelta(days=7)
    return week_key(monday)


def _next_week(year, week):
    monday = date.fromisocalendar(year, week, 1) + timedelta(days=7)
    return week_key(monday)
