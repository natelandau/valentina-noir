---
icon: lucide/dices
---

# Rolling Dice

One of the more significant places where Valentina Noir differs from the canonical World of Darkness system is in how dice are rolled. Valentina rolls dice automatically based on the following system.

## Dice Rolling System

Dice in Valentina are rolled as a single pool of D10s with a set difficulty. The number of successes (dice above the difficulty) determine the outcome of the roll.

Once dice are rolled, all the dice are tallied and the number of success are added together with the following rules:

-   Any dice rolled at or above the difficulty count as a success.
-   Any dice rolled below the difficulty count as a failure.
-   Rolled ones count as `-1` success
-   Rolled tens count as `2` successes

There are four possible outcomes to a roll:

-   **Critical Success** - The number of successes is greater than the number of dice in the pool.
-   **Success** - The number of sucsuccessful dice after tallying.
-   **Failure** - There are no sucsuccessful dice after tallying.
-   **Botch** - The tally is negative.

## Examples

| Difficulty | Roll | Outcome | Tally |
| :-: | --- | --- | --- |
| **6** | :one: :five: :seven: | Failure | :one: and :seven: cancel each other out leaving :five: as the only die which is below the difficulty |
| **6** | :one: :five: :keycap_ten: | One Success | :keycap_ten: counts as `2` successes. The :one: removes one of those successes leaving `1` success |
| **8** | :two: :five: :four: :five: :nine: | One Success | A single :nine: is above the difficulty |
| **6** | :six: :four: :keycap_ten: :keycap_ten: | Critical Success | Each :keycap_ten: counts as `2` successes and the :six: is above the difficulty, so there are `4` successes which is above the size of the pool. |
| **7** | :seven: :one: :two: :three: | Failure | The :one: effectively cancels the single ssuccessful :seven: |
| **6** | :six: :one: :five: :one: | Botch | One of the :one:s cancels the :six: leaving a tally of `-1` |
| **6** | :two: :eight: :five: :six: :nine: :four: | Three Successes | Three dice are above the difficulty |

## Quick Rolls

Users are able to save combinations of traits and roll them with a single click. For example a quickroll of "Shoot" would be associated with the traits of `Firearms` and `Dexterity`. The user would then select the character they wanted to roll for and number of dice needed will be automatically calculated.
