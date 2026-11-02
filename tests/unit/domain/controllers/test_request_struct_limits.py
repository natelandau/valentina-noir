"""Keep request struct bounds equal to the model validators they feed.

A request struct field maps to a model field when its encoded name equals the model
field's name. Each mapped field must declare the same length and value bounds as the
model, so msgspec rejects an out-of-range value before the request reaches the database
layer. A struct may add bounds the model lacks.
"""

from collections.abc import Callable
from typing import Any

import msgspec
import pytest
from litestar.datastructures import UploadFile
from tortoise.fields.data import CharEnumFieldInstance
from tortoise.models import Model
from tortoise.validators import (
    MaxLengthValidator,
    MaxValueValidator,
    MinLengthValidator,
    MinValueValidator,
)

from vapi.asgi import create_app
from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter
from vapi.db.sql_models.character import (
    Character,
    CharacterHealth,
    CharacterInventory,
    CharacterTrait,
    CharacterTraitSpecialty,
    HunterAttributes,
    MageAttributes,
    VampireAttributes,
    WerewolfAttributes,
)
from vapi.db.sql_models.character_sheet import Trait
from vapi.db.sql_models.company import Company, CompanySettings
from vapi.db.sql_models.developer import Developer, DeveloperCompanyPermission
from vapi.db.sql_models.diceroll import DiceRoll
from vapi.db.sql_models.dictionary import DictionaryTerm
from vapi.db.sql_models.notes import Note
from vapi.db.sql_models.quickroll import QuickRoll
from vapi.db.sql_models.user import User
from vapi.db.sql_models.validators import (
    EMAIL_PATTERN,
    NUM_CHOICES_MAX,
    NUM_CHOICES_MIN,
    STARTING_POINTS_MAX,
    STARTING_POINTS_MIN,
    XP_COST_MAX,
    XP_COST_MIN,
    validate_company_settings_num_choices,
    validate_company_settings_starting_points,
    validate_company_settings_xp_cost,
    validate_email_format,
)
from vapi.domain.controllers.campaign.dto import (
    BookChapterNumber,
    CampaignBookCreate,
    CampaignBookPatch,
    CampaignChapterCreate,
    CampaignChapterPatch,
    CampaignCreate,
    CampaignPatch,
)
from vapi.domain.controllers.character.dto import (
    CharacterCreate,
    CharacterPatch,
    CharacterTraitCreate,
    HunterAttributesCreate,
    HunterAttributesPatch,
    MageAttributesCreate,
    MageAttributesPatch,
    VampireAttributesCreate,
    VampireAttributesPatch,
    WerewolfAttributesCreate,
    WerewolfAttributesPatch,
)
from vapi.domain.controllers.character_generation.dto import (
    ChargenSessionFinalizeRequest,
    CreateAutogenerateRequest,
)
from vapi.domain.controllers.character_health.dto import HealthStateSet
from vapi.domain.controllers.character_inventory.dto import (
    InventoryItemCreate,
    InventoryItemPatch,
)
from vapi.domain.controllers.character_trait.dto import (
    CharacterTraitAddConstant,
    CharacterTraitCreateCustom,
    CharacterTraitSpecialtyCreate,
    CharacterTraitSpecialtyUpdate,
    TrackerActionRequest,
    TrackerStateSet,
    TraitModifyRequest,
)
from vapi.domain.controllers.company.dto import (
    CompanyCreate,
    CompanyPatch,
    CompanyPermissionRequest,
    CompanySettingsCreate,
    CompanySettingsPatch,
)
from vapi.domain.controllers.developer.dto import DeveloperPatch
from vapi.domain.controllers.dicerolls.dto import DiceRollCreate, QuickRollRequest
from vapi.domain.controllers.dictionary.dto import DictionaryTermCreate, DictionaryTermPatch
from vapi.domain.controllers.global_admin.dto import (
    AdminDeveloperPatch,
    AdminUserCreate,
    AdminUserPatch,
    DeveloperCreate,
)
from vapi.domain.controllers.identity.dto import IdentifyRequest, LinkIdentityRequest
from vapi.domain.controllers.notes.dto import NoteCreate, NotePatch
from vapi.domain.controllers.user.dto import (
    ExperienceAddRemove,
    QuickRollCreate,
    QuickRollPatch,
    UserApprove,
    UserCreate,
    UserMerge,
    UserPatch,
)
from vapi.lib.validation_messages import unwrap_optional

