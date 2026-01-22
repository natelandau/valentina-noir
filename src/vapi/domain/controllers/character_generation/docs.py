"""Character generation documentation."""

AUTOGEN_DOCUMENTATION = """\
Generate a complete character using randomized values. Useful for quick NPC or Storyteller character creation.

**Optionally specify:**
- Character type
- Experience level
- Skill focus
- Concept
- Affiliation (clan/tribe/auspice/etc.)


**Access:**
* Only Storytellers can use this endpoint.
"""

CHARGEN_START_DOCUMENTATION = """\
Begin a character generation session by generating multiple character options.  The number of characters generated is controlled by the company's `character_autogen_num_choices` setting. The experience cost is controlled by the company's `character_autogen_xp_cost` setting.

If a single character is generated, it is automatically marked as active and the user is not required to select it.

If multiple characters are generated, the user must select one of the characters to keep. This can be done by calling the `.../chargen/finalize` endpoint with the selected character ID.

**Note:** No character is activated until it has been finalized.

**Workflow:**
1. Call this endpoint to generate character options.
2. Present options to the player
3. Call `.../chargen/finalize` with the selected character ID

**Access:**
* The user must have enough experience points to complete the action. If the user does not have enough experience points, the endpoint will return a 400 error.
"""

CHARGEN_FINALIZE_DOCUMENTATION = """\
Complete a character generation session by selecting one character to keep.
All other characters from the session will be deleted.

**Prerequisites:**
- Must have an active chargen session
- The selected character must belong to the provided session
"""
