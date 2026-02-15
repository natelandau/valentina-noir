---
icon: lucide/book-a
---

# Dictionary Service

Manage dictionary terms within a company for in-game terminology and definitions. Store and search custom terms, definitions, and synonyms specific to your campaigns.

## Initialize the Service

```python
from vclient import dictionary_service

dictionary = dictionary_service(company_id="COMPANY_ID")
```

## Available Methods

### CRUD Operations

| Method                                            | Returns          | Description                  |
| ------------------------------------------------- | ---------------- | ---------------------------- |
| `get(term_id)`                                    | `DictionaryTerm` | Retrieve a term by ID        |
| `create(request=None, **kwargs)`               | `DictionaryTerm` | Create a new term            |
| `update(term_id, request=None, **kwargs)`      | `DictionaryTerm` | Update an existing term      |
| `delete(term_id)`                                 | `None`           | Delete a term                |

### Pagination Methods

| Method                                      | Returns                             | Description                          |
| ------------------------------------------- | ----------------------------------- | ------------------------------------ |
| `get_page(limit=10, offset=0, term=None)`   | `PaginatedResponse[DictionaryTerm]` | Retrieve a paginated page of terms   |
| `list_all(term=None)`                       | `list[DictionaryTerm]`              | Retrieve all terms (auto-paginated)  |
| `iter_all(term=None, limit=100)`            | `AsyncIterator[DictionaryTerm]`     | Iterate through all terms            |

## Examples

### Create a Term

Add a new dictionary term with definition and synonyms.

```python
from vclient.models import DictionaryTermCreate

# Option 1: Use a model object (preferred)
request = DictionaryTermCreate(
    term="Embrace",
    definition="The act of turning a mortal into a vampire",
    synonyms=["Turn", "Siring"]
)
term = await dictionary.create(request)

# Option 2: Pass fields as keyword arguments
term = await dictionary.create(
    term="Embrace",
    definition="The act of turning a mortal into a vampire",
    synonyms=["Turn", "Siring"]
)
```

### Update a Term

Modify an existing dictionary term's definition or synonyms.

```python
from vclient.models import DictionaryTermUpdate

update = DictionaryTermUpdate(
    definition="The transformation of a mortal into an immortal vampire"
)
updated = await dictionary.update(term.id, update)
```

### Search Terms

Search for dictionary terms by name.

```python
# Search for a specific term
terms = await dictionary.list_all(term="Embrace")
for term in terms:
    print(f"{term.term}: {term.definition}")

# Get a paginated page
page = await dictionary.get_page(limit=20, term="Blood")
print(f"Found {page.total} matching terms")
```

### Iterate Through All Terms

Use memory-efficient iteration for large dictionaries.

```python
async for term in dictionary.iter_all():
    print(f"{term.term}: {term.definition}")
```

## Related Documentation

- [Response Models](models.md) - View `DictionaryTerm` model schema
