---
icon: lucide/scroll-text
---

# House Rules

Valentina Noir changes some World of Darkness rules on purpose, to keep play and client apps simple. This page lists each difference from the published V4 and V5 games. The API applies these rules, so a client that shows the API responses follows them without extra work.

| Area       | Published games                                                                      | Valentina Noir                                                                                  |
| ---------- | ------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------- |
| Dice       | Each game version has its own dice rules.                                            | One dice system for V4 and V5. Ones remove a success and tens count as two successes.          |
| Experience | Each character earns and spends its own experience.                                 | The player owns the experience, per campaign, and can spend it on any of their characters.     |
| Health     | Several damage types (bashing, lethal, and aggravated in V4, superficial and aggravated in V5). | One damage type. Damage adds boxes and healing removes them.                       |
| Penalties  | Damage, stains, and other effects impose dice penalties and impairment.               | The API tracks no dice penalties and no impairment. Players apply them to their own dice.      |
| Willpower  | V5 Willpower is a damage track.                                                      | Willpower is a spend-and-gain counter in V4 and V5.                                             |
| Humanity   | Stains and the Humanity rules apply to the character types of each game.             | Only V5 vampires track stains. Every other character with Humanity has a spend-and-gain counter. |
| Stains     | In V5, stains that do not fit on the Humanity track also damage Willpower.           | Extra stains are recorded and have no other effect.                                             |

## Dice

Valentina uses one dice system for both game versions. Each die at or above the difficulty is one success, each one removes a success, and each ten counts as two successes. The API has no Hunger dice. See [Rolling Dice](./dice.md) for the outcomes and examples.

## Experience

Experience belongs to the player, not to a character. The API records it for each campaign, and the player can spend it on any of their characters in that campaign. Storytellers can also give Cool Points, which are worth 10 XP each. See [Experience](./experience.md).

## Health

Health records one number: the count of boxes that hold damage. There are no damage types, so damage never upgrades from one type to another.

- V4 health has the seven named levels from Bruised to Incapacitated.
- V5 health has Stamina plus 3 boxes.
- Damage past a full track is dropped.

The track does not report dice penalties, impairment, or a state such as incapacitated, in torpor, or dead. The players and the Storyteller decide these in play, and you record a death with the `status` field of the character. See [Health](./trackers_and_health.md#health).

## Willpower

Willpower is a counter in both game versions. Players spend points and regain them, the same as Blood Pool. V5 Willpower keeps its value of Composure plus Resolve. See [V5 Willpower](./trackers_and_health.md#v5-willpower).

## Humanity and Stains

Only V5 vampires track stains on Humanity. All other characters with Humanity have a counter, the same as Willpower. This includes V4 vampires and V5 mortals, ghouls, and hunters.

A V5 vampire can have more stains than free Humanity boxes. The extra stains do not damage Willpower or impose a penalty. The API does not roll Remorse at the end of a session. The Storyteller removes stains and lowers Humanity. See [Tracker Types](./trackers_and_health.md#tracker-types).
