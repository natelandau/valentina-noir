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

GET_CHARACTER_FULL_SHEET_DESCRIPTION = """\
Retrieve the full character sheet including all traits, attributes, and other character data. Traits are organized in a hierarchical dictionary of sheet sections, categories, optional subcategories, traits, and values.

Set `include_available_traits=true` to also include standard traits that the character could add but hasn't yet, organized within the same category and subcategory hierarchy.
"""

GET_CHARACTER_FULL_SHEET_CATEGORY_DESCRIPTION = """\
Retrieve a single category slice of the character's full sheet, including its subcategories and traits.

Use this endpoint to efficiently refresh a specific category after a trait edit, rather than re-fetching the entire full sheet. The response uses the same DTO structure as categories within the full sheet response.

Set `include_available_traits=true` to also include standard traits that the character could add but hasn't yet within this category.
"""
