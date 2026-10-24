from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.fields.base import OnDelete
from vapi.constants import AuditEntityType, TrackerType
from vapi.db.sql_models.base import new_uuid
from tortoise import fields


def _attribute_join(name: str) -> str:
    """Return a LEFT JOIN exposing `<name>.value`: the character's global `name` trait.

    Only rows in the character's archive state and batch count, so an archived character
    reads the rows archived with it. Duplicates resolve to the most recently modified row.
    """
    alias = name.lower()
    return (
        "LEFT JOIN LATERAL ("
        " SELECT ct.value FROM character_trait ct"
        " JOIN trait t ON t.id = ct.trait_id"
        " WHERE ct.character_id = c.id"
        " AND ct.is_archived = c.is_archived"
        " AND ct.archive_batch_id IS NOT DISTINCT FROM c.archive_batch_id"
        f" AND t.name = '{name}'"
        " AND t.custom_for_character_id IS NULL"
        " ORDER BY ct.date_modified DESC, ct.id DESC"
        " LIMIT 1"
        f") {alias} ON true"
    )


# Archive stamps are copied from the character so a batch restore brings the rows back with it.
BACKFILL_HEALTH_SQL = (
    "INSERT INTO character_health ("
    " id, date_created, date_modified, is_archived, archive_date, archive_batch_id,"
    " character_id, size, extra_levels, bashing, lethal, superficial, aggravated"
    ") "
    "SELECT"
    " gen_random_uuid(), now(), now(), c.is_archived, c.archive_date, c.archive_batch_id,"
    " c.id,"
    " CASE WHEN c.game_version = 'V5' THEN COALESCE(stamina.value, 0) + 3 ELSE 7 END,"
    " 0, 0, 0, 0, 0 "
    'FROM "character" c '
    f"{_attribute_join('Stamina')} "
    "WHERE NOT EXISTS (SELECT 1 FROM character_health h WHERE h.character_id = c.id) "
    "ON CONFLICT (character_id) DO NOTHING;"
)

# One statement: the `corrected` CTE always runs to completion even though the INSERT does not
# read it. Lowering a value trims superficial marks before aggravated ones, like clamp_marks.
# With no global Willpower trait (a database migrated before seeding) both parts match nothing.
BACKFILL_V5_WILLPOWER_SQL = (
    "WITH source AS ("
    " SELECT c.id AS character_id, c.is_archived, c.archive_date, c.archive_batch_id,"
    " COALESCE(composure.value, 0) + COALESCE(resolve.value, 0) AS willpower"
    ' FROM "character" c'
    f" {_attribute_join('Composure')}"
    f" {_attribute_join('Resolve')}"
    " WHERE c.game_version = 'V5'"
    "), "
    "willpower_trait AS ("
    " SELECT id FROM trait"
    " WHERE name = 'Willpower' AND custom_for_character_id IS NULL AND is_archived = false"
    " ORDER BY date_created, id LIMIT 1"
    "), "
    "targets AS ("
    " SELECT ct.id, s.willpower,"
    " GREATEST(ct.tracker_superficial + ct.tracker_aggravated - GREATEST(s.willpower, 0), 0)"
    " AS excess"
    " FROM character_trait ct"
    " JOIN trait t ON t.id = ct.trait_id"
    " JOIN source s ON s.character_id = ct.character_id AND s.is_archived = ct.is_archived"
    " AND ct.archive_batch_id IS NOT DISTINCT FROM s.archive_batch_id"
    " WHERE t.name = 'Willpower' AND t.custom_for_character_id IS NULL"
    " AND ct.value <> s.willpower"
    "), "
    "corrected AS ("
    " UPDATE character_trait ct SET"
    " value = targets.willpower,"
    " tracker_superficial = GREATEST(ct.tracker_superficial - targets.excess, 0),"
    " tracker_aggravated = GREATEST("
    "ct.tracker_aggravated - GREATEST(targets.excess - ct.tracker_superficial, 0), 0),"
    " date_modified = now()"
    " FROM targets WHERE ct.id = targets.id"
    " RETURNING ct.id"
    ") "
    "INSERT INTO character_trait ("
    " id, date_created, date_modified, is_archived, archive_date, archive_batch_id,"
    " character_id, trait_id, value,"
    " tracker_spent, tracker_superficial, tracker_aggravated, tracker_stains"
    ") "
    "SELECT"
    " gen_random_uuid(), now(), now(), s.is_archived, s.archive_date, s.archive_batch_id,"
    " s.character_id, w.id, s.willpower, 0, 0, 0, 0 "
    "FROM source s CROSS JOIN willpower_trait w "
    "WHERE NOT EXISTS ("
    " SELECT 1 FROM character_trait ct JOIN trait t ON t.id = ct.trait_id"
    " WHERE ct.character_id = s.character_id AND ct.is_archived = s.is_archived"
    " AND ct.archive_batch_id IS NOT DISTINCT FROM s.archive_batch_id"
    " AND t.name = 'Willpower' AND t.custom_for_character_id IS NULL"
    ");"
)


