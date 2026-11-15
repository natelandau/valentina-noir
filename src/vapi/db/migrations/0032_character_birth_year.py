from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0031_company_settings_specialty_rules')]

    initial = False

    operations = [
        ops.AddField(
            model_name='Character',
            name='birth_year',
            field=fields.IntField(null=True),
        ),
    ]
