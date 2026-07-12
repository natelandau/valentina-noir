from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0016_custom_traits_rollable')]

    initial = False

    operations = [
        ops.AddField(
            model_name='Campaign',
            name='year',
            field=fields.CharField(null=True, max_length=50),
        ),
    ]
