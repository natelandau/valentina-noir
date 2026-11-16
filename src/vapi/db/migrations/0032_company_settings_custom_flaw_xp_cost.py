from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0031_company_settings_specialty_rules')]

    initial = False

    operations = [
        ops.AddField(
            model_name='CompanySettings',
            name='custom_flaw_xp_cost',
            field=fields.IntField(default=2, db_default=2),
        ),
    ]
