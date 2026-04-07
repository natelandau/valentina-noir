from tortoise import fields, migrations
from tortoise.migrations import operations as ops

from vapi.constants import PermissionsRecoupXP


class StateOnlyAddField(ops.AddField):
    """AddField variant that updates ORM state only, leaving the schema untouched.

    Used when the column has already been created via raw SQL (e.g. to attach a
    SQL-level DEFAULT for backfilling existing rows) but the migration still
    needs to register the field in Tortoise's model state for future migrations.
    """

    async def database_forward(self, app_label, old_state, new_state, state_editor=None):
        return None

    async def database_backward(self, app_label, old_state, new_state, state_editor=None):
        return None


class Migration(migrations.Migration):
    dependencies = [("models", "0001_initial")]

    initial = False

    operations = [
        # Tortoise's AddField does not propagate Python-level defaults to pre-existing
        # rows, which violates NOT NULL on tables that already have data. Add the column
        # via raw SQL with a DEFAULT clause so existing company_settings rows backfill to
        # DENIED, then register the field in ORM state via StateOnlyAddField.
        ops.RunSQL(
            "ALTER TABLE company_settings ADD COLUMN permission_recoup_xp VARCHAR(14) NOT NULL DEFAULT 'DENIED';",
            reverse_sql="ALTER TABLE company_settings DROP COLUMN permission_recoup_xp;",
        ),
        StateOnlyAddField(
            model_name="CompanySettings",
            name="permission_recoup_xp",
            field=fields.CharEnumField(default=PermissionsRecoupXP.DENIED, description="UNRESTRICTED: UNRESTRICTED\nDENIED: DENIED\nWITHIN_SESSION: WITHIN_SESSION", enum_type=PermissionsRecoupXP, max_length=14),
        ),
    ]
