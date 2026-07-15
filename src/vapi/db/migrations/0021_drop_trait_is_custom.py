from tortoise import migrations
from tortoise.migrations import operations as ops


class StateOnlyRemoveField(ops.RemoveField):
    """RemoveField variant that updates ORM state only, leaving the schema untouched.

    Used when the column is dropped by hand-written SQL, but the migration still needs to
    retire the field from Tortoise's model state.
    """

    async def database_forward(self, app_label, old_state, new_state, state_editor=None):
        return None

    async def database_backward(self, app_label, old_state, new_state, state_editor=None):
        return None


class Migration(migrations.Migration):
    dependencies = [("models", "0020_auto_20260714_2130")]

    initial = False

    # Drop trait.is_custom: it duplicated `custom_for_character_id IS NOT NULL` with nothing
    # keeping the two in agreement. Ownership is the load-bearing definition (it carries the
    # cascade delete), so it becomes the only way to tell a custom trait from a core one.
    operations = [
        # Hand-rolled rather than ops.RemoveField so the reverse works at all. A generated
        # reverse re-adds is_custom as NOT NULL with no database default (Tortoise's
        # BooleanField default is applied in Python, not by the schema), which fails outright
        # on any non-empty trait table. The reverse below adds the column with a temporary
        # default so the NOT NULL holds, drops that default to match the original schema
        # (peer BooleanFields carry no database default), then restores is_custom from
        # ownership so a rollback cannot silently mark every custom trait global.
        ops.RunSQL(
            "ALTER TABLE trait DROP COLUMN is_custom",
            reverse_sql=(
                "ALTER TABLE trait ADD COLUMN is_custom BOOL NOT NULL DEFAULT False; "
                "ALTER TABLE trait ALTER COLUMN is_custom DROP DEFAULT; "
                "UPDATE trait SET is_custom = true WHERE custom_for_character_id IS NOT NULL;"
            ),
        ),
        StateOnlyRemoveField(model_name="Trait", name="is_custom"),
    ]
