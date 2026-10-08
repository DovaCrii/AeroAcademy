"""Carga de las categorías del foro desde seed/foro.json (idempotente)."""

from apps.catalog.seeding import SeedError

from .models import Category


def validate_forum(data):
    errors, seen = [], set()
    for c in data.get("categories", []):
        slug = c.get("slug", "?")
        if not c.get("slug") or not c.get("name"):
            errors.append(f"foro: la categoría «{slug}» necesita `slug` y `name`")
        if slug in seen:
            errors.append(f"foro: slug repetido «{slug}»")
        seen.add(slug)
    return errors


def load_forum(data):
    errors = validate_forum(data)
    if errors:
        raise SeedError(errors)
    seen = set()
    for order, c in enumerate(data.get("categories", [])):
        Category.objects.update_or_create(
            slug=c["slug"],
            defaults={
                "name": c["name"],
                "description": c.get("description", ""),
                "order": order,
                "retired": False,
            },
        )
        seen.add(c["slug"])
    Category.objects.exclude(slug__in=seen).update(retired=True)
    return {"categories": len(seen)}
