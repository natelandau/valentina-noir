"""Endpoint descriptions for user avatar management."""

SET_AVATAR_DESCRIPTION = (
    "Upload a custom avatar for the user. The image is normalized to a 512x512 WebP "
    "and overrides any avatar derived from a linked identity provider. Accepts PNG, "
    "JPEG, WEBP, or GIF (first frame), up to 5 MB. Replaces any existing custom avatar."
)

DELETE_AVATAR_DESCRIPTION = (
    "Remove the user's custom avatar. The avatar falls back to the identity-provider "
    "avatar, or none if no provider avatar is available."
)
