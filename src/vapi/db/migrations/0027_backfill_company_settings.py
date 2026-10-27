from tortoise import migrations
from tortoise.migrations import operations as ops

# Give every company without a settings row one at the model defaults. Archive stamps are
# copied from the company so a batch restore brings the row back with it.
BACKFILL_COMPANY_SETTINGS_SQL = (
    "INSERT INTO company_settings ("
    " id, date_created, date_modified, is_archived, archive_date, archive_batch_id,"
    " company_id, character_autogen_xp_cost, character_autogen_num_choices,"
    " character_autogen_starting_points, permission_manage_campaign, permission_manage_npc,"
    " permission_grant_xp, permission_free_trait_changes, permission_recoup_xp,"
    " specialty_xp_cost_enabled"
    ") "
    "SELECT"
    " gen_random_uuid(), now(), now(), c.is_archived, c.archive_date, c.archive_batch_id,"
    " c.id, 10, 3, 0, 'UNRESTRICTED', 'UNRESTRICTED', 'UNRESTRICTED', 'UNRESTRICTED',"
    " 'DENIED', false "
    "FROM company c "
    "WHERE NOT EXISTS (SELECT 1 FROM company_settings s WHERE s.company_id = c.id) "
    "ON CONFLICT (company_id) DO NOTHING;"
)


class Migration(migrations.Migration):
    dependencies = [("models", "0026_reference_data_seed")]

    initial = False

    operations = [
        ops.RunSQL(sql=BACKFILL_COMPANY_SETTINGS_SQL, reverse_sql=ops.RunSQL.noop),
    ]
