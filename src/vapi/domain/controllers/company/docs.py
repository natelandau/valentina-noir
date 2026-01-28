"""Company endpoint documentation."""

LIST_COMPANIES_DESCRIPTION = """\
Retrieve a paginated list of companies you have access to.

Only companies where you have been granted at least user-level permissions are returned.
"""

GET_COMPANY_DESCRIPTION = """\
Retrieve detailed information about a specific company including its settings and configuration.

**Note:** Requires at least user-level access to the company.
"""

CREATE_COMPANY_DESCRIPTION = """\
Create a new company in the system AND a user account with `ADMIN` permissions for the company with your developer username and email (you can patch this later).

Your API key is granted `OWNER` permission for the new company, giving you full administrative control, including the ability to grant permissions to other developers.
"""

UPDATE_COMPANY_DESCRIPTION = """\
Modify a company's properties such as name or settings.

Only include fields that need to be changed; omitted fields remain unchanged.

**Note:** Requires admin-level access to the company.
"""

DELETE_COMPANY_DESCRIPTION = """\
Delete a company from the system.

This is a destructive action that archives the company and all associated data.

**Note:** Requires owner-level access to the company.
"""

DEVELOPER_ACCESS_DESCRIPTION = """\
Add, update, or revoke a developer's permission level for this company.

Valid permission levels are `USER`, `ADMIN`, and `OWNER`. Set permission to `REVOKE` to revoke access entirely.

**Restrictions:**
- Every company must have at least one owner

**Note:** Requires owner-level access to the company.
"""
