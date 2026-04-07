"""User endpoint documentation."""

# User Controller
LIST_USERS_DESCRIPTION = """\
Retrieve a paginated list of users within a company.

Optionally filter by user role to view specific user types such as players or storytellers. \
Filter by email to find a user by their exact email address, useful for checking if a user \
already exists before registration.
"""

GET_USER_DESCRIPTION = """\
Retrieve detailed information about a specific user including their role and experience.

Use the `include` query parameter to embed related child resources in the response. \
Pass one or more of: `quickrolls`, `notes`, `assets`, `characters`. Example: \
`?include=quickrolls&include=characters`. The `assets` value returns assets attached \
to the user (not assets the user uploaded). The `characters` value returns only \
characters the user plays. When omitted, child resources are not included and must \
be fetched via their dedicated endpoints. Invalid values return a 400 error.
"""

CREATE_USER_DESCRIPTION = """\
Create a new user within a company.

The user is automatically added to the company's user list. The Discord profile is optional and is not used for authentication but is included for Discord bot integration.

**Note:** Requires admin-level access to the company.
"""

UPDATE_USER_DESCRIPTION = """\
Modify a user's properties such as name, role, or profile information.

Only include fields that need to be changed; omitted fields remain unchanged.
"""

DELETE_USER_DESCRIPTION = """\
Remove a user from the company.

The user is removed from the company's user list and their data is archived.
"""

# Experience Controller
GET_CAMPAIGN_EXPERIENCE_DESCRIPTION = """\
Retrieve a user's experience points and cool points for a specific campaign.

Creates the experience record automatically if it doesn't exist for the campaign.
"""

ADD_XP_DESCRIPTION = """\
Award experience points to a user for a specific campaign.

The XP is added to both the current XP pool (available for spending) and the total XP tracker (lifetime earned).
"""

REMOVE_XP_DESCRIPTION = """\
Deduct experience points from a user's current XP pool.

Returns an error if the user has insufficient XP to complete the deduction.
"""

ADD_CP_DESCRIPTION = """\
Award cool points to a user for a specific campaign.

Cool points are converted to XP automatically based on the company's configured exchange rate.
"""

# Quick Roll Controller
LIST_QUICKROLLS_DESCRIPTION = """\
Retrieve a paginated list of quick rolls saved by a user.

Quick rolls are pre-configured dice pools for frequently used trait combinations, allowing faster gameplay.
"""

GET_QUICKROLL_DESCRIPTION = """\
Retrieve details of a specific quick roll including its name and associated trait configuration.
"""

CREATE_QUICKROLL_DESCRIPTION = """\
Create a new quick roll for a user.

Define the traits that make up the dice pool. Quick roll names must be unique per user.
"""

UPDATE_QUICKROLL_DESCRIPTION = """\
Modify a quick roll's name or trait configuration.

Only include fields that need to be changed; omitted fields remain unchanged.
"""

DELETE_QUICKROLL_DESCRIPTION = """\
Remove a quick roll from a user. This action cannot be undone.
"""

# Unapproved User Controller
LIST_UNAPPROVED_USERS_DESCRIPTION = """\
Retrieve a paginated list of users pending approval within a company.

Only returns non-archived users with the UNAPPROVED role. Requires admin-level access.
"""

APPROVE_USER_DESCRIPTION = """\
Approve a pending user and assign them a role within the company.

The target user must have the UNAPPROVED role. The assigned role must be PLAYER, STORYTELLER, or ADMIN.

**Note:** Requires admin-level access.
"""

DENY_USER_DESCRIPTION = """\
Deny a pending user and remove them from the company.

The target user must have the UNAPPROVED role. The user is archived and removed from the company's user list.

**Note:** Requires admin-level access.
"""

# Registration & Merge Controller
REGISTER_USER_DESCRIPTION = """\
Register a new user via SSO onboarding.

Creates a new user with the UNAPPROVED role. This endpoint is designed for automated \
user provisioning when a new identity provider user is encountered. No requesting user \
ID is required - developer API key authentication is sufficient.

The created user must be approved by an admin before they can access features. \
Use the approve endpoint to activate the user after registration.
"""

MERGE_USERS_DESCRIPTION = """\
Merge an UNAPPROVED user into an existing primary user.

Copies OAuth profile fields (Google, GitHub, Discord) from the secondary user to the \
primary user, filling in only empty profile fields on the primary. The secondary user \
is then deleted and removed from the company's user list.

The secondary user must have the UNAPPROVED role. This endpoint is designed for \
account linking when a user authenticates via a new identity provider and a duplicate \
UNAPPROVED account was created before the match was identified.

**Note:** Requires admin-level access.
"""
