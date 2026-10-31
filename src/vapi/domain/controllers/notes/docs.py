"""Notes endpoint documentation."""

_WRITE_PERMISSIONS = """\
Requires the `On-Behalf-Of` header. The acting user must be allowed to write to the parent:

- **Character notes:** the character's player, or a storyteller or admin. NPC notes follow the company's `permission_manage_npc` setting.
- **User notes:** the user themself, or an admin.
- **Campaign, book, and chapter notes:** any user the company's `permission_manage_campaign` setting allows.
"""

LIST_NOTES_DESCRIPTION = """\
Retrieve a paginated list of notes attached to the parent object.
"""

GET_NOTE_DESCRIPTION = """\
Retrieve a specific note including its content and metadata.
"""

CREATE_NOTE_DESCRIPTION = (
    """\
Attach a new note to the parent object. Notes support markdown formatting.

"""
    + _WRITE_PERMISSIONS
)

UPDATE_NOTE_DESCRIPTION = (
    """\
Modify a note's content. Only include fields that need to be changed.

"""
    + _WRITE_PERMISSIONS
)

DELETE_NOTE_DESCRIPTION = (
    """\
Remove a note. This action cannot be undone.

"""
    + _WRITE_PERMISSIONS
)
