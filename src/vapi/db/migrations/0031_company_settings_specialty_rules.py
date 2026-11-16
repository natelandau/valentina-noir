from tortoise import migrations
from tortoise.migrations import operations as ops
from vapi.constants import SpecialtyRules
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0030_auto_20261109_0043')]

    initial = False

    operations = [
        ops.AddField(
            model_name='CompanySettings',
            name='specialty_rules',
            field=fields.CharEnumField(default=SpecialtyRules.FIXED_COST, description='FIXED_COST: FIXED_COST\nRATING_BASED: RATING_BASED', db_default='FIXED_COST', enum_type=SpecialtyRules, max_length=12),
        ),
    ]
