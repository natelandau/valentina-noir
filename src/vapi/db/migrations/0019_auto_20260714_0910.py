from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.fields.base import OnDelete
from uuid_utils._uuid_utils import uuid7
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0018_auto_20260713_0754')]

    initial = False

    operations = [
        ops.CreateModel(
            name='TraitPower',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid7, unique=True, db_index=True)),
                ('date_created', fields.DatetimeField(auto_now=False, auto_now_add=True)),
                ('date_modified', fields.DatetimeField(auto_now=True, auto_now_add=False)),
                ('is_archived', fields.BooleanField(default=False)),
                ('archive_date', fields.DatetimeField(null=True, auto_now=False, auto_now_add=False)),
                ('archive_batch_id', fields.UUIDField(null=True, db_index=True)),
                ('level', fields.IntField()),
                ('name', fields.CharField(max_length=100, null=True)),
                ('description', fields.TextField(null=True, unique=False)),
                ('system', fields.TextField(null=True, unique=False)),
                ('link', fields.TextField(null=True, unique=False)),
                ('trait', fields.ForeignKeyField('models.Trait', source_field='trait_id', db_constraint=True, to_field='id', related_name='powers', on_delete=OnDelete.CASCADE)),
            ],
            options={'table': 'trait_power', 'app': 'models', 'unique_together': (('trait', 'level', 'name'),), 'pk_attr': 'id', 'table_description': 'A named power a trait grants at a specific dot level (e.g. a Discipline or Thaumaturgy path power).'},
            bases=['BaseModel'],
        ),
    ]
