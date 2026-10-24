"""Test the tracker service."""

import pytest

from vapi.constants import DamageType, GameVersion, TrackerAction
from vapi.db.sql_models.character import Character, CharacterHealth, CharacterTrait
from vapi.db.sql_models.character_sheet import Trait
from vapi.domain.controllers.character_health.dto import HealthStateSet
from vapi.domain.controllers.character_trait.dto import (
    CounterTrackerResponse,
    DamageTrackResponse,
    StainsTrackerResponse,
    TrackerActionRequest,
    TrackerStateSet,
    build_tracker_response,
)
from vapi.domain.services import CharacterTraitService, TrackerService
from vapi.lib.exceptions import NotFoundError, ValidationError

pytestmark = pytest.mark.anyio


async def _global_trait(name: str) -> Trait:
    return await Trait.get(name=name, custom_for_character_id=None, is_archived=False)


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
        character=character, trait=await _global_trait("Willpower"), value=5
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


async def test_damage_v5_willpower(character_factory, character_trait_factory) -> None:
    """Verify superficial damage marks the V5 Willpower track."""
    # Given a V5 character with Willpower 4
    character = await character_factory(game_version=GameVersion.V5)
    ct = await character_trait_factory(
        character=character, trait=await _global_trait("Willpower"), value=4
    )
    svc = TrackerService()

    # When taking 2 superficial damage
    result = await svc.apply_trait_action(
        character=character,
        character_trait=ct,
        data=TrackerActionRequest(
            action=TrackerAction.DAMAGE, amount=2, damage_type=DamageType.SUPERFICIAL
        ),
    )

    # Then two boxes are superficial
    await ct.refresh_from_db()
    assert isinstance(result, DamageTrackResponse)
    assert result.superficial == 2
    assert result.aggravated == 0
    assert ct.tracker_superficial == 2
    assert svc.audit_description == (
        f"Took 2 Superficial damage to Willpower for character '{character.name}'"
    )


async def test_stains_overflow_damages_willpower(
    character_factory, character_trait_factory
) -> None:
    """Verify stains beyond capacity deal aggravated damage to V5 Willpower."""
    # Given a V5 character with Humanity 8 (capacity 2) and Willpower 4
    character = await character_factory(game_version=GameVersion.V5)
    humanity = await character_trait_factory(
        character=character, trait=await _global_trait("Humanity"), value=8
    )
    willpower = await character_trait_factory(
        character=character, trait=await _global_trait("Willpower"), value=4
    )
    svc = TrackerService()

    # When adding 3 stains
    result = await svc.apply_trait_action(
        character=character,
        character_trait=humanity,
        data=TrackerActionRequest(action=TrackerAction.ADD_STAIN, amount=3),
    )

    # Then 3 stains record, 1 overflows into aggravated Willpower damage
    await willpower.refresh_from_db()
    assert isinstance(result, StainsTrackerResponse)
    assert result.stains == 3
    assert result.is_impaired is True
    assert result.willpower_damage_applied == 1
    assert willpower.tracker_aggravated == 1
    assert "Willpower" in svc.audit_description


async def test_stains_overflow_without_willpower_row(
    character_factory, character_trait_factory
) -> None:
    """Verify stain overflow records stains when the character has no Willpower."""
    # Given a V5 character with Humanity 9 and no Willpower row
    character = await character_factory(game_version=GameVersion.V5)
    humanity = await character_trait_factory(
        character=character, trait=await _global_trait("Humanity"), value=9
    )

    # When adding 2 stains
    result = await TrackerService().apply_trait_action(
        character=character,
        character_trait=humanity,
        data=TrackerActionRequest(action=TrackerAction.ADD_STAIN, amount=2),
    )

    # Then the stains record and no Willpower damage is applied
    await humanity.refresh_from_db()
    assert isinstance(result, StainsTrackerResponse)
    assert humanity.tracker_stains == 2
    assert result.willpower_damage_applied == 0


async def test_reset_health(character_factory, character_health_factory) -> None:
    """Verify reset clears every health mark."""
    # Given a V5 character with damaged health
    character = await character_factory(game_version=GameVersion.V5, health=False)
    await character_health_factory(character=character, size=3, superficial=2, aggravated=1)
    svc = TrackerService()

    # When resetting health
    result = await svc.apply_health_action(
        character=character, data=TrackerActionRequest(action=TrackerAction.RESET)
    )

    # Then no marks remain
    health = await _health(character)
    assert result.superficial == 0
    assert result.aggravated == 0
    assert health.superficial == 0
    assert health.aggravated == 0
    assert svc.audit_description == f"Reset Health for character '{character.name}'"
    assert svc.audit_changes == {
        "superficial": {"old": 2, "new": 0},
        "aggravated": {"old": 1, "new": 0},
    }


