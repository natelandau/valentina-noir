"""Character trait endpoint documentation."""

LIST_CHARACTER_TRAITS_DESCRIPTION = """\
Retrieve a paginated list of traits assigned to a character.

Each trait includes the base trait definition and the character's current value. Optionally filter by parent category to view specific trait groups.
"""

GET_CHARACTER_TRAIT_DESCRIPTION = """\
Retrieve a specific character trait including the base trait definition and current value.
"""

ASSIGN_TRAIT_DESCRIPTION = """\
Assign a trait to a character with an initial value.

The trait must not already exist on the character and the value must not exceed the trait's maximum.

**Note:** Only storyteller users and character owners can use this endpoint. Respects the company's free trait changes setting.
"""

CREATE_CUSTOM_TRAIT_DESCRIPTION = """\
Create a new custom trait unique to this character.

Specify the trait name, category, and optional cost configuration. Custom traits are useful for specializations or homebrew content.

**Note:** Only storyteller users and character owners can use this endpoint. Respects the company's free trait changes setting.
"""

INCREASE_TRAIT_VALUE_DESCRIPTION = """\
Increase a character trait's value by a specified number of dots.

The value cannot exceed the trait's maximum.

**Note:** Only storyteller users can use this endpoint. Respects the company's free trait changes setting.
"""

DECREASE_TRAIT_VALUE_DESCRIPTION = """\
Decrease a character trait's value by a specified number of dots.

The value cannot go below zero.

**Note:** Only storyteller users can use this endpoint. Respects the company's free trait changes setting.
"""

PURCHASE_TRAIT_XP_DESCRIPTION = """\
Purchase trait dots with experience points.

The XP cost is calculated based on the trait's cost configuration and deducted from the user's campaign experience points.

**Note:** Only storyteller users and character owners can use this endpoint.
"""

REFUND_TRAIT_XP_DESCRIPTION = """\
Refund trait dots and recover experience points.

By downgrading the number of dots on the trait, the user is refunded the experience points spent on those trait dots. The XP is added to the user's campaign experience points.

**Note:** Only storyteller users and character owners can use this endpoint.
"""

PURCHASE_STARTING_POINTS_DESCRIPTION = """\
Purchase trait dots using starting points.

Starting points are a separate pool from experience points used during character creation. The points are deducted from the user's available starting points.

**Note:** Only storyteller users and character owners can use this endpoint.
"""

REFUND_STARTING_POINTS_DESCRIPTION = """\
Refund trait dots and recover starting points.

The starting points are added back to the user's available pool.

**Note:** Only storyteller users and character owners can use this endpoint.
"""

DELETE_CHARACTER_TRAIT_DESCRIPTION = """\
Remove a trait from a character.

**This action cannot be undone.**

**Note:** Only storyteller users and character owners can use this endpoint.
"""
