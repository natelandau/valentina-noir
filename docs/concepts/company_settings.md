---
icon: lucide/settings
---

# Company Settings

Administrators for each company are able to configure the following settings to allow the customization of the game experience.

## Campaign Management

**Manage Campaigns** - Who is able to create, update, and delete campaigns, books, and chapters?

-   `UNRESTRICTED` - Any user can create, update, and delete campaigns, books, and chapters. (Default)
-   `STORYTELLER ONLY` - Only the storyteller can create, update, and delete campaigns, books, and chapters.

**XP Management** - Who is able to grant experience to players?

-   `UNRESTRICTED` - Any user can grant experience to players. (Default)
-   `STORYTELLER ONLY` - Only the storyteller can grant experience to players.

## Character Autogeneration

**XP Cost for Character Autogen** - The experience required to use the character autogeneration engine. Default is set to `10 xp` and can be any positive integer

**Number of Characters to Autogen** - When using the character autogeneration engine, how many characters should be generated for a user to select from? Default is set to `3` and can be any integer between `1` and `10`.

## Character Management

**Free Trait Updates** - Determines when a player can update traits and values for their own character _without needing to spend experience points_. Useful if errors were made during character creation or the Storyteller grants a skill to a character during the game. **Note:** This setting only applies to the character owner - Storytellers and admins can change a trait's value on any character at any time bypassing the experience point cost.

-   `UNRESTRICTED` - The player who owns the character can change a trait's value at any time bypassing the experience point cost. (Default)
-   `WITHIN 24 HOURS` - The player who owns the character can change a trait's value for free within `24 hours` of the character being created.
-   `STORYTELLER ONLY` - Only the storyteller can change add a new trait or change a trait's value bypassing the experience point cost.
