"""Test the tracker service."""

import pytest

from tests.fixtures import global_trait
from vapi.constants import CharacterClass, GameVersion, TrackerAction
from vapi.db.sql_models.character import Character, CharacterHealth, CharacterTrait
from vapi.db.sql_models.character_sheet import Trait
from vapi.domain.controllers.character_health.dto import HealthStateSet
from vapi.domain.controllers.character_trait.dto import (
    CounterTrackerResponse,
    StainsTrackerResponse,
    TrackerActionRequest,
    TrackerStateSet,
    build_tracker_response,
)
from vapi.domain.services import CharacterTraitService, TrackerService
from vapi.lib.exceptions import NotFoundError, ValidationError

pytestmark = pytest.mark.anyio


async def _character_trait(character: Character, name: str) -> CharacterTrait | None:
    return await CharacterTrait.filter(
        character_id=character.id, trait__name=name, is_archived=False
    ).first()


async def _health(character: Character) -> CharacterHealth:
    return await CharacterHealth.get(character_id=character.id)


async def test_spend_willpower_v4(character_factory, character_trait_factory) -> None:
    """Verify spending V4 Willpower lowers current and records the audit."""
    # Given a V4 character with Willpower 5
    character = await character_factory(game_version=GameVersion.V4)
    ct = await character_trait_factory(
        character=character, trait=await global_trait("Willpower"), value=5
    )
    svc = TrackerService()

    # When spending 2
    result = await svc.apply_trait_action(
        character=character,
        character_trait=ct,
        data=TrackerActionRequest(action=TrackerAction.SPEND, amount=2),
    )

    # Then current is 3, the row stores 2 spent, and the audit names the spend
    await ct.refresh_from_db()
    assert result == CounterTrackerResponse(size=5, current=3)
    assert ct.tracker_spent == 2
    assert svc.audit_description == f"Spent 2 Willpower for character '{character.name}'"
    assert svc.audit_changes == {"tracker_spent": {"old": 0, "new": 2}}


async def test_spend_v5_willpower(character_factory, character_trait_factory) -> None:
    """Verify V5 Willpower is a counter that spends like V4 Willpower."""
    # Given a V5 character with Willpower 4
    character = await character_factory(game_version=GameVersion.V5)
    ct = await character_trait_factory(
        character=character, trait=await global_trait("Willpower"), value=4
    )

    # When spending 2
    result = await TrackerService().apply_trait_action(
        character=character,
        character_trait=ct,
        data=TrackerActionRequest(action=TrackerAction.SPEND, amount=2),
    )

    # Then current is 2 and the row stores 2 spent
    await ct.refresh_from_db()
    assert result == CounterTrackerResponse(size=4, current=2)
    assert ct.tracker_spent == 2


async def test_stains_overflow_kept_without_willpower_damage(
    character_factory, character_trait_factory
) -> None:
    """Verify stains beyond capacity are kept and leave Willpower untouched."""
    # Given a V5 vampire with Humanity 8 (capacity 2) and Willpower 4
    character = await character_factory(
        game_version=GameVersion.V5, character_class=CharacterClass.VAMPIRE
    )
    humanity = await character_trait_factory(
        character=character, trait=await global_trait("Humanity"), value=8
    )
    willpower = await character_trait_factory(
        character=character, trait=await global_trait("Willpower"), value=4
    )
    svc = TrackerService()

    # When adding 3 stains
    result = await svc.apply_trait_action(
        character=character,
        character_trait=humanity,
        data=TrackerActionRequest(action=TrackerAction.ADD_STAIN, amount=3),
    )

    # Then 3 stains record and Willpower is unspent
    await willpower.refresh_from_db()
    assert result == StainsTrackerResponse(humanity=8, stain_capacity=2, stains=3)
    assert willpower.tracker_spent == 0
    assert svc.audit_description == (f"Added 3 stains to Humanity for character '{character.name}'")


