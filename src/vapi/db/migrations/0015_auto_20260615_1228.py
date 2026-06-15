from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.fields.base import OnDelete
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0014_auto_20260608_2241')]

    initial = False

    operations = [
        ops.AddField(
            model_name='CampaignChapter',
            name='characters',
            field=fields.ManyToManyField('models.Character', unique=True, db_constraint=True, through='j_campaign_chapter_characters', forward_key='character_id', backward_key='campaign_chapter_id', related_name='chapters', on_delete=OnDelete.CASCADE),
        ),
    ]
