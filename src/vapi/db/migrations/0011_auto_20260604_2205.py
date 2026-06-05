from tortoise import migrations
from tortoise.migrations import operations as ops
import functools
from json import dumps, loads
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0010_archive_batch_id')]

    initial = False

    operations = [
        ops.AddField(
            model_name='User',
            name='apple_profile',
            field=fields.JSONField(null=True, encoder=functools.partial(dumps, separators=(',', ':')), decoder=loads),
        ),
    ]