STRUCT_MODELS: dict[type[msgspec.Struct], type[Model]] = {
    AdminDeveloperPatch: Developer,
    AdminUserCreate: User,
    AdminUserPatch: User,
    CampaignBookCreate: CampaignBook,
    CampaignBookPatch: CampaignBook,
    CampaignChapterCreate: CampaignChapter,
    CampaignChapterPatch: CampaignChapter,
    CampaignCreate: Campaign,
    CampaignPatch: Campaign,
    CharacterCreate: Character,
    CharacterPatch: Character,
    CharacterTraitAddConstant: CharacterTrait,
    CharacterTraitCreate: CharacterTrait,
    CharacterTraitCreateCustom: Trait,
    CharacterTraitSpecialtyCreate: CharacterTraitSpecialty,
    CharacterTraitSpecialtyUpdate: CharacterTraitSpecialty,
    CompanyCreate: Company,
    CompanyPatch: Company,
    CompanyPermissionRequest: DeveloperCompanyPermission,
    CompanySettingsCreate: CompanySettings,
    CompanySettingsPatch: CompanySettings,
    DeveloperCreate: Developer,
    DeveloperPatch: Developer,
    DiceRollCreate: DiceRoll,
    DictionaryTermCreate: DictionaryTerm,
    DictionaryTermPatch: DictionaryTerm,
    HealthStateSet: CharacterHealth,
    HunterAttributesCreate: HunterAttributes,
    HunterAttributesPatch: HunterAttributes,
    IdentifyRequest: User,
    InventoryItemCreate: CharacterInventory,
    InventoryItemPatch: CharacterInventory,
    MageAttributesCreate: MageAttributes,
    MageAttributesPatch: MageAttributes,
    NoteCreate: Note,
    NotePatch: Note,
    QuickRollCreate: QuickRoll,
    QuickRollPatch: QuickRoll,
    QuickRollRequest: DiceRoll,
    UserApprove: User,
    UserCreate: User,
    UserPatch: User,
    VampireAttributesCreate: VampireAttributes,
    VampireAttributesPatch: VampireAttributes,
    WerewolfAttributesCreate: WerewolfAttributes,
    WerewolfAttributesPatch: WerewolfAttributes,
}

UNMAPPED: dict[type, str] = {
    UploadFile: "multipart file upload; the asset service checks the file itself",
    BookChapterNumber: "reorders a book or chapter; the number has no model validator",
    ChargenSessionFinalizeRequest: "selects a generated character by id; writes no field",
    CreateAutogenerateRequest: "drives character generation; writes no field directly",
    ExperienceAddRemove: "amount is a delta applied to campaign experience, not a column",
    LinkIdentityRequest: "provider token exchange; writes no field directly",
    TrackerActionRequest: "action and amount drive tracker rules, not columns",
    TrackerStateSet: "current and stains are translated to tracker columns by tracker rules",
    TraitModifyRequest: "target value is checked against the trait by the service",
    UserMerge: "names two users to merge; writes no field directly",
}

_EMPTY_IS_NULL = "empty string is stored as null; the model validator enforces the minimum"


EXEMPT: dict[tuple[type[Model], str], str] = {
    (Campaign, "description"): _EMPTY_IS_NULL,
    (Character, "biography"): _EMPTY_IS_NULL,
    (Character, "demeanor"): _EMPTY_IS_NULL,
    (Character, "name_nick"): _EMPTY_IS_NULL,
    (Character, "nature"): _EMPTY_IS_NULL,
    (HunterAttributes, "creed"): _EMPTY_IS_NULL,
    (MageAttributes, "sphere"): _EMPTY_IS_NULL,
    (MageAttributes, "tradition"): _EMPTY_IS_NULL,
    (QuickRoll, "description"): _EMPTY_IS_NULL,
    (VampireAttributes, "sire"): _EMPTY_IS_NULL,
    (WerewolfAttributes, "pack_name"): _EMPTY_IS_NULL,
}

_EMPTY_IS_ABSENT = (
    "empty string means absent; the service derives a username or falls back to the provider email"
)

