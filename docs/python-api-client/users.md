---
icon: lucide/users
---

# Users Service

Manage users within a company, including their experience points, assets, notes, and quickrolls. This service provides comprehensive user management for World of Darkness campaigns.

## Initialize the Service

```python
from vclient import users_service

users = users_service(company_id="COMPANY_ID")
```

## Available Methods

### CRUD Operations

| Method                                          | Returns | Description                  |
| ----------------------------------------------- | ------- | ---------------------------- |
| `get(user_id)`                                  | `User`  | Retrieve a user by ID        |
| `create(request=None, **kwargs)`             | `User`  | Create a new user            |
| `update(user_id, request=None, **kwargs)`    | `User`  | Update user properties       |
| `delete(user_id, requesting_user_id)`           | `None`  | Delete a user                |

### Pagination Methods

| Method                                           | Returns                   | Description                       |
| ------------------------------------------------ | ------------------------- | --------------------------------- |
| `get_page(user_role=None, limit=10, offset=0)`   | `PaginatedResponse[User]` | Retrieve a paginated page         |
| `list_all(user_role=None)`                       | `list[User]`              | Retrieve all users                |
| `iter_all(user_role=None, limit=100)`            | `AsyncIterator[User]`     | Iterate through all users         |

### Statistics

| Method                                          | Returns          | Description                       |
| ----------------------------------------------- | ---------------- | --------------------------------- |
| `get_statistics(user_id, num_top_traits=5)`     | `RollStatistics` | Retrieve aggregated roll stats    |

### Experience Management

| Method                                                              | Returns              | Description                    |
| ------------------------------------------------------------------- | -------------------- | ------------------------------ |
| `get_experience(user_id, campaign_id)`                              | `CampaignExperience` | Retrieve XP and cool points    |
| `add_xp(user_id, campaign_id, amount, requesting_user_id)`          | `CampaignExperience` | Award experience points        |
| `remove_xp(user_id, campaign_id, amount, requesting_user_id)`       | `CampaignExperience` | Deduct experience points       |
| `add_cool_points(user_id, campaign_id, amount, requesting_user_id)` | `CampaignExperience` | Award cool points              |

### Asset Management

| Method                                                      | Returns                      | Description                  |
| ----------------------------------------------------------- | ---------------------------- | ---------------------------- |
| `list_assets(user_id, limit=10, offset=0)`                  | `PaginatedResponse[S3Asset]` | List user's assets           |
| `get_asset(user_id, asset_id)`                              | `S3Asset`                    | Retrieve an asset by ID      |
| `upload_asset(user_id, filename, content, content_type)`    | `S3Asset`                    | Upload a new file            |
| `delete_asset(user_id, asset_id)`                           | `None`                       | Delete an asset              |

### Notes Management

| Method                                                      | Returns                   | Description                    |
| ----------------------------------------------------------- | ------------------------- | ------------------------------ |
| `get_notes_page(user_id, limit=10, offset=0)`               | `PaginatedResponse[Note]` | Retrieve a paginated page      |
| `list_all_notes(user_id)`                                   | `list[Note]`              | Retrieve all notes             |
| `iter_all_notes(user_id, limit=100)`                        | `AsyncIterator[Note]`     | Iterate through all notes      |
| `get_note(user_id, note_id)`                                | `Note`                    | Retrieve a note by ID          |
| `create_note(user_id, request=None, **kwargs)`           | `Note`                    | Create a new note              |
| `update_note(user_id, note_id, request=None, **kwargs)`  | `Note`                    | Update note content            |
| `delete_note(user_id, note_id)`                             | `None`                    | Delete a note                  |

### Quickrolls Management

| Method                                                              | Returns                       | Description                      |
| ------------------------------------------------------------------- | ----------------------------- | -------------------------------- |
| `get_quickrolls_page(user_id, limit=10, offset=0)`                  | `PaginatedResponse[Quickroll]`| Retrieve a paginated page        |
| `list_all_quickrolls(user_id)`                                      | `list[Quickroll]`             | Retrieve all quickrolls          |
| `iter_all_quickrolls(user_id, limit=100)`                           | `AsyncIterator[Quickroll]`    | Iterate through all quickrolls   |
| `get_quickroll(user_id, quickroll_id)`                              | `Quickroll`                   | Retrieve a quickroll by ID       |
| `create_quickroll(user_id, request=None, **kwargs)`              | `Quickroll`                   | Create a new quickroll           |
| `update_quickroll(user_id, quickroll_id, request=None, **kwargs)`| `Quickroll`                   | Update quickroll configuration   |
| `delete_quickroll(user_id, quickroll_id)`                           | `None`                        | Delete a quickroll               |

