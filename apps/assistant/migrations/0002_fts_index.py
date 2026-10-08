from django.db import migrations

# Índice de búsqueda de Teo (SQLite FTS5). Se reconstruye desde la base: no es fuente de verdad.
CREATE = """
CREATE VIRTUAL TABLE assistant_fts USING fts5(
    kind UNINDEXED, ref UNINDEXED, title, body, url UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 2'
)
"""


class Migration(migrations.Migration):
    dependencies = [("assistant", "0001_initial")]

    operations = [migrations.RunSQL(CREATE, "DROP TABLE IF EXISTS assistant_fts")]
