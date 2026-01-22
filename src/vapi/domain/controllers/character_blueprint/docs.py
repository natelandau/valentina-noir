"""Character blueprint endpoint documentation."""

# Sheet Sections
LIST_SECTIONS_DESCRIPTION = """\
Retrieve character sheet sections for a game version.

Sections organize trait categories on the character sheet (e.g., Attributes, Abilities, Backgrounds). Optionally filter by character class to get class-specific sections.
"""

GET_SECTION_DESCRIPTION = """\
Retrieve a specific character sheet section including its metadata, ordering, and display configuration.
"""

# Categories
LIST_CATEGORIES_DESCRIPTION = """\
Retrieve trait categories within a sheet section for a game version.

Categories group related traits together (e.g., `Physical`, `Social`, `Mental` attributes). Optionally filter by character class for class-specific categories.
"""

GET_CATEGORY_DESCRIPTION = """\
Retrieve a specific trait category including its cost configuration, value constraints, and metadata.
"""

# Category Traits
LIST_CATEGORY_TRAITS_DESCRIPTION = """\
Retrieve traits within a category for a game version.

These are the individual traits that can be assigned to characters (e.g., `Strength`, `Firearms`, `Resources`). Optionally filter by character class or include custom traits for a specific character.
"""

GET_TRAIT_DESCRIPTION = """\
Retrieve a specific trait including its value range, cost configuration, and metadata.
"""

# All Traits
LIST_ALL_TRAITS_DESCRIPTION = """\
Retrieve all system traits regardless of game version or character class.

Excludes custom character-specific traits. Useful for building trait selection interfaces or validating trait references.
"""

# Concepts
LIST_CONCEPTS_DESCRIPTION = """\
Retrieve all character concepts available in the system.

Concepts define character archetypes and provide narrative hooks for character creation. Includes both system-wide and company-specific concepts.
"""

GET_CONCEPT_DESCRIPTION = """\
Retrieve a specific character concept including its name, description, and example applications.
"""

# Vampire Clans
LIST_VAMPIRE_CLANS_DESCRIPTION = """\
Retrieve all vampire clans available in the system.

Optionally filter by game version to get version-specific clans.
"""

GET_VAMPIRE_CLAN_DESCRIPTION = """\
Retrieve a specific vampire clan including its name, disciplines, and lore description.
"""

# Werewolf Tribes
LIST_WEREWOLF_TRIBES_DESCRIPTION = """\
Retrieve all werewolf tribes available in the system.

Optionally filter by game version to get version-specific tribes.
"""

GET_WEREWOLF_TRIBE_DESCRIPTION = """\
Retrieve a specific werewolf tribe including its name, gifts, and cultural description.
"""

# Werewolf Auspices
LIST_WEREWOLF_AUSPICES_DESCRIPTION = """\
Retrieve all werewolf auspices available in the system.

Auspices represent the moon phase under which a werewolf was born. Optionally filter by game version.
"""

GET_WEREWOLF_AUSPICE_DESCRIPTION = """\
Retrieve a specific werewolf auspice including its name, gifts, and role description.
"""

# Werewolf Gifts
LIST_WEREWOLF_GIFTS_BLUEPRINT_DESCRIPTION = """\
Retrieve all werewolf gifts available in the system.

Gifts are supernatural abilities. Optionally filter by tribe, auspice, or game version.
"""

GET_WEREWOLF_GIFT_BLUEPRINT_DESCRIPTION = """\
Retrieve a specific werewolf gift including its level, cost, and effect description.
"""

# Werewolf Rites
LIST_WEREWOLF_RITES_BLUEPRINT_DESCRIPTION = """\
Retrieve all werewolf rites available in the system.

Rites are ceremonial abilities that werewolves can learn and perform.
"""

GET_WEREWOLF_RITE_BLUEPRINT_DESCRIPTION = """\
Retrieve a specific werewolf rite including its level, requirements, and effect description.
"""

# Hunter Edges
LIST_HUNTER_EDGES_BLUEPRINT_DESCRIPTION = """\
Retrieve all hunter edges available in the system.

Edges represent the supernatural abilities available to hunter characters. Optionally filter by edge type.
"""

GET_HUNTER_EDGE_BLUEPRINT_DESCRIPTION = """\
Retrieve a specific hunter edge including its type, perks, and effect description.
"""

# Hunter Edge Perks
LIST_HUNTER_EDGE_PERKS_BLUEPRINT_DESCRIPTION = """\
Retrieve all perks for a specific hunter edge.

Perks are specialized abilities within an edge that provide additional benefits.
"""

GET_HUNTER_EDGE_PERK_BLUEPRINT_DESCRIPTION = """\
Retrieve a specific hunter edge perk including its cost and effect description.
"""
