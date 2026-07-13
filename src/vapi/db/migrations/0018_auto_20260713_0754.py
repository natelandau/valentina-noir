from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0017_auto_20260711_2120')]

    initial = False

    operations = [
        ops.AddField(
            model_name='Character',
            name='date_of_birth',
            field=fields.DateField(null=True),
        ),
    ]
