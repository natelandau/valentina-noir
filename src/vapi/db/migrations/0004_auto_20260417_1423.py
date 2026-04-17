from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0003_auto_20260412_1249')]

    initial = False

    operations = [
        ops.AddField(
            model_name='CompanySettings',
            name='character_autogen_starting_points',
            field=fields.IntField(default=0),
        ),
    ]