# Mapped struct fields that deliberately skip some of the model's bounds, keyed by struct
# field, with the reason for each bound skipped. Every other bound is still compared.
BOUND_EXEMPT: dict[tuple[type[msgspec.Struct], str], dict[str, str]] = {
    (IdentifyRequest, "email"): {"pattern": _EMPTY_IS_ABSENT},
    (IdentifyRequest, "username"): {"min_length": _EMPTY_IS_ABSENT},
}


def _skipped_bounds(struct: type[msgspec.Struct], field_name: str) -> dict[str, str]:
    """Return the bounds BOUND_EXEMPT skips for a struct field, with their reasons."""
    return BOUND_EXEMPT.get((struct, field_name), {})


EMAIL_STRUCT_PATTERN = rf"^\s*{EMAIL_PATTERN.removeprefix('^').removesuffix('$')}\s*$"

# Function validators msgspec can express, as the struct constraints that replace them.
# The comparison checks these constraints, so their fields need no EXEMPT entry.
FUNCTION_BOUNDS: dict[Callable[..., None], dict[str, Any]] = {
    validate_company_settings_num_choices: {"ge": NUM_CHOICES_MIN, "le": NUM_CHOICES_MAX},
    validate_company_settings_starting_points: {
        "ge": STARTING_POINTS_MIN,
        "le": STARTING_POINTS_MAX,
    },
    validate_company_settings_xp_cost: {"ge": XP_COST_MIN, "le": XP_COST_MAX},
    validate_email_format: {"pattern": EMAIL_STRUCT_PATTERN},
}

_COMPARED = (MinLengthValidator, MaxLengthValidator, MinValueValidator, MaxValueValidator)
_CONTAINERS = (
    msgspec.inspect.ListType,
    msgspec.inspect.SetType,
    msgspec.inspect.FrozenSetType,
    msgspec.inspect.VarTupleType,
)


def _request_body_types() -> list[Any]:
    """Collect the `data` annotation of every route handler in the app."""
    app = create_app()
    bodies: list[Any] = []
    for route in app.routes:
        for handler in getattr(route, "route_handlers", []):
            data = handler.parsed_fn_signature.parameters.get("data")
            if data is not None:
                bodies.append(data.annotation)
    return bodies


def _collect_structs(info: msgspec.inspect.Type, found: set[type]) -> None:
    """Walk a type tree and add every Struct class it reaches to `found`."""
    if isinstance(info, msgspec.inspect.StructType):
        if info.cls in found:
            return
        found.add(info.cls)
        for field in info.fields:
            _collect_structs(field.type, found)
    elif isinstance(info, msgspec.inspect.UnionType):
        for member in info.types:
            _collect_structs(member, found)
    elif isinstance(info, msgspec.inspect.TupleType):
        for member in info.item_types:
            _collect_structs(member, found)
    elif isinstance(info, _CONTAINERS):
        _collect_structs(info.item_type, found)
    elif isinstance(info, msgspec.inspect.DictType):
        _collect_structs(info.key_type, found)
        _collect_structs(info.value_type, found)


def _is_enum(info: msgspec.inspect.Type) -> bool:
    """Report whether a struct field only accepts the members of an enum."""
    return isinstance(unwrap_optional(info), msgspec.inspect.EnumType | msgspec.inspect.LiteralType)


def _struct_bounds(info: msgspec.inspect.Type) -> dict[str, Any]:
    """Read the bounds msgspec enforces on a struct field."""
    value = unwrap_optional(info)
    if isinstance(value, msgspec.inspect.StrType):
        return {
            "min_length": value.min_length,
            "max_length": value.max_length,
            "pattern": value.pattern,
        }
    if isinstance(value, msgspec.inspect.IntType):
        return {"ge": value.ge, "le": value.le}
    if isinstance(value, msgspec.inspect.ListType):
        return {"min_length": value.min_length, "max_length": value.max_length}
    return {}


