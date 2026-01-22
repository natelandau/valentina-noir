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

Optionally include desperation dice and associate the roll with a character and campaign. The roll result is calculated and stored automatically.
"""

QUICKROLL_DESCRIPTION = """\
Execute a dice roll using a user's saved quick roll configuration.

The dice pool is calculated automatically from the character's current trait values for the traits defined in the quick roll. Useful for frequently used trait combinations.
"""
