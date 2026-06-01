from tortoise import migrations
from tortoise.migrations import operations as ops
from vapi.constants import PermissionManageNPC
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0007_auto_20260601_1252')]

    initial = False

    operations = [
        ops.AddField(
            model_name='CompanySettings',
            name='permission_manage_npc',
            field=fields.CharEnumField(default=PermissionManageNPC.UNRESTRICTED, description='UNRESTRICTED: UNRESTRICTED\nSTORYTELLER: STORYTELLER', db_default='UNRESTRICTED', enum_type=PermissionManageNPC, max_length=12),
        ),
    ]