@pytest.mark.parametrize(
    ("game_version", "character_class"),
    [
        (GameVersion.V5, CharacterClass.MORTAL),
        (GameVersion.V5, CharacterClass.GHOUL),
        (GameVersion.V5, CharacterClass.HUNTER),
        (GameVersion.V4, CharacterClass.VAMPIRE),
        (GameVersion.V4, CharacterClass.MORTAL),
    ],
)
async def test_humanity_is_counter_except_v5_vampire(
    character_factory, character_trait_factory, game_version, character_class
) -> None:
    """Verify Humanity spends like Willpower for every character but a V5 vampire."""
    # Given a character with Humanity 7
    character = await character_factory(game_version=game_version, character_class=character_class)
    humanity = await character_trait_factory(
        character=character, trait=await global_trait("Humanity"), value=7
    )

    # When spending 1 Humanity
    result = await TrackerService().apply_trait_action(
        character=character,
        character_trait=humanity,
        data=TrackerActionRequest(action=TrackerAction.SPEND),
    )

    # Then Humanity is a counter with 6 remaining
    assert result == CounterTrackerResponse(size=7, current=6)


async def test_add_stain_rejected_on_humanity_counter(
    character_factory, character_trait_factory
) -> None:
    """Verify a stains action is refused on a non-vampire's Humanity counter."""
    # Given a V5 mortal with Humanity 7
    character = await character_factory(game_version=GameVersion.V5)
    humanity = await character_trait_factory(
        character=character, trait=await global_trait("Humanity"), value=7
    )

    # When adding a stain
    # Then the action is rejected
    with pytest.raises(ValidationError, match="add_stain"):
        await TrackerService().apply_trait_action(
            character=character,
            character_trait=humanity,
            data=TrackerActionRequest(action=TrackerAction.ADD_STAIN),
        )


async def test_reset_health(character_factory, character_health_factory) -> None:
    """Verify reset clears every health mark."""
    # Given a V5 character with damaged health
    character = await character_factory(game_version=GameVersion.V5, health=False)
    await character_health_factory(character=character, size=3, damage=3)
    svc = TrackerService()

    # When resetting health
    result = await svc.apply_health_action(
        character=character, data=TrackerActionRequest(action=TrackerAction.RESET)
    )

    # Then no damage remains
    health = await _health(character)
    assert result.damage == 0
    assert health.damage == 0
    assert svc.audit_description == f"Reset Health for character '{character.name}'"
    assert svc.audit_changes == {"damage": {"old": 3, "new": 0}}


async def test_take_health_damage_audit(character_factory) -> None:
    """Verify health damage writes the audit description."""
    # Given a V5 character with full health
    character = await character_factory(game_version=GameVersion.V5)
    svc = TrackerService()

    # When taking 2 damage
    result = await svc.apply_health_action(
        character=character,
        data=TrackerActionRequest(action=TrackerAction.DAMAGE, amount=2),
    )

    # Then the damage is stored and the audit names it
    assert result.damage == 2
    assert svc.audit_description == f"Took 2 damage to Health for character '{character.name}'"


async def test_set_state_rejects_inapplicable_field(
    character_factory, character_trait_factory
) -> None:
    """Verify a counter state body may not carry stains."""
    # Given a V4 Willpower counter
    character = await character_factory(game_version=GameVersion.V4)
    ct = await character_trait_factory(
        character=character, trait=await global_trait("Willpower"), value=5
    )

    # When setting a state with a stains field
    # Then it raises a validation error
    with pytest.raises(ValidationError, match="stains"):
        await TrackerService().set_trait_state(
            character=character,
            character_trait=ct,
            data=TrackerStateSet(current=3, stains=1),
        )


async def test_set_state_rejects_inapplicable_zero_field(
    character_factory, character_trait_factory
) -> None:
    """Verify an inapplicable state field is rejected even when it is 0."""
    # Given a V5 vampire's Humanity stains tracker
    character = await character_factory(
        game_version=GameVersion.V5, character_class=CharacterClass.VAMPIRE
    )
    ct = await character_trait_factory(
        character=character, trait=await global_trait("Humanity"), value=7
    )

    # When setting a state with current 0
    # Then it raises a validation error
    with pytest.raises(ValidationError, match="current"):
        await TrackerService().set_trait_state(
            character=character,
            character_trait=ct,
            data=TrackerStateSet(current=0, stains=1),
        )


