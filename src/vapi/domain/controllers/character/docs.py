"""Character endpoint documentation."""

LIST_CHARACTERS_DESCRIPTION = """\
Retrieve a paginated list of characters within a campaign.

Optionally, filter results by `user_player_id`, `user_creator_id`, `character_class`, `type`, or `status` to narrow down the character list.
"""

GET_CHARACTER_DESCRIPTION = """\
Retrieve detailed information about a specific character including traits, status, and biographical data.
"""

CREATE_CHARACTER_DESCRIPTION = """\
Create a new character within a campaign.

Provide character details and initial trait values. The character is associated with both a creator user (who made the character) and a player user (who controls the character). If no player is specified, the creator becomes the player.
"""

UPDATE_CHARACTER_DESCRIPTION = """\
Modify a character's properties such as name, biography, or other details.

Only include fields that need to be changed; omitted fields remain unchanged. Use trait-specific endpoints to modify character traits.

**Note:** Only the character's player or a storyteller can update the character.
"""

DELETE_CHARACTER_DESCRIPTION = """\
Remove a character from the campaign.

The character will no longer be accessible.

**Note:** Only the character's player or a storyteller can delete the character.
"""
