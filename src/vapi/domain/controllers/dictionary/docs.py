"""Dictionary documentation."""

LIST_DICTIONARY_TERMS_DESCRIPTION = """\
Retrieve a paginated list of dictionary terms for a company. Optionally search by term name or synonym. Terms provide definitions for game concepts and lore.

**Note:** This endpoint includes both company-specific and global dictionary terms.
"""

GET_DICTIONARY_TERM_DESCRIPTION = """\
Retrieve a specific dictionary term including its definition and synonyms.

**Note:** This endpoint includes both company-specific and global dictionary terms.
"""

CREATE_DICTIONARY_TERM_DESCRIPTION = """\
Add a new term to the company's dictionary. Include the term, definition, and optional synonyms for discovery.
"""

UPDATE_DICTIONARY_TERM_DESCRIPTION = """\
Modify a dictionary term's definition or synonyms. Only include fields that need to be changed.

**Note:** You may only update dictionary terms that are local to the company.
"""

DELETE_DICTIONARY_TERM_DESCRIPTION = """\
Remove a term from the company's dictionary. This action cannot be undone.

**Note:** You may only delete dictionary terms that are local to the company.
"""