async def test_unrelated_trait_save_skips_sync(character_factory, character_trait_factory) -> None:
    """Verify saving a trait that feeds nothing derived does not run the sync."""
    # Given a V5 character with only an ability trait and no Willpower
    character = await character_factory(game_version=GameVersion.V5)
    ability = await Trait.filter(
        sheet_section__name="Abilities", is_archived=False, custom_for_character_id=None
    ).first()
    ct = await character_trait_factory(character=character, trait=ability, value=2)

    # When the post-save hook runs for the ability
    await CharacterTraitService().after_save(ct, character)

    # Then no Willpower row is created
    assert await _character_trait(character, "Willpower") is None


async def test_bulk_after_save_syncs(character_factory, character_trait_factory) -> None:
    """Verify sync_all recomputes derived values whatever trait is passed."""
    # Given a V5 character with Composure 2 and an ability
    character = await character_factory(game_version=GameVersion.V5)
    await character_trait_factory(
        character=character, trait=await global_trait("Composure"), value=2
    )
    ability = await Trait.filter(
        sheet_section__name="Abilities", is_archived=False, custom_for_character_id=None
    ).first()
    ct = await character_trait_factory(character=character, trait=ability, value=2)

    # When the post-save hook runs for the ability with sync_all
    await CharacterTraitService().after_save(ct, character, sync_all=True)

    # Then Willpower follows Composure
    willpower = await _character_trait(character, "Willpower")
    assert willpower is not None
    assert willpower.value == 2


async def test_set_state_counter(character_factory, character_trait_factory) -> None:
    """Verify setting a counter state stores the spent amount."""
    # Given a V4 Willpower counter of 5
    character = await character_factory(game_version=GameVersion.V4)
    ct = await character_trait_factory(
        character=character, trait=await global_trait("Willpower"), value=5
    )

    # When setting current to 2
    result = await TrackerService().set_trait_state(
        character=character, character_trait=ct, data=TrackerStateSet(current=2)
    )

    # Then 3 are spent
    await ct.refresh_from_db()
    assert result == CounterTrackerResponse(size=5, current=2)
    assert ct.tracker_spent == 3


async def test_set_health_rejects_marks_over_size(character_factory) -> None:
    """Verify a health state with more damage than boxes is rejected."""
    # Given a V5 character with no Stamina (size 3)
    character = await character_factory(game_version=GameVersion.V5)

    # When setting 4 damage
    # Then it raises a validation error
    with pytest.raises(ValidationError, match="damage"):
        await TrackerService().set_health_state(character=character, data=HealthStateSet(damage=4))


async def test_set_health_extra_levels_resizes(character_factory) -> None:
    """Verify extra levels grow the stored health size."""
    # Given a V4 character
    character = await character_factory(game_version=GameVersion.V4)

    # When setting 1 extra level and 2 damage
    result = await TrackerService().set_health_state(
        character=character, data=HealthStateSet(extra_levels=1, damage=2)
    )

    # Then the track has 8 boxes and 2 damage
    health = await _health(character)
    assert health.size == 8
    assert health.damage == 2
    assert result.size == 8


async def test_lowering_willpower_clamps_spent(character_factory, character_trait_factory) -> None:
    """Verify lowering a counter's value trims spent marks to the new size."""
    # Given a V4 Willpower lowered from 5 to 2 while 4 were spent
    character = await character_factory(game_version=GameVersion.V4)
    ct = await character_trait_factory(
        character=character, trait=await global_trait("Willpower"), value=2, tracker_spent=4
    )

    # When the trait service runs its post-save hook
    await CharacterTraitService().after_save(ct, character)

    # Then spent is clamped to 2
    await ct.refresh_from_db()
    assert ct.tracker_spent == 2


