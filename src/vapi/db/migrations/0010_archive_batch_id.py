from tortoise import fields, migrations
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    dependencies = [("models", "0009_prefix_join_tables")]

    initial = False

    operations = [
        ops.AddField(
            model_name="AuditLog",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="Campaign",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="CampaignBook",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="CampaignChapter",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="CampaignExperience",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="CharSheetSection",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="Character",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="CharacterConcept",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="CharacterInventory",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="CharacterTrait",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="ChargenSession",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="Company",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="CompanySettings",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="Developer",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="DeveloperCompanyPermission",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="DiceRoll",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="DiceRollResult",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="DictionaryTerm",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="HunterAttributes",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="MageAttributes",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="Note",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="QuickRoll",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="S3Asset",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="Specialty",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="Trait",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="TraitCategory",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="TraitSubcategory",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="User",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="VampireAttributes",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="VampireClan",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="WerewolfAttributes",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="WerewolfAuspice",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        ops.AddField(
            model_name="WerewolfTribe",
            name="archive_batch_id",
            field=fields.UUIDField(null=True, db_index=True),
        ),
        # --- archive-stamp enforcement ---
        ops.RunSQL(
            sql=(
                "DO $$ DECLARE tbl text; BEGIN "
                "FOR tbl IN SELECT table_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND column_name = 'archive_batch_id' "
                "LOOP EXECUTE format("
                "'UPDATE %I SET archive_date = date_modified "
                "WHERE is_archived AND archive_date IS NULL', tbl); "
                "END LOOP; END $$;"
            ),
            reverse_sql="",
        ),
        ops.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS pgcrypto;",
            reverse_sql="",
        ),
        # Kept in sync with the canonical constant
        # vapi.lib.database._ARCHIVE_TRIGGER_FUNCTION_SQL, which installs the
        # same function on fresh schemas that bypass migrations.
        ops.RunSQL(
            sql=(
                "CREATE OR REPLACE FUNCTION enforce_archive_stamps() "
                "RETURNS trigger AS $$ BEGIN "
                "IF NEW.is_archived THEN "
                "IF NEW.archive_date IS NULL THEN NEW.archive_date := now(); END IF; "
                "IF NEW.archive_batch_id IS NULL THEN "
                "NEW.archive_batch_id := gen_random_uuid(); END IF; "
                "ELSE NEW.archive_date := NULL; NEW.archive_batch_id := NULL; "
                "END IF; RETURN NEW; END; $$ LANGUAGE plpgsql;"
            ),
            reverse_sql="DROP FUNCTION IF EXISTS enforce_archive_stamps();",
        ),
        # Kept in sync with the canonical constant
        # vapi.lib.database._ARCHIVE_TRIGGER_ATTACH_SQL, which attaches the same
        # trigger on fresh schemas that bypass migrations.
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
            reverse_sql=(
                "DO $$ DECLARE tbl text; BEGIN "
                "FOR tbl IN SELECT table_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND column_name = 'archive_batch_id' "
                "LOOP EXECUTE format("
                "'DROP TRIGGER IF EXISTS trg_enforce_archive_stamps ON %I', tbl); "
                "END LOOP; END $$;"
            ),
        ),
    ]