class Migration(migrations.Migration):
    dependencies = [('models', '0023_auto_20261023_1737')]

    initial = False

    operations = [
        ops.CreateModel(
            name='CharacterHealth',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=new_uuid, unique=True, db_index=True)),
                ('date_created', fields.DatetimeField(auto_now=False, auto_now_add=True)),
                ('date_modified', fields.DatetimeField(auto_now=True, auto_now_add=False)),
                ('is_archived', fields.BooleanField(default=False)),
                ('archive_date', fields.DatetimeField(null=True, auto_now=False, auto_now_add=False)),
                ('archive_batch_id', fields.UUIDField(null=True, db_index=True)),
                ('character', fields.OneToOneField('models.Character', source_field='character_id', db_constraint=True, to_field='id', related_name='health', on_delete=OnDelete.CASCADE)),
                ('size', fields.IntField(default=0)),
                ('extra_levels', fields.IntField(default=0)),
                ('bashing', fields.IntField(default=0)),
                ('lethal', fields.IntField(default=0)),
                ('superficial', fields.IntField(default=0)),
                ('aggravated', fields.IntField(default=0)),
            ],
            options={'table': 'character_health', 'app': 'models', 'pk_attr': 'id', 'table_description': 'Health track of a character, one-to-one with Character.'},
            bases=['BaseModel'],
        ),
        ops.AlterField(
            model_name='AuditLog',
            name='entity_type',
            field=fields.CharEnumField(null=True, description='ASSET: ASSET\nBOOK: BOOK\nCAMPAIGN: CAMPAIGN\nCHAPTER: CHAPTER\nCHARACTER: CHARACTER\nCHARACTER_HEALTH: CHARACTER_HEALTH\nCHARACTER_INVENTORY: CHARACTER_INVENTORY\nCHARACTER_TRAIT: CHARACTER_TRAIT\nCHARACTER_TRAIT_SPECIALTY: CHARACTER_TRAIT_SPECIALTY\nCHARGEN_SESSION: CHARGEN_SESSION\nCOMPANY: COMPANY\nDEVELOPER: DEVELOPER\nDICTIONARY_TERM: DICTIONARY_TERM\nEXPERIENCE: EXPERIENCE\nNOTE: NOTE\nQUICKROLL: QUICKROLL\nUSER: USER', enum_type=AuditEntityType, max_length=25),
        ),
        ops.AddField(
            model_name='CharacterTrait',
            name='tracker_aggravated',
            field=fields.IntField(default=0, db_default=0),
        ),
        ops.AddField(
            model_name='CharacterTrait',
            name='tracker_spent',
            field=fields.IntField(default=0, db_default=0),
        ),
        ops.AddField(
            model_name='CharacterTrait',
            name='tracker_stains',
            field=fields.IntField(default=0, db_default=0),
        ),
        ops.AddField(
            model_name='CharacterTrait',
            name='tracker_superficial',
            field=fields.IntField(default=0, db_default=0),
        ),
        ops.AddField(
            model_name='Trait',
            name='tracker_type_v4',
            field=fields.CharEnumField(null=True, description='COUNTER: COUNTER\nDAMAGE: DAMAGE\nSTAINS: STAINS', enum_type=TrackerType, max_length=7),
        ),
        ops.AddField(
            model_name='Trait',
            name='tracker_type_v5',
            field=fields.CharEnumField(null=True, description='COUNTER: COUNTER\nDAMAGE: DAMAGE\nSTAINS: STAINS', enum_type=TrackerType, max_length=7),
        ),
        # Attach the archive-stamp trigger (function from 0010) to tables created since,
        # matching vapi.lib.database._ARCHIVE_TRIGGER_ATTACH_SQL.
        ops.RunSQL(
            sql=(
                "DO $$ DECLARE tbl text; BEGIN "
                "FOR tbl IN SELECT table_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND column_name = 'archive_batch_id' "
                "LOOP "
                "EXECUTE format("
                "'DROP TRIGGER IF EXISTS trg_enforce_archive_stamps ON %I', tbl); "
                "EXECUTE format("
                "'CREATE TRIGGER trg_enforce_archive_stamps "
                "BEFORE INSERT OR UPDATE ON %I FOR EACH ROW "
                "EXECUTE FUNCTION enforce_archive_stamps()', tbl); "
                "END LOOP; END $$;"
            ),
            reverse_sql="",
        ),
        ops.RunSQL(sql=BACKFILL_HEALTH_SQL, reverse_sql=ops.RunSQL.noop),
        ops.RunSQL(sql=BACKFILL_V5_WILLPOWER_SQL, reverse_sql=ops.RunSQL.noop),
    ]
