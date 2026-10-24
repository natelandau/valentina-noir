"""Character health endpoint documentation."""

GET_HEALTH_DESCRIPTION = """\
Retrieve a character's current health track.

The response shape follows the character's game version:

- **V4:** bashing, lethal, and aggravated damage marked across the named health levels, each with its dice penalty, plus `extra_levels` and the `current_penalty`.
- **V5:** superficial and aggravated damage marked across a track sized by Stamina plus three, plus any `extra_levels`.

The track size updates automatically when the character's Stamina changes.

**Returns 404 when:** the character has no health track.
"""

SET_HEALTH_DESCRIPTION = """\
Set a character's full health state in one request.

Send every field you want stored. Omitted fields reset to 0.

**Body fields:**
- `extra_levels`: Additional health levels beyond the base track
- V4: `bashing`, `lethal`, `aggravated`
- V5: `superficial`, `aggravated`

**Returns 400 when:**
- A damage field does not apply to the character's game version and is non-zero
- A value is negative
- The marks added together exceed the resulting track size

**Returns 404 when:** the character has no health track.

**Note:** Only the character's player or a storyteller can change health.
"""

APPLY_HEALTH_ACTION_DESCRIPTION = """\
Apply one in-play action to a character's health.

**Body fields:**
- `action`: `damage`, `heal`, or `reset`
- `amount`: How many boxes to change, at least 1 (default 1)
- `damage_type`: Required for `damage` and `heal`, and not accepted for `reset`. V4 accepts `BASHING`, `LETHAL`, and `AGGRAVATED`. V5 accepts `SUPERFICIAL` and `AGGRAVATED`.

**Returns 400 when:**
- The action is not accepted for the character's game version
- `damage_type` is missing, not accepted for the game version, or sent with an action that takes none

**Returns 404 when:** the character has no health track.

**Note:** Only the character's player or a storyteller can change health.
"""
