from tortoise import fields, migrations
from tortoise.migrations import operations as ops

# Health keeps one damage count: every typed mark becomes one point of damage.
BACKFILL_HEALTH_DAMAGE_SQL = (
    "UPDATE character_health SET"
    " damage = LEAST(GREATEST(size, 0), bashing + lethal + superficial + aggravated)"
    " WHERE bashing + lethal + superficial + aggravated > 0;"
)

# V5 Willpower becomes a counter: each marked damage box becomes one spent point.
BACKFILL_V5_WILLPOWER_SPENT_SQL = (
    "UPDATE character_trait ct SET"
    " tracker_spent = LEAST(GREATEST(ct.value, 0), ct.tracker_superficial + ct.tracker_aggravated)"
    ' FROM trait t, "character" c'
    " WHERE t.id = ct.trait_id AND c.id = ct.character_id"
    " AND t.name = 'Willpower' AND t.custom_for_character_id IS NULL"
    " AND c.game_version = 'V5';"
)

# Only V5 vampires track stains. Stains do not map to spent Humanity, so others start clean.
CLEAR_NON_VAMPIRE_STAINS_SQL = (
    "UPDATE character_trait ct SET tracker_stains = 0"
    ' FROM trait t, "character" c'
    " WHERE t.id = ct.trait_id AND c.id = ct.character_id"
    " AND t.name = 'Humanity' AND t.custom_for_character_id IS NULL"
    " AND NOT (c.game_version = 'V5' AND c.character_class = 'VAMPIRE')"
    " AND ct.tracker_stains <> 0;"
)


class Migration(migrations.Migration):
    dependencies = [("models", "0027_backfill_company_settings")]

    initial = False

    operations = [
        ops.AddField(
            model_name="CharacterHealth",
            name="damage",
            field=fields.IntField(default=0, db_default=0),
        ),
        ops.RunSQL(sql=BACKFILL_HEALTH_DAMAGE_SQL, reverse_sql=ops.RunSQL.noop),
        ops.RunSQL(sql=BACKFILL_V5_WILLPOWER_SPENT_SQL, reverse_sql=ops.RunSQL.noop),
        ops.RunSQL(sql=CLEAR_NON_VAMPIRE_STAINS_SQL, reverse_sql=ops.RunSQL.noop),
        ops.RemoveField(model_name="CharacterHealth", name="aggravated"),
        ops.RemoveField(model_name="CharacterHealth", name="bashing"),
        ops.RemoveField(model_name="CharacterHealth", name="lethal"),
        ops.RemoveField(model_name="CharacterHealth", name="superficial"),
        ops.RemoveField(model_name="CharacterTrait", name="tracker_aggravated"),
        ops.RemoveField(model_name="CharacterTrait", name="tracker_superficial"),
    ]
