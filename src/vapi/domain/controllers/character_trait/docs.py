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

**Note:** Only storyteller users and character owners can use this endpoint. Respects the company's free trait changes setting. `NPC` and `STORYTELLER` characters only accept `NO_COST`; using `XP` or `STARTING_POINTS` returns 400.
"""

CREATE_CUSTOM_TRAIT_DESCRIPTION = """\
Create a new custom trait unique to this character.

Specify the trait name, category, optional cost configuration, and the `currency` used to buy the trait's first dot. Custom traits are useful for specializations or homebrew content. The trait is always created at a value of `1`.

Custom traits are `is_rollable` by default so they appear when listing a character's rollable traits. Set `is_rollable` to `false` to create a non-rollable custom trait.

**Currency options:**
- `NO_COST`: Add the trait without spending points (respects the company's free trait changes setting)
- `XP`: Spend experience points equal to the trait's initial cost
- `STARTING_POINTS`: Spend starting points equal to the trait's initial cost

**Note:** Only storyteller users and character owners can use this endpoint. `NO_COST` respects the company's free trait changes setting; `XP` and `STARTING_POINTS` are always available to character owners who can afford the cost. `NPC` and `STORYTELLER` characters only accept `NO_COST`; using `XP` or `STARTING_POINTS` returns 400. An `XP` or `STARTING_POINTS` cost the character cannot afford returns 400.
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

**NPC and STORYTELLER characters** only accept `NO_COST`. Using `XP` or `STARTING_POINTS` on these character types returns 400.

**Concurrent changes:** If another request changes the trait's value first, the change returns 409, leaves the value as the other request set it, and spends or refunds nothing. Fetch the trait again and retry.

**Specialties:** When an ability reaches a value of 0, its specialties are refunded and removed.
"""

DELETE_CHARACTER_TRAIT_DESCRIPTION = """\
Remove a trait from a character.

**This action cannot be undone.**

Any specialties on the trait are refunded and removed with it.

**Note:** Only storyteller users and character owners can use this endpoint. `NPC` and `STORYTELLER` characters only accept `NO_COST`; using `XP` or `STARTING_POINTS` returns 400. Returns 409 when another request changes the trait's value first while recouping `XP` or `STARTING_POINTS`.
"""

BULK_ASSIGN_TRAITS_DESCRIPTION = """\
Assign multiple traits to a character in a single request.

Accepts a list of trait assignments, each with a `trait_id`, `value`, and `currency`. Each trait is processed independently with best-effort semantics -successful assignments are saved and failed ones are reported with error details.

The response contains `succeeded` and `failed` lists. Retry only the failed items.

**Currency balances are tracked across the batch.** If early traits in the list spend XP or starting points, later traits see the reduced balance. Flaw traits (which grant currency) increase the running balance.

**Maximum batch size:** 200 items.

**Note:** Only storyteller users and character owners can use this endpoint. `NPC` and `STORYTELLER` characters only accept `NO_COST`; using `XP` or `STARTING_POINTS` returns 400.
"""

ADD_SPECIALTY_DESCRIPTION = """\
Add a free-text specialty to an ability trait.

Specialties are only available on ability traits (the Abilities section of the character sheet) that have a value of 1 or higher. An ability can have several specialties. The name must be 3 to 50 characters long and unique on the trait, ignoring case.

**Currency options:**
- `NO_COST`: Add the specialty without spending points (respects the company's free trait changes setting when the specialty XP cost setting is on)
- `XP`: Spend 3 experience points when the company's specialty XP cost setting is on
- `STARTING_POINTS`: Spend 3 starting points when the company's specialty XP cost setting is on

When the specialty XP cost setting is off, specialties are free and the `currency` does not affect the cost. The response is the updated character trait.

**Note:** Only storyteller users and character owners can use this endpoint. `NPC` and `STORYTELLER` characters only accept `NO_COST`; using `XP` or `STARTING_POINTS` returns 400. A cost the character cannot afford returns 400.
"""

UPDATE_SPECIALTY_DESCRIPTION = """\
Rename a specialty on an ability trait.

The name must be 3 to 50 characters long and unique on the trait, ignoring case. Renaming never changes the cost paid or the currency used. The response is the updated character trait.

**Note:** Only storyteller users and character owners can use this endpoint.
"""

DELETE_SPECIALTY_DESCRIPTION = """\
Remove a specialty from an ability trait.

The cost paid for the specialty is refunded in the currency used to buy it. A refund in `XP` follows the company's XP recoup setting: it is given when the setting is `UNRESTRICTED` or `WITHIN_SESSION` and skipped when it is `DENIED`. Starting points are always refunded. Removing the specialty is never refused because of the recoup setting.

**This action cannot be undone.**

**Note:** Only storyteller users and character owners can use this endpoint.
"""
