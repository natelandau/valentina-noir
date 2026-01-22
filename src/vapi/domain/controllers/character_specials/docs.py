"""Character specials endpoint documentation."""

# Hunter Edge Endpoints
LIST_HUNTER_EDGES_DESCRIPTION = """\
Retrieve a paginated list of hunter edges assigned to a character.

Edges represent the supernatural abilities and powers available to hunter characters.
"""

GET_HUNTER_EDGE_DESCRIPTION = """\
Retrieve a specific hunter edge including all its associated perks that the character has unlocked.
"""

LIST_HUNTER_EDGE_PERKS_DESCRIPTION = """\
Retrieve a paginated list of perks for a specific hunter edge.

Perks are specialized abilities within an edge that provide additional benefits.
"""

GET_HUNTER_EDGE_PERK_DESCRIPTION = """\
Retrieve detailed information about a specific hunter edge perk.
"""

ADD_HUNTER_EDGE_DESCRIPTION = """\
Add a hunter edge to a character's available powers.

**Note:** Only the character's player or a storyteller can add edges.
"""

REMOVE_HUNTER_EDGE_DESCRIPTION = """\
Remove a hunter edge from a character.

**Note:** Only the character's player or a storyteller can remove edges.
"""

ADD_HUNTER_EDGE_PERK_DESCRIPTION = """\
Add a perk to an existing hunter edge on a character.

The character must already have the edge to add perks to it.

**Note:** Only the character's player or a storyteller can add perks.
"""

REMOVE_HUNTER_EDGE_PERK_DESCRIPTION = """\
Remove a perk from a hunter edge on a character.

**Note:** Only the character's player or a storyteller can remove perks.
"""

# Werewolf Gift Endpoints
LIST_WEREWOLF_GIFTS_DESCRIPTION = """\
Retrieve a paginated list of werewolf gifts assigned to a character.

Gifts are supernatural abilities granted by spirits to werewolf characters.
"""

GET_WEREWOLF_GIFT_DESCRIPTION = """\
Retrieve detailed information about a specific werewolf gift including its effects and requirements.
"""

ADD_WEREWOLF_GIFT_DESCRIPTION = """\
Add a werewolf gift to a character's available powers.

**Note:** Only the character's player or a storyteller can add gifts.
"""

REMOVE_WEREWOLF_GIFT_DESCRIPTION = """\
Remove a werewolf gift from a character.

**Note:** Only the character's player or a storyteller can remove gifts.
"""

# Werewolf Rite Endpoints
LIST_WEREWOLF_RITES_DESCRIPTION = """\
Retrieve a paginated list of werewolf rites known by a character.

Rites are ceremonial abilities that werewolves can learn and perform.
"""

GET_WEREWOLF_RITE_DESCRIPTION = """\
Retrieve detailed information about a specific werewolf rite including its level and effects.
"""

ADD_WEREWOLF_RITE_DESCRIPTION = """\
Add a werewolf rite to a character's known rites.

**Note:** Only the character's player or a storyteller can add rites.
"""

REMOVE_WEREWOLF_RITE_DESCRIPTION = """\
Remove a werewolf rite from a character.

**Note:** Only the character's player or a storyteller can remove rites.
"""
