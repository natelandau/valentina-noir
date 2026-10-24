from tortoise import migrations
from tortoise.migrations import operations as ops

# Keep one nameless descriptor per (trait, level) so the index can build: prefer an
# active row over an archived one, then the oldest (uuid7 ids sort by creation time).
DEDUPE_NAMELESS_SQL = (
    "DELETE FROM trait_power a USING trait_power b "
    "WHERE a.name IS NULL AND b.name IS NULL "
    "AND a.trait_id = b.trait_id AND a.level = b.level "
    "AND (a.is_archived, a.id) > (b.is_archived, b.id);"
)


class Migration(migrations.Migration):
    dependencies = [("models", "0024_auto_20261023_2254")]

    initial = False

    operations = [
        ops.RunSQL(sql=DEDUPE_NAMELESS_SQL, reverse_sql=ops.RunSQL.noop),
        # Kept in sync with vapi.lib.database._TRAIT_POWER_NAMELESS_UNIQUE_SQL, which
        # installs the same index on fresh schemas that bypass migrations.
        ops.RunSQL(
            sql=(
                "CREATE UNIQUE INDEX IF NOT EXISTS uidx_trait_power_nameless_level "
                "ON trait_power (trait_id, level) WHERE name IS NULL;"
            ),
            reverse_sql="DROP INDEX IF EXISTS uidx_trait_power_nameless_level;",
        ),
    ]
