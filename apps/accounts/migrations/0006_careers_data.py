from django.db import migrations

# Carreras vigentes. Las cinco primeras conservan su slug (solo cambió el nombre que se muestra), así que no hay
# nada que renombrar: esta migración deja consistentes los datos que ya existían.
VALID = {
    "architect", "engineer", "cartographer", "artificer", "pilot",
    "lev_lead", "bim_modeler", "drafter", "bim_coord", "inspector", "gis", "scanner", "hse",
}  # fmt: skip


def normalize(apps, schema_editor):
    Person = apps.get_model("accounts", "Person")
    for person in Person.objects.exclude(character_class="").only(
        "id", "character_class", "avatar_config"
    ):
        changed = []
        if person.character_class not in VALID:
            person.character_class = ""
            changed.append("character_class")
        cfg = person.avatar_config
        if isinstance(cfg, dict) and cfg:
            if cfg.get("class") != person.character_class and person.character_class:
                person.avatar_config = {**cfg, "class": person.character_class}
                changed.append("avatar_config")
            elif cfg.get("class") and cfg["class"] not in VALID:
                person.avatar_config = {k: v for k, v in cfg.items() if k != "class"}
                changed.append("avatar_config")
        if changed:
            person.save(update_fields=changed)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0005_careers")]
    operations = [migrations.RunPython(normalize, migrations.RunPython.noop)]
