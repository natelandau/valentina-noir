from tortoise import migrations
from tortoise.migrations import operations as ops
import functools
from json import dumps, loads
from tortoise.fields.base import OnDelete
from vapi.constants import AuditEntityType, AuditOperation, UserRole
from tortoise import fields
from tortoise.indexes import Index

class Migration(migrations.Migration):
    dependencies = [('models', '0002_auto_20260407_1459')]

    initial = False

    operations = [
        ops.AddField(
            model_name='AuditLog',
            name='acting_user',
            field=fields.ForeignKeyField('models.User', source_field='acting_user_id', null=True, db_constraint=True, to_field='id', related_name='audit_logs_acted', on_delete=OnDelete.SET_NULL),
        ),
        ops.AddField(
            model_name='AuditLog',
            name='book',
            field=fields.ForeignKeyField('models.CampaignBook', source_field='book_id', null=True, db_constraint=True, to_field='id', related_name='audit_logs', on_delete=OnDelete.SET_NULL),
        ),
        ops.AddField(
            model_name='AuditLog',
            name='campaign',
            field=fields.ForeignKeyField('models.Campaign', source_field='campaign_id', null=True, db_constraint=True, to_field='id', related_name='audit_logs', on_delete=OnDelete.SET_NULL),
        ),
        ops.AddField(
            model_name='AuditLog',
            name='changes',
            field=fields.JSONField(null=True, encoder=functools.partial(dumps, separators=(',', ':')), decoder=loads),
        ),
        ops.AddField(
            model_name='AuditLog',
            name='chapter',
            field=fields.ForeignKeyField('models.CampaignChapter', source_field='chapter_id', null=True, db_constraint=True, to_field='id', related_name='audit_logs', on_delete=OnDelete.SET_NULL),
        ),
        ops.AddField(
            model_name='AuditLog',
            name='character',
            field=fields.ForeignKeyField('models.Character', source_field='character_id', null=True, db_constraint=True, to_field='id', related_name='audit_logs', on_delete=OnDelete.SET_NULL),
        ),
        ops.AddField(
            model_name='AuditLog',
            name='company',
            field=fields.ForeignKeyField('models.Company', source_field='company_id', null=True, db_constraint=True, to_field='id', related_name='audit_logs', on_delete=OnDelete.SET_NULL),
        ),
        ops.AddField(
            model_name='AuditLog',
            name='entity_type',
            field=fields.CharEnumField(null=True, description='ASSET: ASSET\nBOOK: BOOK\nCAMPAIGN: CAMPAIGN\nCHAPTER: CHAPTER\nCHARACTER: CHARACTER\nCHARACTER_INVENTORY: CHARACTER_INVENTORY\nCHARACTER_TRAIT: CHARACTER_TRAIT\nCHARGEN_SESSION: CHARGEN_SESSION\nCOMPANY: COMPANY\nDEVELOPER: DEVELOPER\nDICTIONARY_TERM: DICTIONARY_TERM\nEXPERIENCE: EXPERIENCE\nNOTE: NOTE\nQUICKROLL: QUICKROLL\nUSER: USER', enum_type=AuditEntityType, max_length=19),
        ),
        ops.AddField(
            model_name='AuditLog',
            name='operation',
            field=fields.CharEnumField(null=True, description='CREATE: CREATE\nUPDATE: UPDATE\nDELETE: DELETE', enum_type=AuditOperation, max_length=6),
        ),
        ops.AddField(
            model_name='AuditLog',
            name='target_entity_id',
            field=fields.UUIDField(null=True),
        ),
        ops.AddField(
            model_name='AuditLog',
            name='user',
            field=fields.ForeignKeyField('models.User', source_field='user_id', null=True, db_constraint=True, to_field='id', related_name='audit_logs_targeted', on_delete=OnDelete.SET_NULL),
        ),
        ops.AddIndex(
            model_name='AuditLog',
            index=Index(fields=['company_id', 'entity_type']),
        ),
        ops.AddIndex(
            model_name='AuditLog',
            index=Index(fields=['company_id', 'date_created']),
        ),
        ops.AddIndex(
            model_name='AuditLog',
            index=Index(fields=['developer_id', 'date_created']),
        ),
        ops.AlterField(
            model_name='User',
            name='role',
            field=fields.CharEnumField(description='ADMIN: ADMIN\nSTORYTELLER: STORYTELLER\nPLAYER: PLAYER\nUNAPPROVED: UNAPPROVED\nDEACTIVATED: DEACTIVATED', enum_type=UserRole, max_length=11),
        ),
        ops.RemoveField(model_name='AuditLog', name='name'),
    ]
