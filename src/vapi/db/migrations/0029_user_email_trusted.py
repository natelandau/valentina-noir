from tortoise import fields, migrations
from tortoise.migrations import operations as ops

# Trust an existing email only where a stored provider profile proves it. Google and Apple
# profiles store the email from a signed ID token; Discord stores its own verified flag.
# GitHub profiles can hold an unverified public email, so they never establish trust.
BACKFILL_EMAIL_TRUSTED_SQL = (
    'UPDATE "user" SET email_trusted = TRUE'
    " WHERE lower(email) = lower(google_profile->>'email')"
    " OR lower(email) = lower(apple_profile->>'email')"
    " OR (lower(email) = lower(discord_profile->>'email')"
    " AND discord_profile->>'verified' = 'true');"
)


class Migration(migrations.Migration):
    dependencies = [("models", "0028_simplify_trackers")]

    initial = False

    operations = [
        ops.AddField(
            model_name="User",
            name="email_trusted",
            field=fields.BooleanField(default=False, db_default=False),
        ),
        ops.RunSQL(sql=BACKFILL_EMAIL_TRUSTED_SQL, reverse_sql=ops.RunSQL.noop),
    ]
