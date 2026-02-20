---
icon: lucide/building-2
---

# Companies Service

Manage companies and developer access permissions.

## Usage

```python
from vclient import companies_service

companies = companies_service()
```

## Methods

### CRUD Operations

| Method                                        | Returns              | Description          |
| --------------------------------------------- | -------------------- | -------------------- |
| `get(company_id)`                             | `Company`            | Get a company by ID  |
| `create(CompanyCreate, **kwargs)`             | `NewCompanyResponse` | Create a new company |
| `update(company_id, CompanyUpdate, **kwargs)` | `Company`            | Update a company     |
| `delete(company_id)`                          | `None`               | Delete a company     |

### Pagination

| Method                      | Returns                      | Description                   |
| --------------------------- | ---------------------------- | ----------------------------- |
| `get_page(limit?, offset?)` | `PaginatedResponse[Company]` | Get a page of companies       |
| `list_all()`                | `list[Company]`              | Get all companies             |
| `iter_all(limit?)`          | `AsyncIterator[Company]`     | Iterate through all companies |

### Permissions

| Method                                               | Returns              | Description                               |
| ---------------------------------------------------- | -------------------- | ----------------------------------------- |
| `grant_access(company_id, developer_id, permission)` | `CompanyPermissions` | Grant, modify, or revoke developer access |

## Permission Levels

| Level    | Description                                 |
| -------- | ------------------------------------------- |
| `USER`   | View company data                           |
| `ADMIN`  | Modify company settings and data            |
| `OWNER`  | Full control including managing permissions |
| `REVOKE` | Remove all access                           |

!!! warning "Permission Considerations"

    Only company owners can grant or revoke permissions. You cannot revoke access from the last remaining owner of a company.

## Example

```python
from vclient.models import CompanyCreate, CompanyUpdate

# Create a company (preferred method: use model object)
request = CompanyCreate(
    name="Dark Haven Games",
    email="contact@darkhaven.com"
)
result = await companies.create(request)
company = result.company
admin_user = result.admin_user

# Alternative: pass fields as keyword arguments
result = await companies.create(
    name="Dark Haven Games",
    email="contact@darkhaven.com"
)

# Update company details
update = CompanyUpdate(name="Dark Haven Gaming")
updated = await companies.update(company.id, update)

# Grant admin access to another developer
permissions = await companies.grant_access(
    company_id=company.id,
    developer_id="507f1f77bcf86cd799439012",
    permission="ADMIN"
)
print(f"Granted {permissions.permission} access")
```

See [Response Models](models.md) for `Company`, `CompanySettings`, and related types.
