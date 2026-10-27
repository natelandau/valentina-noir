from tortoise import fields, migrations
from tortoise.migrations import operations as ops

from vapi.db.sql_models.base import new_uuid


class Migration(migrations.Migration):
    dependencies = [("models", "0025_trait_power_nameless_unique")]

    initial = False

    operations = [
        ops.CreateModel(
            name="ReferenceDataSeed",
            fields=[
                ("id", fields.UUIDField(primary_key=True, default=new_uuid, unique=True, db_index=True)),
                ("date_created", fields.DatetimeField(auto_now=False, auto_now_add=True)),
                ("date_modified", fields.DatetimeField(auto_now=True, auto_now_add=False)),
                ("is_archived", fields.BooleanField(default=False)),
                ("archive_date", fields.DatetimeField(null=True, auto_now=False, auto_now_add=False)),
                ("archive_batch_id", fields.UUIDField(null=True, db_index=True)),
                ("fingerprint", fields.CharField(max_length=64)),
            ],
            options={"table": "reference_data_seed", "app": "models", "pk_attr": "id", "table_description": "Fingerprint of the build the reference data was last seeded from."},
            bases=["BaseModel"],
        ),
        # Attach the archive-stamp trigger (function from 0010), matching
        # vapi.lib.database._ARCHIVE_TRIGGER_ATTACH_SQL.
        ops.RunSQL(
            sql=(
                "DROP TRIGGER IF EXISTS trg_enforce_archive_stamps ON reference_data_seed; "
                "CREATE TRIGGER trg_enforce_archive_stamps "
                "BEFORE INSERT OR UPDATE ON reference_data_seed FOR EACH ROW "
                "EXECUTE FUNCTION enforce_archive_stamps();"
            ),
            reverse_sql="",
        ),
    ]
