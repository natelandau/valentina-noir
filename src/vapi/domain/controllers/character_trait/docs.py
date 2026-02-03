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

GET_VALUE_OPTIONS_DESCRIPTION = """\
Retrieve all possible target values for a character trait with associated costs and affordability.

Returns the current value, min/max bounds, current XP and starting points, and a dictionary of options. Each option shows the point cost/refund, whether it's affordable with XP or starting points, and the resulting balance after the transaction.

Use this endpoint to display upgrade/downgrade options to users before they commit to a change.
"""

MODIFY_VALUE_DESCRIPTION = """\
Modify a character trait to a target value using the specified currency.

**Currency options:**
- `NO_COST`: Direct modification without spending points (storyteller/admin only)
- `XP`: Spend or refund experience points
- `STARTING_POINTS`: Spend or refund starting points

The direction (increase/decrease) is determined automatically from the current value. Guards and affordability checks are applied based on the currency type.

**Note:** `NO_COST` requires storyteller privileges. `XP` and `STARTING_POINTS` are available to character owners and storytellers. Company settings may restrict these currencies, use the `GET /value-options` endpoint to check availability.
"""

DELETE_CHARACTER_TRAIT_DESCRIPTION = """\
Remove a trait from a character.

**This action cannot be undone.**

**Note:** Only storyteller users and character owners can use this endpoint.
"""
