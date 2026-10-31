"""Dice roll endpoint documentation."""

LIST_DICEROLLS_DESCRIPTION = """\
Retrieve a paginated list of dice roll records within a company.

Filter by user, character, or campaign to view specific roll history. Results include roll outcomes, dice pools, and difficulty settings.
"""

GET_DICEROLL_DESCRIPTION = """\
Retrieve details of a specific dice roll including the result, dice pool, difficulty, and any successes or failures.
"""

CREATE_DICEROLL_DESCRIPTION = """\
Execute a dice roll with the specified pool size and difficulty.

Optionally include desperation dice and associate the roll with a character and campaign. The roll result is calculated and stored automatically. When you send both `character_id` and `campaign_id` and the character belongs to a campaign, `campaign_id` must be that campaign. Otherwise the request returns `400 Bad Request`.

`num_dice` must be between 0 and 100, `num_desperation_dice` between 0 and 5, and `difficulty` between 0 and 100. `trait_ids` can hold up to 20 IDs, and `comment` up to 2000 characters. Values outside these limits return `400 Bad Request`.

Only storytellers and admins can roll for a `STORYTELLER` character. Other users get `403 Forbidden`.
"""

QUICKROLL_DESCRIPTION = """\
Execute a dice roll using a user's saved quick roll configuration.

The dice pool is calculated automatically from the character's current trait values for the traits defined in the quick roll. Useful for frequently used trait combinations.

`num_desperation_dice` must be between 0 and 5, `difficulty` between 0 and 100, and `comment` can hold up to 2000 characters. If the character's trait values add up to more than 100 dice, the request returns `400 Bad Request`.

Only storytellers and admins can roll for a `STORYTELLER` character. Other users get `403 Forbidden`.
"""
