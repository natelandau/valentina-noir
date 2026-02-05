# Core Concepts

Understanding these core concepts helps you build clients that integrate with the Valentina Noir API.

## API Structure

**Developers (You)** - Use your API key to authenticate requests. This key determines which actions you can perform. You can create unlimited applications with a single API key.

**[Companies](../technical/companies.md)** - Companies are the foundational entity. Each company maintains its own users, campaigns, and characters.

**[End Users](../technical/user_management.md)** - Players and storytellers interact with your client. They create and manage characters, campaigns, and other game resources.

**Campaigns** - Storytellers create campaigns to organize their game worlds. Each campaign contains:

-   **Books** - Track a singular theme or storyline
-   **Chapters** - Represent individual gaming sessions
-   Characters, NPCs, experience, and other game elements are tracked at the campaign level

**[Characters](./characters.md)** - Characters represent players and NPCs in a campaign.

## Customized World of Darkness System

Valentina Noir uses a customized version of World of Darkness. These changes evolved from a 30+ year campaign and include:

-   [Dice rolling system](./dice.md)
-   [Experience system](./experience.md)

## Supported Editions

The API supports characters created for these World of Darkness editions:

-   World of Darkness v4
-   World of Darkness v5

## Character Classes

The API supports these character classes:

| Class | Support Level |
| --- | --- |
| Vampire | Full |
| Werewolf | Full |
| Hunter | Full |
| Mortal | Full |
| Ghoul | Full |
| Mage | Partial |

!!! info "Mage Support"
    Mage `Spheres` and `Traditions` have limited support. See the [roadmap](../roadmap/index.md) for details.
