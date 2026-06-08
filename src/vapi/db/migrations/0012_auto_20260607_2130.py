from tortoise import migrations
from tortoise.migrations import operations as ops
import functools
from json import dumps, loads
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0011_auto_20260604_2205')]

    initial = False

    operations = [
        ops.AddField(
            model_name='Developer',
            name='provider_audiences',
            field=fields.JSONField(null=True, encoder=functools.partial(dumps, separators=(',', ':')), decoder=loads),
        ),
    ]
