from tortoise import migrations
from tortoise.migrations import operations as ops
from vapi.constants import CharacterType
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0005_auto_20260422_1945')]

    initial = False

    operations = [
        ops.AlterField(
            model_name='Character',
            name='type',
            field=fields.CharEnumField(description='PLAYER: PLAYER\nNPC: NPC\nSTORYTELLER: STORYTELLER', enum_type=CharacterType, max_length=11),
        ),
    ]