## User Roles

| Role          | Description                            |
| ------------- | -------------------------------------- |
| `ADMIN`       | Full administrative access to company  |
| `STORYTELLER` | Game master role with elevated access  |
| `PLAYER`      | Standard player with limited access    |

## Examples

### Create a User

Add a new user to the company.

```python
from vclient.models import UserCreate

# Option 1: Use a model object (preferred)
request = UserCreate(
    name="John Doe",
    email="john@example.com",
    role="PLAYER",
    requesting_user_id="admin_user_id"
)
user = await users.create(request)

# Option 2: Pass fields as keyword arguments
user = await users.create(
    name="John Doe",
    email="john@example.com",
    role="PLAYER",
    requesting_user_id="admin_user_id"
)
```

### Manage Experience Points

Award or deduct experience points for character progression.

```python
# Get current experience
experience = await users.get_experience(user.id, campaign_id)
print(f"Current XP: {experience.xp_current}")
print(f"Total earned: {experience.xp_total}")

# Award XP (requesting_user_id for permission checking)
updated = await users.add_xp(
    user.id, campaign_id, amount=50, requesting_user_id=admin.id
)
print(f"New XP: {updated.xp_current}")

# Award cool points (converted to XP automatically)
updated = await users.add_cool_points(
    user.id, campaign_id, amount=3, requesting_user_id=admin.id
)

# Deduct XP for character upgrades
updated = await users.remove_xp(
    user.id, campaign_id, amount=20, requesting_user_id=admin.id
)
```

### Create and Manage Notes

Store session notes and character information.

```python
from vclient.models import NoteCreate, NoteUpdate

# Create a note with markdown content
note_request = NoteCreate(
    title="Session 12 Notes",
    content="## Key Events\n\n- Met the Prince\n- Discovered betrayal"
)
note = await users.create_note(user.id, note_request)

# Update note content
update = NoteUpdate(content="Updated content here...")
updated = await users.update_note(user.id, note.id, update)

# List all notes
notes = await users.list_all_notes(user.id)
for note in notes:
    print(f"{note.title}: {len(note.content)} characters")
```

### Create Quickrolls

Set up pre-configured dice pools for common actions.

```python
from vclient.models import QuickrollCreate

# Create a quickroll for a common dice pool
quickroll_request = QuickrollCreate(
    name="Strength + Brawl",
    description="Melee combat attack",
    trait_ids=["trait_strength_id", "trait_brawl_id"]
)
quickroll = await users.create_quickroll(user.id, quickroll_request)

# List all quickrolls
quickrolls = await users.list_all_quickrolls(user.id)
for qr in quickrolls:
    print(f"{qr.name}: {len(qr.trait_ids)} traits")
```

### Upload and Manage Assets

Store character portraits, handouts, and other files.

```python
# Upload a character portrait
with open("portrait.jpg", "rb") as f:
    content = f.read()

asset = await users.upload_asset(
    user.id,
    filename="john_doe_portrait.jpg",
    content=content,
    content_type="image/jpeg"
)
print(f"Asset URL: {asset.public_url}")

# List all assets
assets_page = await users.list_assets(user.id, limit=20)
for asset in assets_page.data:
    print(f"{asset.original_filename}: {asset.file_type}")

# Delete an asset
await users.delete_asset(user.id, asset.id)
```

### Get Roll Statistics

View aggregated dice roll statistics for a user.

```python
stats = await users.get_statistics(user.id, num_top_traits=10)

print(f"Total rolls: {stats.total_rolls}")
print(f"Success rate: {stats.success_percentage:.1f}%")
print(f"Critical rate: {stats.criticals_percentage:.1f}%")
print(f"Botch rate: {stats.botch_percentage:.1f}%")
```

### Filter Users by Role

Retrieve users filtered by their role in the company.

```python
from vclient.constants import UserRole

# Get all storytellers
storytellers = await users.list_all(user_role=UserRole.STORYTELLER)

# Get paginated list of players
players_page = await users.get_page(user_role=UserRole.PLAYER, limit=25)
print(f"Total players: {players_page.total}")
```

## Related Documentation

- [Response Models](models.md) - View `User`, `CampaignExperience`, `S3Asset`, `Note`, and `Quickroll` model schemas
