"""Carga de disciplinas, vendors, productos, plataformas y habilidades desde seed/ (idempotente)."""

from .models import Discipline, Platform, Product, Skill, Vendor, World


class SeedError(Exception):
    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


def _dupes(values):
    seen, dupes = set(), set()
    for value in values:
        (dupes if value in seen else seen).add(value)
    return sorted(dupes)


def validate_catalog(vendors_data, platforms_data, skills_data):
    errors = []
    disciplines = vendors_data.get("disciplines", [])
    vendors = vendors_data.get("vendors", [])
    products = [p for v in vendors for p in v.get("products", [])]
    worlds = {w.value for w in World}

    for label, items in (
        ("disciplina", disciplines),
        ("vendor", vendors),
        ("producto", products),
        ("plataforma", platforms_data.get("platforms", [])),
        ("habilidad", skills_data.get("skills", [])),
    ):
        for slug in _dupes(i.get("slug") for i in items):
            errors.append(f"{label} duplicado: {slug}")

    discipline_slugs = {d["slug"] for d in disciplines}
    for d in disciplines:
        if d.get("default_world") not in worlds:
            errors.append(f"disciplina {d['slug']}: mundo inválido «{d.get('default_world')}»")
    for p in products:
        for slug in p.get("disciplines", []):
            if slug not in discipline_slugs:
                errors.append(f"producto {p['slug']}: disciplina desconocida «{slug}»")

    vendor_slugs = {v["slug"] for v in vendors}
    kinds = {k.value for k in Platform.Kind}
    for p in platforms_data.get("platforms", []):
        if p.get("kind") not in kinds:
            errors.append(f"plataforma {p['slug']}: tipo inválido «{p.get('kind')}»")
        if p.get("vendor") and p["vendor"] not in vendor_slugs:
            errors.append(f"plataforma {p['slug']}: vendor desconocido «{p['vendor']}»")

    attrs = {a.value for a in Skill.Attribute}
    for s in skills_data.get("skills", []):
        if s.get("attribute") and s["attribute"] not in attrs:
            errors.append(f"habilidad {s['slug']}: atributo inválido «{s['attribute']}»")
    return errors


def load_catalog(vendors_data, platforms_data, skills_data):
    errors = validate_catalog(vendors_data, platforms_data, skills_data)
    if errors:
        raise SeedError(errors)

    for d in vendors_data.get("disciplines", []):
        Discipline.objects.update_or_create(
            slug=d["slug"],
            defaults={
                "name": d["name"],
                "default_world": d["default_world"],
                "order": d.get("order", 0),
                "icon": d.get("icon", ""),
            },
        )

    for order, v in enumerate(vendors_data.get("vendors", [])):
        vendor, _ = Vendor.objects.update_or_create(
            slug=v["slug"],
            defaults={
                "name": v["name"],
                "url": v.get("url", ""),
                "logo": v.get("logo", ""),
                "order": v.get("order", order),
            },
        )
        for p_order, p in enumerate(v.get("products", [])):
            product, _ = Product.objects.update_or_create(
                slug=p["slug"],
                defaults={"vendor": vendor, "name": p["name"], "order": p.get("order", p_order)},
            )
            product.disciplines.set(Discipline.objects.filter(slug__in=p.get("disciplines", [])))

    for p in platforms_data.get("platforms", []):
        Platform.objects.update_or_create(
            slug=p["slug"],
            defaults={
                "name": p["name"],
                "kind": p["kind"],
                "vendor": Vendor.objects.filter(slug=p["vendor"]).first()
                if p.get("vendor")
                else None,
                "url": p.get("url", ""),
                "notes": p.get("notes", ""),
            },
        )

    for s in skills_data.get("skills", []):
        Skill.objects.update_or_create(
            slug=s["slug"],
            defaults={
                "name": s["name"],
                "category": s.get("category", ""),
                "attribute": s.get("attribute", ""),
            },
        )

    return {
        "disciplines": Discipline.objects.count(),
        "vendors": Vendor.objects.count(),
        "products": Product.objects.count(),
        "platforms": Platform.objects.count(),
        "skills": Skill.objects.count(),
    }
