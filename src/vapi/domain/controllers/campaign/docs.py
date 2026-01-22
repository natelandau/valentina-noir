"""Campaign endpoint documentation."""

# Campaign Controller
LIST_CAMPAIGNS_DESCRIPTION = """\
Retrieve a paginated list of campaigns within a company.

Campaigns are containers for characters, books, chapters, and other game content.
"""

GET_CAMPAIGN_DESCRIPTION = """\
Retrieve detailed information about a specific campaign including desperation and danger levels.
"""

CREATE_CAMPAIGN_DESCRIPTION = """\
Create a new campaign within the company.

**Note:** Returns a 403 error if the user does not have the required privileges as defined in the Company's `permission_manage_campaign` setting.
"""

UPDATE_CAMPAIGN_DESCRIPTION = """\
Modify a campaign's properties such as name, description, or danger levels.

Only include fields that need to be changed; omitted fields remain unchanged.

**Note:** Returns a 403 error if the user does not have the required privileges as defined in the Company's `permission_manage_campaign` setting.
"""

DELETE_CAMPAIGN_DESCRIPTION = """\
Remove a campaign from the system.

Associated characters, books, and other content will no longer be accessible.

**Note:** Returns a 403 error if the user does not have the required privileges as defined in the Company's `permission_manage_campaign` setting.
"""

# Book Controller
LIST_BOOKS_DESCRIPTION = """\
Retrieve a paginated list of books within a campaign.

Books organize campaign content into distinct story arcs or sourcebook sections.
"""

GET_BOOK_DESCRIPTION = """\
Retrieve detailed information about a specific book including its number and description.
"""

CREATE_BOOK_DESCRIPTION = """\
Create a new book within a campaign.

The book number is assigned automatically based on existing books in the campaign.

**Note:** Returns a 403 error if the user does not have the required privileges as defined in the Company's `permission_manage_campaign` setting.
"""

UPDATE_BOOK_DESCRIPTION = """\
Modify a book's properties such as name or description.

Only include fields that need to be changed; omitted fields remain unchanged.

**Note:** Returns a 403 error if the user does not have the required privileges as defined in the Company's `permission_manage_campaign` setting.
"""

DELETE_BOOK_DESCRIPTION = """\
Remove a book from a campaign.

Remaining books are automatically renumbered to maintain sequential ordering.

**Note:** Returns a 403 error if the user does not have the required privileges as defined in the Company's `permission_manage_campaign` setting.
"""

RENUMBER_BOOK_DESCRIPTION = """\
Change a book's position in the campaign sequence.

Other books are automatically reordered to accommodate the new position.

**Note:** Returns a 403 error if the user does not have the required privileges as defined in the Company's `permission_manage_campaign` setting.
"""

# Chapter Controller
LIST_CHAPTERS_DESCRIPTION = """\
Retrieve a paginated list of chapters within a book.

Chapters represent individual game sessions or story segments.
"""

GET_CHAPTER_DESCRIPTION = """\
Retrieve detailed information about a specific chapter including its number and description.
"""

CREATE_CHAPTER_DESCRIPTION = """\
Create a new chapter within a book.

The chapter number is assigned automatically based on existing chapters in the book.

**Note:** Returns a 403 error if the user does not have the required privileges as defined in the Company's `permission_manage_campaign` setting.
"""

UPDATE_CHAPTER_DESCRIPTION = """\
Modify a chapter's properties such as name or description.

Only include fields that need to be changed; omitted fields remain unchanged.

**Note:** Returns a 403 error if the user does not have the required privileges as defined in the Company's `permission_manage_campaign` setting.
"""

DELETE_CHAPTER_DESCRIPTION = """\
Remove a chapter from a book.

Remaining chapters are automatically renumbered to maintain sequential ordering.

**Note:** Returns a 403 error if the user does not have the required privileges as defined in the Company's `permission_manage_campaign` setting.
"""

RENUMBER_CHAPTER_DESCRIPTION = """\
Change a chapter's position within a book.

Other chapters are automatically reordered to accommodate the new position.

**Note:** Returns a 403 error if the user does not have the required privileges as defined in the Company's `permission_manage_campaign` setting.
"""
