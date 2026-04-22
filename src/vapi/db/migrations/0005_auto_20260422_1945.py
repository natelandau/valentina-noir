from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.indexes import Index

class Migration(migrations.Migration):
    dependencies = [('models', '0004_auto_20260419_0921')]

    initial = False

    operations = [
        ops.AddIndex(
            model_name='AuditLog',
            index=Index(fields=['date_created']),
        ),
    ]
