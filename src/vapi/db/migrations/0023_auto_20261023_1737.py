from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.fields.base import OnDelete
from vapi.constants import AuditEntityType, TraitModifyCurrency
from vapi.db.sql_models.base import new_uuid
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0022_auto_20260715_0934')]

    initial = False

    operations = [
        ops.CreateModel(
            name='CharacterTraitSpecialty',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=new_uuid, unique=True, db_index=True)),
                ('date_created', fields.DatetimeField(auto_now=False, auto_now_add=True)),
                ('date_modified', fields.DatetimeField(auto_now=True, auto_now_add=False)),
                ('is_archived', fields.BooleanField(default=False)),
                ('archive_date', fields.DatetimeField(null=True, auto_now=False, auto_now_add=False)),
                ('archive_batch_id', fields.UUIDField(null=True, db_index=True)),
                ('character_trait', fields.ForeignKeyField('models.CharacterTrait', source_field='character_trait_id', db_index=True, db_constraint=True, to_field='id', related_name='specialties', on_delete=OnDelete.CASCADE)),
                ('name', fields.CharField(max_length=50)),
                ('cost_paid', fields.IntField(default=0)),
                ('currency_paid', fields.CharEnumField(default=TraitModifyCurrency.NO_COST, description='NO_COST: NO_COST\nXP: XP\nSTARTING_POINTS: STARTING_POINTS', enum_type=TraitModifyCurrency, max_length=15)),
            ],
            options={'table': 'character_trait_specialty', 'app': 'models', 'pk_attr': 'id', 'table_description': "A free-text specialty attached to a character's ability trait."},
            bases=['BaseModel'],
        ),
        ops.AlterField(
            model_name='AuditLog',
            name='entity_type',
            field=fields.CharEnumField(null=True, description='ASSET: ASSET\nBOOK: BOOK\nCAMPAIGN: CAMPAIGN\nCHAPTER: CHAPTER\nCHARACTER: CHARACTER\nCHARACTER_INVENTORY: CHARACTER_INVENTORY\nCHARACTER_TRAIT: CHARACTER_TRAIT\nCHARACTER_TRAIT_SPECIALTY: CHARACTER_TRAIT_SPECIALTY\nCHARGEN_SESSION: CHARGEN_SESSION\nCOMPANY: COMPANY\nDEVELOPER: DEVELOPER\nDICTIONARY_TERM: DICTIONARY_TERM\nEXPERIENCE: EXPERIENCE\nNOTE: NOTE\nQUICKROLL: QUICKROLL\nUSER: USER', enum_type=AuditEntityType, max_length=25),
        ),
        ops.AddField(
            model_name='CompanySettings',
            name='specialty_xp_cost_enabled',
            field=fields.BooleanField(default=False, db_default=False),
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
    ]
