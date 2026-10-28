"""In-play tracker and character health services."""

from typing import Any

from tortoise.transactions import in_transaction

from vapi.constants import GameVersion, TrackerAction, TrackerType
from vapi.db.sql_models.character import Character, CharacterHealth, CharacterTrait
from vapi.db.sql_models.character_sheet import Trait
from vapi.domain.controllers.character_health.dto import HealthResponse, HealthStateSet
from vapi.domain.controllers.character_trait.dto import (
    TrackerActionRequest,
    TrackerResponse,
    TrackerStateSet,
    tracker_response_for,
    tracker_type_for,
)
from vapi.lib.exceptions import NotFoundError, ValidationError
from vapi.lib.tracker_rules import (
    HUMANITY_BOXES,
    apply_counter,
    apply_damage,
    apply_stains,
    health_size,
    validate_action,
)

V5_WILLPOWER_SOURCES = ("Composure", "Resolve")
HEALTH_SIZE_SOURCE = "Stamina"
WILLPOWER_TRAIT_NAME = "Willpower"
_SYNC_TRIGGER_TRAIT_NAMES = frozenset(
    {*V5_WILLPOWER_SOURCES, HEALTH_SIZE_SOURCE, WILLPOWER_TRAIT_NAME}
)

_TRACKER_FIELDS: dict[TrackerType, str] = {
    TrackerType.COUNTER: "current",
    TrackerType.STAINS: "stains",
}
_TRAIT_MARK_FIELDS = ("tracker_spent", "tracker_stains")


def is_derived_trait(*, trait: Trait, game_version: GameVersion) -> bool:
    """Return whether the trait's value is computed rather than purchased.

    Only the global Willpower trait on V5 is derived, from Composure + Resolve.
    """
    return (
        game_version == GameVersion.V5
        and trait.custom_for_character_id is None  # ty:ignore[unresolved-attribute]
        and trait.name == WILLPOWER_TRAIT_NAME
    )


async def load_trait(character_trait: CharacterTrait) -> Trait:
    """Return the trait of a character trait, loading it when the relation is not fetched."""
    trait = character_trait.trait
    if isinstance(trait, Trait):
        return trait
    trait = await Trait.get(id=character_trait.trait_id)
    # Cache on the instance so later callers in the same save path skip the query
    character_trait.trait = trait
    return trait


def _invalid(*, field: str, msg: str) -> ValidationError:
    return ValidationError(detail=msg, invalid_parameters=[{"field": field, "message": msg}])


def _changes(before: dict[str, Any], obj: object) -> dict[str, dict[str, Any]]:
    """Return `{"field": {"old": x, "new": y}}` for every field of `before` that changed on `obj`."""
    return {
        field: {"old": old, "new": getattr(obj, field)}
        for field, old in before.items()
        if getattr(obj, field) != old
    }


def _snapshot(obj: object, fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: getattr(obj, field) for field in fields}


_ACTION_PHRASES: dict[TrackerAction, str] = {
    TrackerAction.SPEND: "Spent {amount}",
    TrackerAction.GAIN: "Gained {amount}",
    TrackerAction.DAMAGE: "Took {amount} damage to",
    TrackerAction.HEAL: "Healed {amount} damage on",
    TrackerAction.ADD_STAIN: "Added {amount} stains to",
    TrackerAction.REMOVE_STAIN: "Removed {amount} stains from",
    TrackerAction.RESET: "Reset",
}


def _action_phrase(*, action: TrackerAction, amount: int) -> str:
    """Return the verb phrase for an audit description, e.g. "Took 2 damage to"."""
    return _ACTION_PHRASES[action].format(amount=amount)


def _health_size(
    *, character: Character, extra_levels: int, sources: dict[str, CharacterTrait]
) -> int:
    """Return a character's health size from the Stamina among its derived sources."""
    stamina = sources.get(HEALTH_SIZE_SOURCE)
    return health_size(
        game_version=character.game_version,
        extra_levels=extra_levels,
        stamina=stamina.value if stamina else 0,
    )


