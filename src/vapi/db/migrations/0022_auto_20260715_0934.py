from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.fields.base import OnDelete
from tortoise import fields


class Migration(migrations.Migration):
    dependencies = [("models", "0021_drop_trait_is_custom")]

    initial = False

    operations = [
        ops.AlterField(
            model_name="CharacterInventory",
            name="character",
            field=fields.ForeignKeyField(
                "models.Character",
                source_field="character_id",
                db_index=True,
                db_constraint=True,
                to_field="id",
                related_name="inventory",
                on_delete=OnDelete.CASCADE,
            ),
        ),
        ops.AlterField(
            model_name="CharacterTrait",
            name="character",
            field=fields.ForeignKeyField(
                "models.Character",
                source_field="character_id",
                db_index=True,
                db_constraint=True,
                to_field="id",
                related_name="traits",
                on_delete=OnDelete.CASCADE,
            ),
        ),
        ops.AlterField(
            model_name="Specialty",
            name="character",
            field=fields.ForeignKeyField(
                "models.Character",
                source_field="character_id",
                db_index=True,
                db_constraint=True,
                to_field="id",
                related_name="specialties",
                on_delete=OnDelete.CASCADE,
            ),
        ),
    ]
