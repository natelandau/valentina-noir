from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0029_user_email_trusted')]

    initial = False

    operations = [
        ops.AddField(
            model_name='DiceRoll',
            name='dice_modifier',
            field=fields.IntField(default=0, db_default=0),
        ),
    ]
