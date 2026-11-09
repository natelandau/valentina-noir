---
icon: lucide/dices
---

# Rolling Dice

Valentina Noir uses a customized dice rolling system that differs from canonical World of Darkness.

## Dice Rolling System

Roll a pool of D10s against a set difficulty. The number of successes determines the outcome.

### Dice Modifiers

A dice roll can carry a `dice_modifier`, a whole number from -100 to 100. A positive modifier adds dice to the pool, and a negative modifier removes dice from it. The pool after the modifier must contain 0 to 100 dice, or the API rejects the roll. The modifier does not change desperation dice. The roll stores `num_dice` and `dice_modifier` as two separate fields.

### Success Calculation

Tally all dice using these rules:

-   Dice at or above difficulty: `+1` success
-   Dice below difficulty: `0` successes
-   Rolled ones: `-1` success
-   Rolled tens: `+2` successes

### Possible Outcomes

| Outcome | Condition |
| --- | --- |
| **Critical Success** | Successes exceed the number of dice rolled, including dice from the modifier and desperation dice |
| **Success** | Positive number of successes after tallying |
| **Failure** | Zero successes after tallying |
| **Botch** | Negative tally |

## Examples

| Difficulty | Roll | Outcome | Explanation |
| :-: | --- | --- | --- |
| **6** | :one: :five: :seven: | Failure | :one: and :seven: cancel each other. :five: is below difficulty. |
| **6** | :one: :five: :keycap_ten: | One Success | :keycap_ten: counts as `2` successes. :one: removes one success, leaving `1`. |
| **8** | :two: :five: :four: :five: :nine: | One Success | Single :nine: exceeds difficulty. |
| **6** | :six: :four: :keycap_ten: :keycap_ten: | Critical Success | Two :keycap_ten:s (`4` successes) + :six: (`1` success) = `5` successes (exceeds pool size of 4). |
| **7** | :seven: :one: :two: :three: | Failure | :one: cancels the successful :seven:. |
| **6** | :six: :one: :five: :one: | Botch | One :one: cancels :six:. Second :one: creates negative tally of `-1`. |
| **6** | :two: :eight: :five: :six: :nine: :four: | Three Successes | :eight:, :six:, and :nine: all exceed difficulty. |

## Quick Rolls

Users can save trait combinations for one-click rolling. For example, a "Shoot" quick roll combines `Firearms` and `Dexterity`. Select a character and the API sums the character's trait values to determine the dice pool. A dice modifier on the quick roll adjusts that pool.

See the [Quick Rolls](./quick_rolls.md) documentation for details on creating, managing, and executing quick rolls.
