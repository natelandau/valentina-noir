"""Character health endpoint documentation."""

GET_HEALTH_DESCRIPTION = """\
Retrieve a character's current health track.

Damage is one count with no damage types. The response shape follows the character's game version:

- **V4:** `damage` marked down the named health `levels` from Bruised, plus `extra_levels`.
- **V5:** `damage` on a track sized by Stamina plus three, plus any `extra_levels`.

The track size updates automatically when the character's Stamina changes.

**Returns 404 when:** the character has no health track.
"""

SET_HEALTH_DESCRIPTION = """\
Set a character's full health state in one request.

Send every field you want stored. Omitted fields reset to 0.

**Body fields:**
- `extra_levels`: Additional health levels beyond the base track
- `damage`: Boxes of damage

**Returns 400 when:**
- The body has any other field
- A value is negative
- `damage` exceeds the resulting track size

**Returns 404 when:** the character has no health track.

**Note:** Only the character's player or a storyteller can change health.
"""

APPLY_HEALTH_ACTION_DESCRIPTION = """\
Apply one in-play action to a character's health.

**Body fields:**
- `action`: `damage`, `heal`, or `reset`
- `amount`: How many boxes to change, at least 1 (default 1)

Damage past a full track and healing past zero are dropped.

**Returns 400 when:**
- The action is not `damage`, `heal`, or `reset`

**Returns 404 when:** the character has no health track.

**Note:** Only the character's player or a storyteller can change health.
"""
