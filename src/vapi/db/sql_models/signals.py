"""Pre-save signal handlers for Tortoise models.

This module must be imported at module load time (via __init__.py) so that
signal handlers are registered before any model saves occur.

Note: archive_date management is handled via BaseModel.save() override, not a
signal, because Tortoise signals don't fire on abstract models.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise.signals import pre_save

from vapi.db.sql_models.character_sheet import Trait
from vapi.db.sql_models.developer import Developer
from vapi.db.sql_models.dictionary import DictionaryTerm
from vapi.db.sql_models.user import User
from vapi.utils.strings import slugify

__all__: list[str] = []

if TYPE_CHECKING:
    from collections.abc import Iterable

    from tortoise.backends.base.client import BaseDBAsyncClient


@pre_save(Developer)
async def slugify_developer_username(
    sender: type[Developer],  # noqa: ARG001
    instance: Developer,
    using_db: BaseDBAsyncClient | None,  # noqa: ARG001
    update_fields: Iterable[str] | None,  # noqa: ARG001
) -> None:
    """Slugify the developer's username before saving."""
    instance.username = slugify(instance.username)


@pre_save(User)
async def slugify_user_username(
    sender: type[User],  # noqa: ARG001
    instance: User,
    using_db: BaseDBAsyncClient | None,  # noqa: ARG001
    update_fields: Iterable[str] | None,  # noqa: ARG001
) -> None:
    """Slugify the user's username before saving."""
    instance.username = slugify(instance.username)


@pre_save(DictionaryTerm)
async def lowercase_dictionary_term(
    sender: type[DictionaryTerm],  # noqa: ARG001
    instance: DictionaryTerm,
    using_db: BaseDBAsyncClient | None,  # noqa: ARG001
    update_fields: Iterable[str] | None,  # noqa: ARG001
) -> None:
    """Lowercase term, deduplicate and sort synonyms.

    BaseModel.save() already strips whitespace on CharFields before signals fire,
    so .strip() is only needed for individual synonym elements inside the ArrayField.
    """
    instance.term = instance.term.lower()
    instance.synonyms = sorted({s.lower().strip() for s in instance.synonyms})


@pre_save(Trait)
async def normalize_trait_name(
    sender: type[Trait],  # noqa: ARG001
    instance: Trait,
    using_db: BaseDBAsyncClient | None,  # noqa: ARG001
    update_fields: Iterable[str] | None,  # noqa: ARG001
) -> None:
    """Normalize trait name to title case before saving."""
    instance.name = instance.name.title()