def _model_bounds(
    model: type[Model], name: str, struct_type: msgspec.inspect.Type
) -> tuple[dict[str, Any], list[str]]:
    """Read the bounds a model field's validators enforce, and what the comparison skips.

    Returns:
        The bounds to compare, and a description of each check the comparison cannot make.
    """
    field = model._meta.fields_map[name]
    bounds: dict[str, Any] = {}
    skipped: list[str] = []
    for validator in field.validators:
        if isinstance(validator, MinLengthValidator):
            bounds["min_length"] = validator.min_length
        elif isinstance(validator, MaxLengthValidator):
            bounds["max_length"] = validator.max_length
        elif isinstance(validator, MinValueValidator):
            bounds["ge"] = validator.min_value
        elif isinstance(validator, MaxValueValidator):
            bounds["le"] = validator.max_value
        elif validator in FUNCTION_BOUNDS:
            bounds.update(FUNCTION_BOUNDS[validator])
        else:
            skipped.append(f"validator {validator!r}")
    if name in getattr(model, "_empty_string_to_none_fields", frozenset()):
        bounds.pop("min_length", None)
        skipped.append("min_length, since empty is stored as null")
    if isinstance(field, CharEnumFieldInstance):
        # An enum-typed struct field already limits the value to the enum's members.
        if _is_enum(struct_type):
            bounds.pop("max_length", None)
        else:
            skipped.append("enum membership")
    return bounds, skipped


def _mapped_fields(
    struct: type[msgspec.Struct], model: type[Model]
) -> list[tuple[msgspec.structs.FieldInfo, str]]:
    """Pair each struct field with the model field of the same name."""
    return [
        (field, field.encode_name)
        for field in msgspec.structs.fields(struct)
        if field.encode_name in model._meta.fields_map
    ]


def test_every_request_body_is_classified() -> None:
    """Verify every request body and nested Struct is mapped to a model or unmapped."""
    # Given every request body in the app
    bodies = _request_body_types()

    # When walking each body to its nested Struct types
    structs: set[type] = set()
    others: set[type] = set()
    for body in bodies:
        reached: set[type] = set()
        _collect_structs(msgspec.inspect.type_info(body), reached)
        if not reached:
            others.add(body)
        structs |= reached

    # Then each one is classified, and no classification is stale
    classified = set(STRUCT_MODELS) | set(UNMAPPED)
    unclassified = sorted(t.__name__ for t in (structs | others) - classified)
    stale = sorted(t.__name__ for t in classified - structs - others)
    assert not unclassified, f"Unclassified request types: {unclassified}"
    assert not stale, f"Classified types no route uses: {stale}"


def test_struct_limits_match_model_validators() -> None:
    """Verify each mapped struct field declares the model field's bounds."""
    # Given every struct mapped to a model
    mismatches: list[str] = []

    # When comparing each mapped field's bounds
    for struct, model in STRUCT_MODELS.items():
        for field, name in _mapped_fields(struct, model):
            struct_type = msgspec.inspect.type_info(field.type)
            expected, _ = _model_bounds(model, name, struct_type)
            actual = _struct_bounds(struct_type)
            skipped = _skipped_bounds(struct, field.name)
            mismatches.extend(
                f"{struct.__name__}.{field.name}.{key}: struct={actual.get(key)} model={value}"
                for key, value in sorted(expected.items())
                if key not in skipped and actual.get(key) != value
            )

    # Then every bound matches
    assert not mismatches, "Struct bounds differ from the model:\n" + "\n".join(mismatches)


def test_every_other_validator_is_exempt() -> None:
    """Verify each skipped validator or bound on a mapped field has an EXEMPT reason."""
    # Given every mapped field
    mapped = [
        (model, name, msgspec.inspect.type_info(field.type))
        for struct, model in STRUCT_MODELS.items()
        for field, name in _mapped_fields(struct, model)
    ]

    # When finding the fields whose validators the comparison does not fully cover
    needing = {(model, name) for model, name, info in mapped if _model_bounds(model, name, info)[1]}

    # Then exactly those fields are exempt, each with a reason
    missing = sorted(f"{m.__name__}.{n}" for m, n in needing - set(EXEMPT))
    stale = sorted(f"{m.__name__}.{n}" for m, n in set(EXEMPT) - needing)
    assert not missing, f"Fields missing an EXEMPT entry: {missing}"
    assert not stale, f"EXEMPT entries with nothing to exempt: {stale}"
    assert all(EXEMPT.values())


