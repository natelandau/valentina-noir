"""Shared helper utilities for user controllers."""

from uuid import UUID

from vapi.db.sql_models.user import User
from vapi.domain.controllers.user.dto import UserResponse
from vapi.domain.services.user_svc import annotate_user_counts


async def annotated_user_response(user_id: UUID) -> UserResponse:
    """Re-fetch a user with count annotations and return a scalar response.

    Use this helper whenever a mutating endpoint must return accurate child-resource
    counts (num_quickrolls, num_notes, num_assets, num_characters). A plain
    ``UserResponse.from_model(user)`` returns zeros for annotated fields; this
    re-fetches with the annotation query so the response is always accurate.

    Args:
        user_id: The UUID of the user to fetch and annotate.

    Returns:
        A fully-populated UserResponse with accurate count fields.
    """
    user = await annotate_user_counts(
        User.filter(id=user_id).prefetch_related("campaign_experiences")
    ).first()
    return UserResponse.from_model(user)
