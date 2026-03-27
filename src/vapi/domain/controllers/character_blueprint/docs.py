"""Character blueprint endpoint documentation."""

# Sheet Sections
LIST_SECTIONS_DESCRIPTION = """\
Retrieve character sheet sections.

Sections organize trait categories on the character sheet (e.g., Attributes, Abilities, Backgrounds). Optionally filter by game version or character class.
"""

GET_SECTION_DESCRIPTION = """\
Retrieve a specific character sheet section including its metadata, ordering, and display configuration.
"""

# Categories
LIST_CATEGORIES_DESCRIPTION = """\
Retrieve trait categories.

Categories group related traits together (e.g., `Physical`, `Social`, `Mental` attributes). Optionally filter by game version, section, or character class.
"""

GET_CATEGORY_DESCRIPTION = """\
Retrieve a specific trait category including its cost configuration, value constraints, and metadata.
"""

# Subcategories
LIST_SUBCATEGORIES_DESCRIPTION = """\
Retrieve trait subcategories.

Subcategories group related traits together (e.g., `Resources`, `Allies`, `Flaws`). Optionally filter by game version, category, or character class.
"""

GET_SUBCATEGORY_DESCRIPTION = """\
Retrieve a specific trait subcategory including its name, description, and metadata.
"""

# Traits
GET_TRAIT_DESCRIPTION = """\
Retrieve a specific trait including its value range, cost configuration, and metadata.
"""

# All Traits
LIST_ALL_TRAITS_DESCRIPTION = """\
Retrieve all system traits.

Excludes custom character-specific traits. Supports filtering by game version, character class, category, subcategory, and rollable status. Use `exclude_subcategory_traits` to return only top-level traits.
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
