from tortoise import fields, migrations
from tortoise.fields.base import OnDelete
from tortoise.migrations import operations as ops


class StateOnlyRemoveField(ops.RemoveField):
    """RemoveField variant that updates ORM state only, leaving the schema untouched.

    Used when a column is being redefined in place (e.g. gaining a FK constraint)
    rather than dropped, but the migration still needs to retire the old field from
    Tortoise's model state.
    """

    async def database_forward(self, app_label, old_state, new_state, state_editor=None):
        return None

    async def database_backward(self, app_label, old_state, new_state, state_editor=None):
        return None


class StateOnlyAddField(ops.AddField):
    """AddField variant that updates ORM state only, leaving the schema untouched.

    Used when the column already exists (here, the same physical column the old
    field used) but the migration still needs to register the new field in
    Tortoise's model state for future migrations.
    """

    async def database_forward(self, app_label, old_state, new_state, state_editor=None):
        return None

    async def database_backward(self, app_label, old_state, new_state, state_editor=None):
        return None


_FK = fields.ForeignKeyField("models.Character", source_field="custom_for_character_id", null=True, db_constraint=True, to_field="id", related_name="custom_traits", on_delete=OnDelete.CASCADE)
_FK_INDEXED = fields.ForeignKeyField("models.Character", source_field="custom_for_character_id", null=True, db_index=True, db_constraint=True, to_field="id", related_name="custom_traits", on_delete=OnDelete.CASCADE)


class Migration(migrations.Migration):
    dependencies = [("models", "0019_auto_20260714_0910")]

    initial = False

    # Promote trait.custom_for_character_id from a bare UUID column to a real FK, so a
    # custom trait is deleted with the character that owns it. The column itself is
    # unchanged: only the constraint and index are new, so the owner ids are never moved
    # and the state-only ops re-point Tortoise at the redefined field.
    operations = [
        # Without an FK, hard-deleting a character (chargen expiry, temporary-character
        # purge) left its custom traits behind. Those orphans would violate the new
        # constraint, and nothing can reach them: their character_trait rows went with
        # the character. The noop reverse keeps the migration rollbackable; the orphans
        # themselves are not worth restoring.
        ops.RunSQL(
            'DELETE FROM trait WHERE custom_for_character_id IS NOT NULL '
            'AND custom_for_character_id NOT IN (SELECT id FROM "character")',
            reverse_sql=ops.RunSQL.noop,
        ),
        ops.RunSQL(
            'ALTER TABLE trait ADD CONSTRAINT trait_custom_for_character_id_fkey '
            'FOREIGN KEY (custom_for_character_id) REFERENCES "character" (id) ON DELETE CASCADE',
            reverse_sql="ALTER TABLE trait DROP CONSTRAINT trait_custom_for_character_id_fkey",
        ),
        StateOnlyRemoveField(model_name="Trait", name="custom_for_character_id"),
        StateOnlyAddField(model_name="Trait", name="custom_for_character", field=_FK),
        # Index the owner column: Postgres does not index FK columns automatically, so
        # without this every character delete seq-scans trait to find cascade targets.
        # AlterField is what emits the CREATE INDEX; db_index on AddField is ignored.
        ops.AlterField(model_name="Trait", name="custom_for_character", field=_FK_INDEXED),
        ops.AlterModelOptions(
            name="TraitPower",
            options={"table": "trait_power", "app": "models", "unique_together": (("trait", "level", "name"),), "pk_attr": "id", "table_description": "A power or per-dot descriptor a trait grants at a specific dot level."},
        ),
    ]
