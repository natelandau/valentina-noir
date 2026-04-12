"""Unit tests for CharacterService.apply_patch."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from vapi.db.sql_models.character import (
    HunterAttributes,
    MageAttributes,
    VampireAttributes,
    WerewolfAttributes,
)
from vapi.domain.controllers.character.dto import (
    CharacterPatch,
    HunterAttributesPatch,
    MageAttributesPatch,
    VampireAttributesPatch,
    WerewolfAttributesPatch,
)
from vapi.domain.services import CharacterService

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


class TestApplyPatchScalars:
    """Test scalar field patching and change tracking."""

    async def test_apply_patch_scalar_fields(
        self,
        character_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify scalar fields are applied and diffs are recorded."""
        # Given a character with known values
        company = await company_factory()
        character = await character_factory(company=company, name_first="Old", name_last="Name")
        service = CharacterService()

        # When patching name_first and name_last
        data = CharacterPatch(name_first="New", name_last="Last")
        changes = await service.apply_patch(character, data)

        # Then the character is updated in-place
        assert character.name_first == "New"
        assert character.name_last == "Last"

        # And the changes dict records old and new values
        assert changes["name_first"] == {"old": "Old", "new": "New"}
        assert changes["name_last"] == {"old": "Name", "new": "Last"}

    async def test_apply_patch_no_op(
        self,
        character_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify setting a field to its current value produces no diff."""
        # Given a character
        company = await company_factory()
        character = await character_factory(company=company, name_first="Same")
        service = CharacterService()

        # When patching name_first to the same value
        data = CharacterPatch(name_first="Same")
        changes = await service.apply_patch(character, data)

        # Then no changes are recorded
        assert changes == {}

    async def test_apply_patch_unset_fields_ignored(
        self,
        character_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify UNSET fields are not applied."""
        # Given a character with known values
        company = await company_factory()
        character = await character_factory(company=company, name_first="Keep", biography="Bio")
        service = CharacterService()

        # When patching only name_first (biography is UNSET)
        data = CharacterPatch(name_first="Changed")
        changes = await service.apply_patch(character, data)

        # Then biography is unchanged
        assert character.biography == "Bio"
        assert "biography" not in changes
        assert changes["name_first"] == {"old": "Keep", "new": "Changed"}

    async def test_apply_patch_nullable_field_to_none(
        self,
        character_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify nullable fields can be set to None."""
        # Given a character with a biography
        company = await company_factory()
        character = await character_factory(company=company, biography="Has bio")
        service = CharacterService()

        # When patching biography to None
        data = CharacterPatch(biography=None)
        changes = await service.apply_patch(character, data)

        # Then biography is None and the diff is recorded
        assert character.biography is None
        assert changes["biography"] == {"old": "Has bio", "new": None}


class TestApplyPatchNestedAttributes:
    """Test nested attribute patching (vampire, werewolf, mage, hunter)."""

    async def test_apply_patch_vampire_attributes(
        self,
        character_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify vampire attributes are applied with dotted key diffs."""
        # Given a vampire character with existing attributes
        company = await company_factory()
        character = await character_factory(company=company, character_class="VAMPIRE")
        await VampireAttributes.create(character=character, generation=13, sire="Old Sire")

        service = CharacterService()

        # When patching vampire attributes
        data = CharacterPatch(
            vampire_attributes=VampireAttributesPatch(generation=10, sire="New Sire"),
        )
        changes = await service.apply_patch(character, data)

        # Then the attributes are updated in the database
        va = await VampireAttributes.filter(character=character).first()
        assert va.generation == 10
        assert va.sire == "New Sire"

        # And changes use dotted keys
        assert changes["vampire_attributes.generation"] == {"old": 13, "new": 10}
        assert changes["vampire_attributes.sire"] == {"old": "Old Sire", "new": "New Sire"}

    async def test_apply_patch_creates_nested_row_if_absent(
        self,
        character_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify nested attribute row is created when it doesn't exist yet."""
        # Given a character with no werewolf attributes row
        company = await company_factory()
        character = await character_factory(company=company)

        service = CharacterService()

        # When patching werewolf attributes
        data = CharacterPatch(
            werewolf_attributes=WerewolfAttributesPatch(pack_name="Moon Pack"),
        )
        changes = await service.apply_patch(character, data)

        # Then the row is created with the value
        wa = await WerewolfAttributes.filter(character=character).first()
        assert wa is not None
        assert wa.pack_name == "Moon Pack"

        # And the change is recorded (old is None since the row was just created)
        assert changes["werewolf_attributes.pack_name"] == {"old": None, "new": "Moon Pack"}

    async def test_apply_patch_mage_attributes(
        self,
        character_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify mage attributes are applied correctly."""
        # Given a character with existing mage attributes
        company = await company_factory()
        character = await character_factory(company=company)
        await MageAttributes.create(character=character, sphere="Forces", tradition="Etherite")

        service = CharacterService()

        # When patching mage attributes
        data = CharacterPatch(
            mage_attributes=MageAttributesPatch(sphere="Mind"),
        )
        changes = await service.apply_patch(character, data)

        # Then only the changed field is in the diff
        ma = await MageAttributes.filter(character=character).first()
        assert ma.sphere == "Mind"
        assert ma.tradition == "Etherite"
        assert changes["mage_attributes.sphere"] == {"old": "Forces", "new": "Mind"}
        assert "mage_attributes.tradition" not in changes

    async def test_apply_patch_hunter_attributes(
        self,
        character_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify hunter attributes are applied correctly."""
        # Given a character with existing hunter attributes
        company = await company_factory()
        character = await character_factory(company=company)
        await HunterAttributes.create(character=character, creed="Defender")

        service = CharacterService()

        # When patching hunter attributes
        data = CharacterPatch(
            hunter_attributes=HunterAttributesPatch(creed="Avenger"),
        )
        changes = await service.apply_patch(character, data)

        # Then the attribute is updated
        ha = await HunterAttributes.filter(character=character).first()
        assert ha.creed == "Avenger"
        assert changes["hunter_attributes.creed"] == {"old": "Defender", "new": "Avenger"}


class TestApplyPatchMixed:
    """Test combined scalar and nested attribute patches."""

    async def test_apply_patch_scalar_and_nested(
        self,
        character_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify scalar and nested changes are combined in one diff."""
        # Given a character with vampire attributes
        company = await company_factory()
        character = await character_factory(
            company=company, name_first="Old", character_class="VAMPIRE"
        )
        await VampireAttributes.create(character=character, generation=13)

        service = CharacterService()

        # When patching both scalar and nested fields
        data = CharacterPatch(
            name_first="New",
            vampire_attributes=VampireAttributesPatch(generation=10),
        )
        changes = await service.apply_patch(character, data)

        # Then both types of changes are in the diff
        assert character.name_first == "New"
        assert changes["name_first"] == {"old": "Old", "new": "New"}
        assert changes["vampire_attributes.generation"] == {"old": 13, "new": 10}

    async def test_apply_patch_empty_patch(
        self,
        character_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify an empty patch produces no changes."""
        # Given a character
        company = await company_factory()
        character = await character_factory(company=company, name_first="Unchanged")
        service = CharacterService()

        # When applying an empty patch (all fields UNSET)
        data = CharacterPatch()
        changes = await service.apply_patch(character, data)

        # Then nothing changed
        assert changes == {}
        assert character.name_first == "Unchanged"

    async def test_apply_patch_nested_no_op(
        self,
        character_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify nested attributes set to current values produce no diff."""
        # Given a character with vampire attributes
        company = await company_factory()
        character = await character_factory(company=company)
        await VampireAttributes.create(character=character, generation=13)

        service = CharacterService()

        # When patching generation to the same value
        data = CharacterPatch(
            vampire_attributes=VampireAttributesPatch(generation=13),
        )
        changes = await service.apply_patch(character, data)

        # Then no changes are recorded
        assert changes == {}


class TestNestedAttributeFieldsSync:
    """Guard against _NESTED_ATTRIBUTE_FIELDS drifting from CharacterPatch."""

    def test_nested_fields_match_patch_dto(self) -> None:
        """Verify _NESTED_ATTRIBUTE_FIELDS covers all nested Struct fields on CharacterPatch."""
        # Given the CharacterPatch DTO fields
        import msgspec as _msgspec

        # Nested attribute fields end with "_attributes" and default to UNSET
        nested_on_dto: set[str] = set()
        for field in _msgspec.structs.fields(CharacterPatch):
            if field.name.endswith("_attributes") and isinstance(field.default, _msgspec.UnsetType):
                nested_on_dto.add(field.name)

        # Then the service's exclusion set matches
        assert nested_on_dto == CharacterService._NESTED_ATTRIBUTE_FIELDS
