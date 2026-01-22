"""Global admin documentation."""

LIST_DEVELOPERS_DESCRIPTION = """\
Retrieve a paginated list of all developer accounts in the system. Requires global admin privileges.
"""

GET_DEVELOPER_DESCRIPTION = """\
Retrieve detailed information about a specific developer account. Requires global admin privileges.
"""

CREATE_DEVELOPER_DESCRIPTION = """\
Create a new developer account. This creates the account but does not create an API key or grant access to any companies.

**Be certain to generate an API key after account creation.**

Requires global admin privileges.
"""

UPDATE_DEVELOPER_DESCRIPTION = """\
Modify a developer account's properties. Only include fields that need to be changed. Requires global admin privileges.
"""

DELETE_DEVELOPER_DESCRIPTION = """\
Remove a developer account from the system. The developer's API key will be invalidated immediately. Requires global admin privileges.
"""

CREATE_API_KEY_DESCRIPTION = """\
Generate a new API key for a developer. Their current key will be immediately invalidated.

**Be certain to save the API key as it will not be displayed again.**

Requires global admin privileges.
"""