async def test_take_health_damage_audit(character_factory) -> None:
    """Verify health damage writes the audit description."""
    # Given a V5 character with full health
    character = await character_factory(game_version=GameVersion.V5)
    svc = TrackerService()

    # When taking 2 superficial damage
    await svc.apply_health_action(
        character=character,
        data=TrackerActionRequest(
            action=TrackerAction.DAMAGE, amount=2, damage_type=DamageType.SUPERFICIAL
        ),
    )

    # Then the audit names the damage
    assert svc.audit_description == (
        f"Took 2 Superficial damage to Health for character '{character.name}'"
    )


async def test_set_state_rejects_inapplicable_field(
    character_factory, character_trait_factory
) -> None:
    """Verify a counter state body may not carry damage fields."""
    # Given a V4 Willpower counter
    character = await character_factory(game_version=GameVersion.V4)
    ct = await character_trait_factory(
        character=character, trait=await _global_trait("Willpower"), value=5
    )

    # When setting a state with a superficial field
    # Then it raises a validation error
    with pytest.raises(ValidationError, match="superficial"):
        await TrackerService().set_trait_state(
            character=character,
            character_trait=ct,
            data=TrackerStateSet(current=3, superficial=1),
        )


async def test_set_state_rejects_inapplicable_zero_field(
    character_factory, character_trait_factory
) -> None:
    """Verify an inapplicable state field is rejected even when it is 0."""
    # Given a V5 Willpower damage track
    character = await character_factory(game_version=GameVersion.V5)
    ct = await character_trait_factory(
        character=character, trait=await _global_trait("Willpower"), value=5
    )

    # When setting a state with stains 0
    # Then it raises a validation error
    with pytest.raises(ValidationError, match="stains"):
        await TrackerService().set_trait_state(
            character=character,
            character_trait=ct,
            data=TrackerStateSet(superficial=1, stains=0),
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
        character=character, trait=await _global_trait("Composure"), value=2
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


async def test_stains_overflow_skips_save_when_willpower_full(
    character_factory, character_trait_factory
) -> None:
    """Verify overflow onto an all-aggravated Willpower changes nothing."""
    # Given a V5 Humanity 10 and a Willpower 2 that is fully aggravated
    character = await character_factory(game_version=GameVersion.V5)
    humanity = await character_trait_factory(
        character=character, trait=await _global_trait("Humanity"), value=10
    )
    willpower = await character_trait_factory(
        character=character,
        trait=await _global_trait("Willpower"),
        value=2,
        tracker_aggravated=2,
    )
    modified = willpower.date_modified

    # When adding a stain
    result = await TrackerService().apply_trait_action(
        character=character,
        character_trait=humanity,
        data=TrackerActionRequest(action=TrackerAction.ADD_STAIN),
    )

    # Then no damage is applied and Willpower is not rewritten
    await willpower.refresh_from_db()
    assert isinstance(result, StainsTrackerResponse)
    assert result.willpower_damage_applied == 0
    assert willpower.date_modified == modified


async def test_set_state_counter(character_factory, character_trait_factory) -> None:
    """Verify setting a counter state stores the spent amount."""
    # Given a V4 Willpower counter of 5
    character = await character_factory(game_version=GameVersion.V4)
    ct = await character_trait_factory(
        character=character, trait=await _global_trait("Willpower"), value=5
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
    """Verify a health state with more marks than boxes is rejected."""
    # Given a V5 character with no Stamina (size 3)
    character = await character_factory(game_version=GameVersion.V5)

    # When setting 3 superficial and 2 aggravated
    # Then it raises a validation error
    with pytest.raises(ValidationError):
        await TrackerService().set_health_state(
            character=character, data=HealthStateSet(superficial=3, aggravated=2)
        )


async def test_set_health_rejects_inapplicable_field(character_factory) -> None:
    """Verify V5 health rejects V4 damage fields."""
    # Given a V5 character
    character = await character_factory(game_version=GameVersion.V5)

    # When setting bashing damage
    # Then it raises a validation error
    with pytest.raises(ValidationError, match="bashing"):
        await TrackerService().set_health_state(character=character, data=HealthStateSet(bashing=1))


async def test_set_health_extra_levels_resizes(character_factory) -> None:
    """Verify extra levels grow the stored health size."""
    # Given a V4 character
    character = await character_factory(game_version=GameVersion.V4)

    # When setting 1 extra level and 2 lethal
    result = await TrackerService().set_health_state(
        character=character, data=HealthStateSet(extra_levels=1, lethal=2)
    )

    # Then the track has 8 boxes and 2 lethal
    health = await _health(character)
    assert health.size == 8
    assert health.lethal == 2
    assert result.size == 8


async def test_lowering_willpower_clamps_spent(character_factory, character_trait_factory) -> None:
    """Verify lowering a counter's value trims spent marks to the new size."""
    # Given a V4 Willpower lowered from 5 to 2 while 4 were spent
    character = await character_factory(game_version=GameVersion.V4)
    ct = await character_trait_factory(
        character=character, trait=await _global_trait("Willpower"), value=2, tracker_spent=4
    )

    # When the trait service runs its post-save hook
    await CharacterTraitService().after_save(ct, character)

    # Then spent is clamped to 2
    await ct.refresh_from_db()
    assert ct.tracker_spent == 2


async def test_raising_humanity_recomputes_impaired(
    character_factory, character_trait_factory
) -> None:
    """Verify raising Humanity keeps stains and shrinks capacity so impairment follows."""
    # Given a V5 Humanity raised from 7 to 8 with 3 stains
    character = await character_factory(game_version=GameVersion.V5)
    ct = await character_trait_factory(
        character=character, trait=await _global_trait("Humanity"), value=8, tracker_stains=3
    )

    # When the post-save hook runs and the tracker is rebuilt
    await CharacterTraitService().after_save(ct, character)
    await ct.refresh_from_db()
    result = build_tracker_response(ct, game_version=character.game_version)

    # Then the stains remain and the character is impaired
    assert ct.tracker_stains == 3
    assert isinstance(result, StainsTrackerResponse)
    assert result.stain_capacity == 2
    assert result.is_impaired is True


async def test_stamina_change_resizes_v5_health(
    character_factory, character_trait_factory, character_health_factory
) -> None:
    """Verify Stamina changes resize V5 health and clamp its marks."""
    # Given a V5 character whose Stamina dropped from 3 to 1 with 6 full superficial boxes
    character = await character_factory(game_version=GameVersion.V5, health=False)
    await character_health_factory(character=character, size=6, superficial=6)
    stamina = await character_trait_factory(
        character=character, trait=await _global_trait("Stamina"), value=1
    )

    # When the post-save hook runs for Stamina
    await CharacterTraitService().after_save(stamina, character)

    # Then health has 4 boxes and 4 superficial
    health = await _health(character)
    assert health.size == 4
    assert health.superficial == 4


async def test_composure_change_syncs_v5_willpower(
    character_factory, character_trait_factory
) -> None:
    """Verify V5 Willpower follows Composure + Resolve."""
    # Given a V5 character with Composure 2, Resolve 3, and Willpower 1
    character = await character_factory(game_version=GameVersion.V5)
    composure = await character_trait_factory(
        character=character, trait=await _global_trait("Composure"), value=2
    )
    await character_trait_factory(
        character=character, trait=await _global_trait("Resolve"), value=3
    )
    willpower = await character_trait_factory(
        character=character, trait=await _global_trait("Willpower"), value=1
    )

    # When the post-save hook runs for Composure
    await CharacterTraitService().after_save(composure, character)

    # Then Willpower is 5
    await willpower.refresh_from_db()
    assert willpower.value == 5


async def test_v5_willpower_clamped_when_attributes_drop(
    character_factory, character_trait_factory
) -> None:
    """Verify a lowered derived Willpower trims its damage marks."""
    # Given a V5 Willpower 5 fully superficial, with Composure 1 and Resolve 1
    character = await character_factory(game_version=GameVersion.V5)
    await character_trait_factory(
        character=character, trait=await _global_trait("Composure"), value=1
    )
    await character_trait_factory(
        character=character, trait=await _global_trait("Resolve"), value=1
    )
    willpower = await character_trait_factory(
        character=character,
        trait=await _global_trait("Willpower"),
        value=5,
        tracker_superficial=4,
        tracker_aggravated=1,
    )

    # When syncing the character
    await TrackerService().sync_character(character)

    # Then Willpower is 2 with superficial trimmed first
    await willpower.refresh_from_db()
    assert willpower.value == 2
    assert willpower.tracker_superficial == 1
    assert willpower.tracker_aggravated == 1


async def test_v5_willpower_created_when_missing(
    character_factory, character_trait_factory
) -> None:
    """Verify sync creates a missing V5 Willpower at Composure + Resolve."""
    # Given a V5 character with Composure 2 and Resolve 3 and no Willpower
    character = await character_factory(game_version=GameVersion.V5)
    for name, value in (("Composure", 2), ("Resolve", 3)):
        await character_trait_factory(
            character=character, trait=await _global_trait(name), value=value
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
        character=character, trait=await _global_trait("Willpower"), value=6
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
    health = await svc.initialize_character(
        character=character, health=HealthStateSet(superficial=1)
    )

    # Then one health row exists with the applied state
    assert await CharacterHealth.filter(character_id=character.id).count() == 1
    assert health.size == 3
    assert health.superficial == 1


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
        character=character, trait=await _global_trait("Willpower"), value=5
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
        character=character, trait=await _global_trait("Willpower"), value=5
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
    data = TrackerActionRequest(action=TrackerAction.DAMAGE, damage_type=DamageType.SUPERFICIAL)

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
        await TrackerService().set_health_state(
            character=character, data=HealthStateSet(superficial=1)
        )

    # Then the request is refused and no row is created
    assert exc_info.value.detail == "Character health not found"
    assert not await CharacterHealth.filter(character_id=character.id).exists()