async def test_raising_humanity_keeps_stains(character_factory, character_trait_factory) -> None:
    """Verify raising Humanity keeps stains and shrinks the capacity."""
    # Given a V5 vampire's Humanity raised from 7 to 8 with 3 stains
    character = await character_factory(
        game_version=GameVersion.V5, character_class=CharacterClass.VAMPIRE
    )
    ct = await character_trait_factory(
        character=character, trait=await global_trait("Humanity"), value=8, tracker_stains=3
    )

    # When the post-save hook runs and the tracker is rebuilt
    await CharacterTraitService().after_save(ct, character)
    await ct.refresh_from_db()
    result = build_tracker_response(ct, character=character)

    # Then the stains remain and the capacity is 2
    assert ct.tracker_stains == 3
    assert result == StainsTrackerResponse(humanity=8, stain_capacity=2, stains=3)


async def test_stamina_change_resizes_v5_health(
    character_factory, character_trait_factory, character_health_factory
) -> None:
    """Verify Stamina changes resize V5 health and clamp its damage."""
    # Given a V5 character whose Stamina dropped from 3 to 1 with a full track of 6
    character = await character_factory(game_version=GameVersion.V5, health=False)
    await character_health_factory(character=character, size=6, damage=6)
    stamina = await character_trait_factory(
        character=character, trait=await global_trait("Stamina"), value=1
    )

    # When the post-save hook runs for Stamina
    await CharacterTraitService().after_save(stamina, character)

    # Then health has 4 boxes and 4 damage
    health = await _health(character)
    assert health.size == 4
    assert health.damage == 4


async def test_composure_change_syncs_v5_willpower(
    character_factory, character_trait_factory
) -> None:
    """Verify V5 Willpower follows Composure + Resolve."""
    # Given a V5 character with Composure 2, Resolve 3, and Willpower 1
    character = await character_factory(game_version=GameVersion.V5)
    composure = await character_trait_factory(
        character=character, trait=await global_trait("Composure"), value=2
    )
    await character_trait_factory(character=character, trait=await global_trait("Resolve"), value=3)
    willpower = await character_trait_factory(
        character=character, trait=await global_trait("Willpower"), value=1
    )

    # When the post-save hook runs for Composure
    await CharacterTraitService().after_save(composure, character)

    # Then Willpower is 5
    await willpower.refresh_from_db()
    assert willpower.value == 5


async def test_v5_willpower_clamped_when_attributes_drop(
    character_factory, character_trait_factory
) -> None:
    """Verify a lowered derived Willpower trims its spent points."""
    # Given a V5 Willpower 5 fully spent, with Composure 1 and Resolve 1
    character = await character_factory(game_version=GameVersion.V5)
    await character_trait_factory(
        character=character, trait=await global_trait("Composure"), value=1
    )
    await character_trait_factory(character=character, trait=await global_trait("Resolve"), value=1)
    willpower = await character_trait_factory(
        character=character,
        trait=await global_trait("Willpower"),
        value=5,
        tracker_spent=5,
    )

    # When syncing the character
    await TrackerService().sync_character(character)

    # Then Willpower is 2 and fully spent
    await willpower.refresh_from_db()
    assert willpower.value == 2
    assert willpower.tracker_spent == 2


async def test_v5_willpower_created_when_missing(
    character_factory, character_trait_factory
) -> None:
    """Verify sync creates a missing V5 Willpower at Composure + Resolve."""
    # Given a V5 character with Composure 2 and Resolve 3 and no Willpower
    character = await character_factory(game_version=GameVersion.V5)
    for name, value in (("Composure", 2), ("Resolve", 3)):
        await character_trait_factory(
            character=character, trait=await global_trait(name), value=value
        )

    # When syncing the character
    await TrackerService().sync_character(character)

    # Then a Willpower row exists at the sum
    willpower = await _character_trait(character, "Willpower")
    assert willpower is not None
    assert willpower.value == 5


async def test_v4_sync_leaves_willpower_alone(character_factory, character_trait_factory) -> None:
    """Verify V4 sync neither creates nor changes Willpower."""
    # Given a V4 character with Willpower 6
    character = await character_factory(game_version=GameVersion.V4)
    willpower = await character_trait_factory(
        character=character, trait=await global_trait("Willpower"), value=6
    )

    # When syncing the character
    await TrackerService().sync_character(character)

    # Then Willpower is still 6 and V4 health is 7 boxes
    await willpower.refresh_from_db()
    health = await _health(character)
    assert willpower.value == 6
    assert health.size == 7


