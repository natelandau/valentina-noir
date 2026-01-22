"""User endpoint documentation."""

# User Controller
LIST_USERS_DESCRIPTION = """\
Retrieve a paginated list of users within a company.

Optionally filter by user role to view specific user types such as players or storytellers.
"""

GET_USER_DESCRIPTION = """\
Retrieve detailed information about a specific user including their role and experience.
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
