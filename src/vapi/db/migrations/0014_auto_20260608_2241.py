from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0013_drop_user_discord_oauth')]

    initial = False

    operations = [
        ops.AddField(
            model_name='User',
            name='avatar_asset_id',
            field=fields.UUIDField(null=True),
        ),
        ops.AddField(
            model_name='User',
            name='avatar_url',
            field=fields.TextField(null=True, unique=False),
        ),
    ]
