"""Developer documentation."""

GET_ME_DESCRIPTION = """\
Retrieve the developer profile associated with the current API key. Use this to verify authentication and view your account details.
"""

REGENERATE_API_KEY_DESCRIPTION = """\
Generate a new API key for your account. The current key will be immediately invalidated and all cached authentication data will be cleared.

**Be certain to save the API key from the response. It will not be displayed again.**
"""

UPDATE_ME_DESCRIPTION = """\
Modify your developer profile. Only include fields that need to be changed; omitted fields remain unchanged.

Use the `provider_audiences` field to register the Apple bundle IDs or Google OAuth client IDs your \
application uses. Once registered, the identify endpoint will accept tokens whose `aud` claim matches \
one of your registered values, in addition to any server-wide audiences configured by the operator. \
Keys must be `apple` or `google`; each list may contain at most 20 entries of up to 255 characters each. \
Set `provider_audiences` to `null` to clear all registered audiences.
"""
