# Core Concepts

Understanding these core concepts helps you build clients that integrate with the Valentina Noir API.

## API Structure

**Developers (You)** - Use your API key to authenticate requests. A single API key grants access to one or more companies. [Developer permissions](../technical/authentication.md#developer-permissions) control company governance (managing settings, granting other developers access), not access to game resources.

**[Companies](../technical/companies.md)** - Companies are the foundational entity and the tenant boundary. Each company maintains its own users, campaigns, and characters, fully isolated from other companies.

**[End Users](../technical/user_management.md)** - Players and storytellers interact with your application. Your app authenticates them and makes API calls on their behalf. The API enforces game rules based on each user's [role](../technical/user_management.md#user-roles) (player, storyteller, admin).

**Campaigns** - Storytellers create campaigns to organize their game worlds. Each campaign contains:

- **Books** - Track a singular theme or storyline
- **Chapters** - Represent individual gaming sessions
- Characters, NPCs, experience, and other game elements are tracked at the campaign level

**[Characters](./characters.md)** - Characters represent players and NPCs in a campaign.

## Customized World of Darkness System

Valentina Noir uses a customized version of World of Darkness. These changes evolved from a 30+ year campaign and include:

- [Dice rolling system](./dice.md)
- [Experience system](./experience.md)
- [Dictionary terms](./dictionary.md) for looking up game terminology

## Supported Editions

The API supports characters created for these World of Darkness editions:

- World of Darkness v4
- World of Darkness v5

## Character Classes

The API supports these character classes:

| Class    | Support Level |
| -------- | ------------- |
| Vampire  | Full          |
| Werewolf | Full          |
| Hunter   | Full          |
| Mortal   | Full          |
| Ghoul    | Full          |
| Mage     | Partial       |

!!! info "Mage Support"

    Mage `Spheres` and `Traditions` have limited support. See the [roadmap](../roadmap/index.md) for details.
