---
icon: lucide/wand-sparkles
---

# Character Autogen Service

Generate characters for a campaign using AI-assisted character creation.

## Usage

```python
from vclient import character_autogen_service

autogen = character_autogen_service(
    user_id="USER_ID",
    campaign_id="CAMPAIGN_ID",
    company_id="COMPANY_ID"
)
```

## Methods

| Method                                                        | Returns                  | Description                     |
| ------------------------------------------------------------- | ------------------------ | ------------------------------- |
| `generate_character(*, character_type, ...)`                  | `Character`              | Generate a single character     |
| `start_chargen_session()`                                     | `ChargenSessionResponse` | Start an interactive session    |
| `finalize_chargen_session(session_id, selected_character_id)` | `Character`              | Finalize and select a character |

## Generate Character Parameters

| Parameter             | Type                     | Required | Description                               |
| --------------------- | ------------------------ | -------- | ----------------------------------------- |
| `character_type`      | `CharacterType`          | Yes      | Type of character (PLAYER, NPC)           |
| `character_class`     | `CharacterClass`         | No       | Class (VAMPIRE, WEREWOLF, HUNTER, MORTAL) |
| `experience_level`    | `AutoGenExperienceLevel` | No       | Experience level                          |
| `skill_focus`         | `AbilityFocus`           | No       | Primary skill focus                       |
| `concept_id`          | `str`                    | No       | Character concept ID                      |
| `vampire_clan_id`     | `str`                    | No       | Vampire clan ID                           |
| `werewolf_tribe_id`   | `str`                    | No       | Werewolf tribe ID                         |
| `werewolf_auspice_id` | `str`                    | No       | Werewolf auspice ID                       |

!!! tip "Interactive Sessions"

    Use `start_chargen_session()` to generate multiple character options at once, allowing your users to choose their preferred character from several AI-generated alternatives.

## Example

```python
# Generate a single character
character = await autogen.generate_character(
    character_type="PLAYER",
    character_class="VAMPIRE",
    experience_level="NEONATE"
)

# Use an interactive session for multiple character options
session = await autogen.start_chargen_session()
print(f"Session expires: {session.expires_at}")
print(f"Characters available: {len(session.characters)}")

# Finalize by selecting one of the generated characters
final_character = await autogen.finalize_chargen_session(
    session_id=session.session_id,
    selected_character_id=session.characters[0].id
)
```

See [Response Models](models.md) for `Character` and `ChargenSessionResponse`.
