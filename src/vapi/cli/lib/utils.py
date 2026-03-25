"""Utilities."""

from vapi.cli.lib.comparison import (
    JSONWithCommentsDecoder,
    document_differs_from_fixture,
    get_differing_fields,
)
from vapi.cli.lib.trait_syncer import (
    SyncCounts,
    TraitSyncer,
    TraitSyncResult,
)

__all__ = (
    "JSONWithCommentsDecoder",
    "SyncCounts",
    "TraitSyncResult",
    "TraitSyncer",
    "document_differs_from_fixture",
    "get_differing_fields",
)
