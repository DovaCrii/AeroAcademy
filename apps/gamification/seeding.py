"""Carga de insignias y títulos desde seed/ (idempotente; lo que sale del archivo se retira, no se borra)."""

from pathlib import Path

from django.conf import settings

from apps.catalog.seeding import SeedError

from .models import Badge, Title

RARITIES = {"common", "rare", "epic", "legendary"}
RULE_FIELDS = {
    "count": {"event", "min"},
    "path_complete": {"path"},
    "distinct_vendors": {"min"},
    "streak": {"weeks"},
    "credential_kind": {"kinds", "min", "vendor", "platform", "products_all", "requires_valid"},
    "level_complete": {"path", "level"},
    "quiz_correct": {"path", "levels"},
    "paths_complete": {"paths"},
    "general_complete": {"min"},
    "manual": set(),
}
REQUIRED = {
    "count": {"event", "min"},
    "path_complete": {"path"},
    "distinct_vendors": {"min"},
    "streak": {"weeks"},
    "credential_kind": {"kinds", "min"},
    "level_complete": {"path", "level"},
    "quiz_correct": {"path", "levels"},
    "paths_complete": {"paths"},
    "general_complete": set(),
    "manual": set(),
}
SPRITE_DIR = Path(settings.BASE_DIR) / "apps" / "core" / "static" / "game" / "badges"


def validate_game(badges_data, titles_data, *, check_sprites=True):
    errors = []
    slugs = [b.get("slug") for b in badges_data.get("badges", [])]
    for slug in {s for s in slugs if slugs.count(s) > 1}:
        errors.append(f"insignias: slug repetido «{slug}»")
    for b in badges_data.get("badges", []):
        slug = b.get("slug", "?")
        for field in ("slug", "name", "description", "rarity", "rule"):
            if not b.get(field):
                errors.append(f"insignia {slug}: falta «{field}»")
        if b.get("rarity") and b["rarity"] not in RARITIES:
            errors.append(f"insignia {slug}: rareza desconocida «{b['rarity']}»")
        rule = b.get("rule") or {}
        kind = rule.get("type")
        if kind not in RULE_FIELDS:
            errors.append(f"insignia {slug}: tipo de regla desconocido «{kind}»")
            continue
        unknown = set(rule) - RULE_FIELDS[kind] - {"type"}
        if unknown:
            errors.append(f"insignia {slug}: campos de regla desconocidos {sorted(unknown)}")
        missing = REQUIRED[kind] - set(rule)
        if missing:
            errors.append(f"insignia {slug}: a la regla le faltan {sorted(missing)}")
        for field in ("levels", "paths"):
            if field in rule and not (
                isinstance(rule[field], list)
                and rule[field]
                and all(isinstance(x, str) for x in rule[field])
            ):
                errors.append(f"insignia {slug}: «{field}» debe ser una lista de textos")
        if check_sprites and b.get("sprite") and not (SPRITE_DIR / b["sprite"]).is_file():
            errors.append(f"insignia {slug}: no existe el sprite «{b['sprite']}»")
    title_slugs = [t.get("slug") for t in titles_data.get("titles", [])]
    for slug in {s for s in title_slugs if title_slugs.count(s) > 1}:
        errors.append(f"títulos: slug repetido «{slug}»")
    known = set(slugs)
    for t in titles_data.get("titles", []):
        slug = t.get("slug", "?")
        if not t.get("name"):
            errors.append(f"título {slug}: falta el nombre")
        if "min_level" not in t and "badge" not in t:
            errors.append(f"título {slug}: necesita `min_level` o `badge`")
        if t.get("badge") and t["badge"] not in known:
            errors.append(f"título {slug}: la insignia «{t['badge']}» no existe")
    return errors


def load_game(badges_data, titles_data, *, check_sprites=True):
    errors = validate_game(badges_data, titles_data, check_sprites=check_sprites)
    if errors:
        raise SeedError(errors)
    seen = set()
    for order, b in enumerate(badges_data.get("badges", [])):
        Badge.objects.update_or_create(
            slug=b["slug"],
            defaults={
                "name": b["name"],
                "description": b["description"],
                "rarity": b["rarity"],
                "sprite": b.get("sprite", ""),
                "rule": b["rule"],
                "order": order,
                "retired": False,
            },
        )
        seen.add(b["slug"])
    Badge.objects.exclude(slug__in=seen).update(retired=True)
    seen_titles = set()
    for order, t in enumerate(titles_data.get("titles", [])):
        Title.objects.update_or_create(
            slug=t["slug"],
            defaults={
                "name": t["name"],
                "min_level": t.get("min_level", 0),
                "character_class": t.get("character_class", ""),
                "badge": Badge.objects.filter(slug=t["badge"]).first() if t.get("badge") else None,
                "order": order,
                "retired": False,
            },
        )
        seen_titles.add(t["slug"])
    Title.objects.exclude(slug__in=seen_titles).update(retired=True)
    return {"badges": len(seen), "titles": len(seen_titles)}