def _set_trait_marks(
    *, character_trait: CharacterTrait, tracker_type: TrackerType, data: TrackerStateSet
) -> None:
    """Store a validated tracker state on a character trait.

    Raises:
        ValidationError: If a field does not apply, a required field is missing, or the state
            does not fit the tracker.
    """
    accepted = _TRACKER_FIELDS[tracker_type]
    for field, value in (("current", data.current), ("stains", data.stains)):
        if field != accepted and value is not None:
            msg = f"{field} does not apply to a {tracker_type.value} tracker. Accepted fields: {accepted}."
            raise _invalid(field=field, msg=msg)

    size = character_trait.value
    match tracker_type:
        case TrackerType.COUNTER:
            if data.current is None:
                msg = "current is required for a COUNTER tracker."
                raise _invalid(field="current", msg=msg)
            if data.current > size:
                msg = f"current must be at most {size}, got {data.current}."
                raise _invalid(field="current", msg=msg)
            character_trait.tracker_spent = size - data.current
        case TrackerType.STAINS:
            stains = data.stains or 0
            if stains > HUMANITY_BOXES:
                msg = f"stains must be at most {HUMANITY_BOXES}, got {stains}."
                raise _invalid(field="stains", msg=msg)
            character_trait.tracker_stains = stains


class TrackerService:
    """Apply in-play tracker rules and keep derived sizes in sync with trait values.

    Every write sets `audit_description` and `audit_changes` for the controller to copy
    onto the request state.
    """

    def __init__(self) -> None:
        self.audit_description: str = ""
        self.audit_changes: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    async def affects_derived_values(self, character_trait: CharacterTrait) -> bool:
        """Return whether a change to this trait can change V5 Willpower or Health.

        Lets the post-save hook skip `sync_character` for traits that feed nothing.
        """
        trait = await load_trait(character_trait)
        return trait.custom_for_character_id is None and trait.name in _SYNC_TRIGGER_TRAIT_NAMES  # ty:ignore[unresolved-attribute]

    async def _tracker_type(
        self, *, character_trait: CharacterTrait, character: Character
    ) -> tuple[Trait, TrackerType]:
        trait = await load_trait(character_trait)
        tracker_type = tracker_type_for(trait, character=character)
        if tracker_type is None:
            msg = f"Trait '{trait.name}' has no tracker for {character.game_version.value}."
            raise NotFoundError(detail=msg)
        return trait, tracker_type

    @staticmethod
    async def _derived_sources(character: Character) -> dict[str, CharacterTrait]:
        """Return the character's global source and Willpower traits, keyed by trait name."""
        names = [*V5_WILLPOWER_SOURCES, HEALTH_SIZE_SOURCE, WILLPOWER_TRAIT_NAME]
        rows = await CharacterTrait.filter(
            character_id=character.id,
            is_archived=False,
            trait__custom_for_character_id__isnull=True,
            trait__name__in=names,
        ).select_related("trait")
        return {ct.trait.name: ct for ct in rows}

    @staticmethod
    async def _lock_health(character: Character) -> CharacterHealth:
        """Lock and return the character's health row so concurrent writes serialize.

        Call inside a transaction.

        Raises:
            NotFoundError: If the character has no health row.
        """
        health = (
            await CharacterHealth.filter(character_id=character.id, is_archived=False)
            .select_for_update()
            .first()
        )
        if health is None:
            raise NotFoundError(detail="Character health not found")
        return health

    @staticmethod
    async def _lock_trait_marks(character_trait: CharacterTrait) -> None:
        """Lock the trait row and reload its value and marks onto ``character_trait``.

        Holding the lock until the transaction commits keeps two quick actions on the same
        tracker from both applying to the same starting state. Call inside a transaction.

        Raises:
            NotFoundError: If the character trait no longer exists.
        """
        locked = (
            await CharacterTrait.filter(id=character_trait.id)
            .select_for_update()
            .only("id", "value", *_TRAIT_MARK_FIELDS)
            .first()
        )
        if locked is None:
            raise NotFoundError(detail="Character trait not found")
        character_trait.value = locked.value
        for field in _TRAIT_MARK_FIELDS:
            setattr(character_trait, field, getattr(locked, field))

    # ------------------------------------------------------------------
    # Derived sync
    # ------------------------------------------------------------------

    async def initialize_character(
        self, *, character: Character, health: HealthStateSet | None = None
    ) -> CharacterHealth:
        """Create a character's health row if missing and bring derived values up to date.

        Call after a character's traits are created so Health and V5 Willpower are sized
        from them. Safe to call on a character that already has a health row.

        Args:
            character: The character to initialize.
            health: An optional starting health state to apply after sizing.

        Returns:
            The character's health row.
        """
        await CharacterHealth.get_or_create(
            character_id=character.id,
            defaults={
                "size": health_size(game_version=character.game_version, extra_levels=0, stamina=0)
            },
        )
        await self.sync_character(character)
        if health is not None:
            await self.set_health_state(character=character, data=health)
        return await CharacterHealth.get(character_id=character.id)

    async def sync_character(self, character: Character) -> None:
        """Recompute V5 Willpower and the health size from the character's current traits.

        Recomputes everything regardless of which trait changed, because bulk trait creation
        and deletes need a full recompute.
        """
        async with in_transaction():
            # Lock health before reading the sources so concurrent syncs for one character
            # serialize and each reads the values the previous one committed.
            health = (
                await CharacterHealth.filter(character_id=character.id).select_for_update().first()
            )
            sources = await self._derived_sources(character)
            if character.game_version == GameVersion.V5:
                await self._sync_v5_willpower(character=character, sources=sources)

            if health is None:
                return
            size = _health_size(
                character=character, extra_levels=health.extra_levels, sources=sources
            )
            damage = min(health.damage, size)
            if size == health.size and damage == health.damage:
                return
            health.size = size
            health.damage = damage
            await health.save(update_fields=["size", "damage", "date_modified"])

    async def _sync_v5_willpower(
        self, *, character: Character, sources: dict[str, CharacterTrait]
    ) -> None:
        value = sum(sources[name].value for name in V5_WILLPOWER_SOURCES if name in sources)
        willpower = sources.get(WILLPOWER_TRAIT_NAME)

        if willpower is None:
            trait = await Trait.get_or_none(
                name=WILLPOWER_TRAIT_NAME, custom_for_character_id__isnull=True, is_archived=False
            )
            if trait is None:
                return
            await CharacterTrait.create(character=character, trait=trait, value=value)
            return

        if willpower.value == value:
            return
        willpower.value = value
        await willpower.save(update_fields=["value", "date_modified"])
        await self.clamp_trait_tracker(character_trait=willpower, character=character)

    async def clamp_trait_tracker(
        self, *, character_trait: CharacterTrait, character: Character
    ) -> None:
        """Trim a counter's spent points to fit its current value.

        Stains are stored up to the Humanity track size and never clamp on a value change.
        """
        trait = await load_trait(character_trait)
        if tracker_type_for(trait, character=character) != TrackerType.COUNTER:
            return

        async with in_transaction():
            await self._lock_trait_marks(character_trait)
            size = max(0, character_trait.value)
            if character_trait.tracker_spent <= size:
                return
            character_trait.tracker_spent = size
            await character_trait.save(update_fields=[*_TRAIT_MARK_FIELDS, "date_modified"])

    # ------------------------------------------------------------------
    # Trait trackers
    # ------------------------------------------------------------------

    async def apply_trait_action(
        self,
        *,
        character: Character,
        character_trait: CharacterTrait,
        data: TrackerActionRequest,
    ) -> TrackerResponse:
        """Apply one in-play action to a trait tracker under the character's version rules.

        Args:
            character: The character that owns the trait.
            character_trait: The trait whose tracker is changed.
            data: The action and amount.

        Returns:
            The tracker state after the action.

        Raises:
            ValidationError: If the action is not accepted, or a spend exceeds the current value.
        """
        trait, tracker_type = await self._tracker_type(
            character_trait=character_trait, character=character
        )
        validate_action(
            game_version=character.game_version,
            tracker_type=tracker_type,
            action=data.action,
        )
        phrase = _action_phrase(action=data.action, amount=data.amount)

        async with in_transaction():
            await self._lock_trait_marks(character_trait)
            before = _snapshot(character_trait, _TRAIT_MARK_FIELDS)
            match tracker_type:
                case TrackerType.COUNTER:
                    character_trait.tracker_spent = apply_counter(
                        spent=character_trait.tracker_spent,
                        size=character_trait.value,
                        action=data.action,
                        amount=data.amount,
                    )
                case TrackerType.STAINS:
                    character_trait.tracker_stains = apply_stains(
                        stains=character_trait.tracker_stains,
                        action=data.action,
                        amount=data.amount,
                    )

            await character_trait.save(update_fields=[*_TRAIT_MARK_FIELDS, "date_modified"])

        self.audit_description = f"{phrase} {trait.name} for character '{character.name}'"
        self.audit_changes = _changes(before, character_trait)
        return tracker_response_for(character_trait, tracker_type=tracker_type)

    async def set_trait_state(
        self,
        *,
        character: Character,
        character_trait: CharacterTrait,
        data: TrackerStateSet,
    ) -> TrackerResponse:
        """Set a trait tracker's full state, checking only that it fits the tracker.

        Args:
            character: The character that owns the trait.
            character_trait: The trait whose tracker is set.
            data: The new state; only the fields for the tracker type may be given.

        Returns:
            The tracker state after the change.

        Raises:
            ValidationError: If a field does not apply, is missing, or is out of bounds.
        """
        trait, tracker_type = await self._tracker_type(
            character_trait=character_trait, character=character
        )
        async with in_transaction():
            await self._lock_trait_marks(character_trait)
            before = _snapshot(character_trait, _TRAIT_MARK_FIELDS)
            _set_trait_marks(character_trait=character_trait, tracker_type=tracker_type, data=data)
            await character_trait.save(update_fields=[*_TRAIT_MARK_FIELDS, "date_modified"])

        self.audit_description = f"Set {trait.name} tracker for character '{character.name}'"
        self.audit_changes = _changes(before, character_trait)
        return tracker_response_for(character_trait, tracker_type=tracker_type)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def apply_health_action(
        self, *, character: Character, data: TrackerActionRequest
    ) -> HealthResponse:
        """Apply one in-play damage, heal, or reset action to a character's health.

        Args:
            character: The character whose health changes.
            data: The action and amount.

        Returns:
            The health state after the action.

        Raises:
            NotFoundError: If the character has no health row.
        """
        validate_action(
            game_version=character.game_version, tracker_type=TrackerType.DAMAGE, action=data.action
        )
        async with in_transaction():
            health = await self._lock_health(character)
            before = _snapshot(health, ("damage",))
            health.damage = apply_damage(
                damage=health.damage, size=health.size, action=data.action, amount=data.amount
            )
            await health.save(update_fields=["damage", "date_modified"])

        phrase = _action_phrase(action=data.action, amount=data.amount)
        self.audit_description = f"{phrase} Health for character '{character.name}'"
        self.audit_changes = _changes(before, health)
        return HealthResponse.from_model(health, character=character)

    async def set_health_state(
        self, *, character: Character, data: HealthStateSet
    ) -> HealthResponse:
        """Set a character's full health state, including extra levels, and resize the track.

        Args:
            character: The character whose health is set.
            data: The new extra levels and damage.

        Returns:
            The health state after the change.

        Raises:
            NotFoundError: If the character has no health row.
            ValidationError: If the damage exceeds the resulting size.
        """
        async with in_transaction():
            # Size from Stamina read under the health lock so a concurrent sync cannot resize
            # the track between the bounds check and the write.
            health = await self._lock_health(character)
            size = _health_size(
                character=character,
                extra_levels=data.extra_levels,
                sources=await self._derived_sources(character),
            )
            if data.damage > size:
                msg = f"damage must be at most {size}, got {data.damage}."
                raise _invalid(field="damage", msg=msg)

            before = _snapshot(health, ("size", "extra_levels", "damage"))
            health.size = size
            health.extra_levels = data.extra_levels
            health.damage = data.damage
            await health.save(update_fields=["size", "extra_levels", "damage", "date_modified"])

        self.audit_description = f"Set Health for character '{character.name}'"
        self.audit_changes = _changes(before, health)
        return HealthResponse.from_model(health, character=character)
