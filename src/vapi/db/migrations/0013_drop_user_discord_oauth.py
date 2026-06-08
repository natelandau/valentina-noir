from tortoise import migrations
from tortoise.migrations import operations as ops

class Migration(migrations.Migration):
    dependencies = [('models', '0012_auto_20260607_2130')]

    initial = False

    operations = [
        ops.RemoveField(model_name='User', name='discord_oauth'),
    ]
