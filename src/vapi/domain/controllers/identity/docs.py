"""OpenAPI descriptions for identity endpoints."""

IDENTIFY_DESCRIPTION = """\
Resolve a verified provider login to a canonical user.

Send the credential your client obtained from the provider's own login flow: an \
OIDC ID token for `apple` or `google`, or an OAuth access token for `discord` or \
`github`. The API verifies the credential with the provider, then resolves the user \
in order: match by provider ID, auto-link by provider-verified email, or create a \
new UNAPPROVED user.

The `resolution` field reports which path was taken (`matched`, `linked`, or \
`created`). `username` and `email` are used only when a new user is created; `email` \
is required there only if the provider did not supply one. Verification failures \
return 422 with code TOKEN_VERIFICATION_FAILED; provider outages return 503.

Apple and Google tokens are accepted when their audience appears in either the \
server's global env allowlist (`VAPI_OAUTH__APPLE_AUDIENCES` / \
`VAPI_OAUTH__GOOGLE_AUDIENCES`) or the calling developer's self-registered audiences \
(`provider_audiences` on `PATCH /developers/me`). A provider is disabled (422) only \
when both sources are empty for the caller.
"""

LINK_DESCRIPTION = """\
Attach an additional verified provider identity to an existing user.

Use this for "connect your account" settings flows: a user already authenticated \
via one provider presents a credential from a second provider, which is verified \
and linked to the same user. Only the user themselves or a company admin may link \
identities.

Returns 409 with code IDENTITY_ALREADY_LINKED if the identity belongs to another \
user (use the merge endpoint instead) or if the user already has a different \
identity from this provider. Re-linking the same identity is idempotent and \
refreshes the stored profile.
"""
