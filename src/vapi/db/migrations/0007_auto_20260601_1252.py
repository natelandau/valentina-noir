from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.fields.base import OnDelete
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0006_auto_20260601_1004')]

    initial = False

    operations = [
        ops.AlterField(
            model_name='Character',
            name='user_creator',
            field=fields.ForeignKeyField('models.User', source_field='user_creator_id', null=True, db_constraint=True, to_field='id', related_name='created_characters', on_delete=OnDelete.SET_NULL),
        ),
        ops.AlterField(
            model_name='Character',
            name='user_player',
            field=fields.ForeignKeyField('models.User', source_field='user_player_id', null=True, db_constraint=True, to_field='id', related_name='played_characters', on_delete=OnDelete.CASCADE),
        ),
        ops.RunSQL(
            "UPDATE character SET user_player_id = NULL WHERE type IN ('NPC', 'STORYTELLER')",
            reverse_sql="-- irreversible: original NPC/STORYTELLER player assignments are not recoverable",
        ),
    ]
