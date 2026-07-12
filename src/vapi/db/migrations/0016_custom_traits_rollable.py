from tortoise import migrations
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    dependencies = [("models", "0015_auto_20260615_1228")]

    initial = False

    operations = [
        # Custom traits were previously created non-rollable (the is_rollable
        # default), so they never appeared in rollable-filtered trait lists.
        # Backfill every existing custom trait to rollable to match the new
        # create-custom-trait default.
        ops.RunSQL(
            sql="UPDATE trait SET is_rollable = true WHERE is_custom = true;",
            reverse_sql="UPDATE trait SET is_rollable = false WHERE is_custom = true;",
        ),
    ]
