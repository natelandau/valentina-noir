from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.indexes import Index

class Migration(migrations.Migration):
    dependencies = [('models', '0003_auto_20260412_1249')]

    initial = False

    operations = [
        ops.AddIndex(
            model_name='AuditLog',
            index=Index(fields=['developer_id', 'date_created']),
        ),
    ]