def test_empty_string_still_accepted() -> None:
    """Verify an empty description converts, since the model stores it as null."""
    # Given a campaign with an empty description
    payload = {"name": "Camp", "description": ""}

    # When converting it to the request struct
    result = msgspec.convert(payload, CampaignCreate)

    # Then the empty string passes through
    assert result.description == ""


def _email_field_types() -> list[tuple[str, Any]]:
    """Return the annotation of every `email` field on a mapped request struct."""
    return [
        (struct.__name__, field.type)
        for struct in STRUCT_MODELS
        for field in msgspec.structs.fields(struct)
        if field.encode_name == "email" and "pattern" not in _skipped_bounds(struct, field.name)
    ]


@pytest.mark.parametrize(("struct_name", "field_type"), _email_field_types())
def test_email_with_outer_spaces_accepted(struct_name: str, field_type: Any) -> None:
    """Verify a padded email converts and a malformed one fails on every email field."""
    # Given an email with surrounding whitespace
    padded = "  someone@example.com "

    # When converting it to the field type
    result = msgspec.convert(padded, field_type)

    # Then it passes, and a malformed address fails the pattern
    assert result == padded, struct_name
    with pytest.raises(msgspec.ValidationError, match=r"Expected `str` matching regex"):
        msgspec.convert("not-an-email", field_type)


def test_bound_exemptions_are_live() -> None:
    """Verify each BOUND_EXEMPT entry skips a bound the model has and the struct omits."""
    # Given every BOUND_EXEMPT entry
    entries = BOUND_EXEMPT.items()

    # When checking each entry against the model field it maps and the struct
    unmapped: list[str] = []
    problems: list[str] = []
    for (struct, field_name), skipped in entries:
        model = STRUCT_MODELS.get(struct)
        mapped = {f.name: (f, name) for f, name in _mapped_fields(struct, model)} if model else {}
        if field_name not in mapped:
            unmapped.append(f"{struct.__name__}.{field_name}")
            continue
        field, name = mapped[field_name]
        struct_type = msgspec.inspect.type_info(field.type)
        expected, _ = _model_bounds(model, name, struct_type)
        actual = _struct_bounds(struct_type)
        for key, reason in sorted(skipped.items()):
            if key not in expected or actual.get(key) is not None:
                problems.append(
                    f"{struct.__name__}.{field_name}.{key}: model={expected.get(key)} "
                    f"struct={actual.get(key)}"
                )
            if not reason:
                problems.append(f"{struct.__name__}.{field_name}.{key}: no reason")

    # Then every entry maps a model field, and every skipped bound is real, left off the
    # struct, and explained
    assert not unmapped, f"BOUND_EXEMPT entries that map no model field: {sorted(unmapped)}"
    assert not problems, "\n".join(problems)


def test_identify_accepts_empty_username_and_email() -> None:
    """Verify empty identify fields convert, since the service treats them as absent."""
    # Given an identify request with empty username and email
    payload = {"provider": "google", "token": "t", "username": "", "email": ""}

    # When converting it to the request struct
    result = msgspec.convert(payload, IdentifyRequest)

    # Then both empty strings pass through
    assert (result.username, result.email) == ("", "")


def test_identify_rejects_long_username() -> None:
    """Verify the identify username keeps the model's maximum length."""
    # Given an identify request with a 51-character username
    payload = {"provider": "google", "token": "t", "username": "u" * 51}

    # When converting it to the request struct
    # Then msgspec rejects the length
    with pytest.raises(msgspec.ValidationError, match=r"Expected `str` of length <= 50"):
        msgspec.convert(payload, IdentifyRequest)


@pytest.mark.parametrize(
    ("struct", "payload", "field_name"),
    [
        (CompanyCreate, {"name": "Acme"}, "email"),
        (NoteCreate, {"title": "A note"}, "content"),
    ],
)
def test_omitted_required_field_fails(
    struct: type[msgspec.Struct], payload: dict[str, str], field_name: str
) -> None:
    """Verify a field with no valid default must be sent."""
    # Given a payload without the field
    # When converting it to the request struct
    # Then msgspec rejects the missing field
    with pytest.raises(
        msgspec.ValidationError, match=f"Object missing required field `{field_name}`"
    ):
        msgspec.convert(payload, struct)
