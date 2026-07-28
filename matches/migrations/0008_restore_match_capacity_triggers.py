from django.db import migrations


INSERT_TRIGGER = """
CREATE TRIGGER matchplayer_max_two_insert
BEFORE INSERT ON matches_matchplayer
WHEN (
    SELECT COUNT(*)
    FROM matches_matchplayer
    WHERE match_id = NEW.match_id
) >= 2
BEGIN
    SELECT RAISE(ABORT, 'match already has two players');
END;
"""

UPDATE_TRIGGER = """
CREATE TRIGGER matchplayer_max_two_update
BEFORE UPDATE OF match_id ON matches_matchplayer
WHEN NEW.match_id != OLD.match_id AND (
    SELECT COUNT(*)
    FROM matches_matchplayer
    WHERE match_id = NEW.match_id
) >= 2
BEGIN
    SELECT RAISE(ABORT, 'match already has two players');
END;
"""


def create_capacity_triggers(apps, schema_editor):
    if schema_editor.connection.vendor != "sqlite":
        return
    schema_editor.execute("DROP TRIGGER IF EXISTS matchplayer_max_two_insert")
    schema_editor.execute("DROP TRIGGER IF EXISTS matchplayer_max_two_update")
    schema_editor.execute(INSERT_TRIGGER)
    schema_editor.execute(UPDATE_TRIGGER)


def drop_capacity_triggers(apps, schema_editor):
    if schema_editor.connection.vendor != "sqlite":
        return
    schema_editor.execute("DROP TRIGGER IF EXISTS matchplayer_max_two_insert")
    schema_editor.execute("DROP TRIGGER IF EXISTS matchplayer_max_two_update")


class Migration(migrations.Migration):
    dependencies = [
        ("matches", "0007_energy_and_skills"),
    ]

    operations = [
        migrations.RunPython(
            create_capacity_triggers,
            reverse_code=drop_capacity_triggers,
        ),
    ]