async def test_initialize_character_creates_health_once(character_factory) -> None:
    """Verify initialize creates a missing health row and reuses an existing one."""
    # Given a V5 character without a health row
    character = await character_factory(game_version=GameVersion.V5, health=False)
    svc = TrackerService()

    # When initializing twice, the second time with a health state
    await svc.initialize_character(character=character)
    health = await svc.initialize_character(character=character, health=HealthStateSet(damage=1))

    # Then one health row exists with the applied state
    assert await CharacterHealth.filter(character_id=character.id).count() == 1
    assert health.size == 3
    assert health.damage == 1


async def test_action_never_changes_xp(
    company_factory,
    character_factory,
    character_trait_factory,
    campaign_factory,
    user_factory,
    campaign_experience_factory,
) -> None:
    """Verify tracker actions leave XP and the trait value untouched."""
    # Given a V4 player with 10 XP and Willpower 5
    company = await company_factory()
    user = await user_factory(company=company)
    campaign = await campaign_factory(company=company)
    character = await character_factory(
        game_version=GameVersion.V4, company=company, user_player=user, campaign=campaign
    )
    experience = await campaign_experience_factory(
        user=user, campaign=campaign, xp_current=10, xp_total=10
    )
    ct = await character_trait_factory(
        character=character, trait=await global_trait("Willpower"), value=5
    )

    # When spending 1 Willpower
    await TrackerService().apply_trait_action(
        character=character,
        character_trait=ct,
        data=TrackerActionRequest(action=TrackerAction.SPEND),
    )

    # Then XP and value are unchanged
    await experience.refresh_from_db()
    await ct.refresh_from_db()
    assert experience.xp_current == 10
    assert experience.xp_total == 10
    assert ct.value == 5


async def test_trait_action_reads_fresh_marks(character_factory, character_trait_factory) -> None:
    """Verify an action applies to the stored marks, not to a stale instance."""
    # Given a V4 character with Willpower 5 loaded twice before any spend
    character = await character_factory(game_version=GameVersion.V4)
    ct = await character_trait_factory(
        character=character, trait=await global_trait("Willpower"), value=5
    )
    first = await CharacterTrait.get(id=ct.id).prefetch_related("trait")
    second = await CharacterTrait.get(id=ct.id).prefetch_related("trait")
    spend = TrackerActionRequest(action=TrackerAction.SPEND, amount=1)

    # When spending 1 through each instance
    await TrackerService().apply_trait_action(
        character=character, character_trait=first, data=spend
    )
    result = await TrackerService().apply_trait_action(
        character=character, character_trait=second, data=spend
    )

    # Then both spends count
    await ct.refresh_from_db()
    assert ct.tracker_spent == 2
    assert second.tracker_spent == 2
    assert result == CounterTrackerResponse(size=5, current=3)


async def test_health_action_without_row_not_found(character_factory) -> None:
    """Verify a health action returns not found when the character has no health row."""
    # Given a V5 character without a health row
    character = await character_factory(game_version=GameVersion.V5, health=False)
    data = TrackerActionRequest(action=TrackerAction.DAMAGE)

    # When applying damage
    with pytest.raises(NotFoundError) as exc_info:
        await TrackerService().apply_health_action(character=character, data=data)

    # Then the request is refused and no row is created
    assert exc_info.value.detail == "Character health not found"
    assert not await CharacterHealth.filter(character_id=character.id).exists()


async def test_set_health_without_row_not_found(character_factory) -> None:
    """Verify setting health returns not found when the character has no health row."""
    # Given a V5 character without a health row
    character = await character_factory(game_version=GameVersion.V5, health=False)

    # When setting the health state
    with pytest.raises(NotFoundError) as exc_info:
        await TrackerService().set_health_state(character=character, data=HealthStateSet(damage=1))

    # Then the request is refused and no row is created
    assert exc_info.value.detail == "Character health not found"
    assert not await CharacterHealth.filter(character_id=character.id).exists()
