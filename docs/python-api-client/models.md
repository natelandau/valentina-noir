---
icon: lucide/database
---

# Response Models

All API responses return as strongly-typed Pydantic models with automatic validation. Import models from `vclient.models` to access request and response types.

```python
from vclient.models import Company, User, Campaign, Character
```

!!! info "Type Safety"
All models provide full type hints for IDE autocomplete and static type checking with mypy or pyright.

## Using Models

Models serve two primary purposes: creating requests and handling responses.

```python
from vclient import users_service
from vclient.models import UserCreate, User

# Create a request model
request = UserCreate(
    name="Alice Johnson",
    email="alice@example.com",
    role="PLAYER",
    requesting_user_id="admin_id"
)

# Send request and receive response model
users = users_service(company_id="company_123")
user: User = await users.create(request)

# Access response data with full type hints
print(f"Created user: {user.name} (ID: {user.id})")
print(f"Role: {user.role}")
```

## Common Models

These models appear across multiple services and provide shared functionality.

### S3Asset

Represents a file stored in cloud storage (AWS S3). Use this model to manage uploaded files like character portraits, campaign handouts, and other assets.

| Field               | Type          | Description                   |
| ------------------- | ------------- | ----------------------------- |
| `id`                | `str`         | Unique identifier             |
| `date_created`      | `datetime`    | Creation timestamp            |
| `date_modified`     | `datetime`    | Last modified timestamp       |
| `file_type`         | `S3AssetType` | File type (image, text, etc.) |
| `original_filename` | `str`         | Original filename             |
| `public_url`        | `str`         | Public URL to access the file |
| `uploaded_by`       | `str`         | ID of uploader                |

### Note

Represents a markdown-formatted note. Store session notes, character backstories, and campaign information with full markdown support.

| Field           | Type       | Description             |
| --------------- | ---------- | ----------------------- |
| `id`            | `str`      | Unique identifier       |
| `date_created`  | `datetime` | Creation timestamp      |
| `date_modified` | `datetime` | Last modified timestamp |
| `title`         | `str`      | Note title              |
| `content`       | `str`      | Note content (markdown) |

### RollStatistics

Aggregated dice roll statistics for a user. Track success rates, critical rolls, botches, and identify patterns in player performance.

| Field                  | Type    | Description              |
| ---------------------- | ------- | ------------------------ |
| `botches`              | `int`   | Total botched rolls      |
| `successes`            | `int`   | Total successful rolls   |
| `failures`             | `int`   | Total failed rolls       |
| `criticals`            | `int`   | Total critical successes |
| `total_rolls`          | `int`   | Total number of rolls    |
| `success_percentage`   | `float` | Success rate             |
| `failure_percentage`   | `float` | Failure rate             |
| `botch_percentage`     | `float` | Botch rate               |
| `criticals_percentage` | `float` | Critical rate            |

### Quickroll

Pre-configured dice pool for frequently used trait combinations. Speed up gameplay by saving common rolls like "Strength + Brawl" or "Wits + Investigation".

| Field           | Type          | Description                |
| --------------- | ------------- | -------------------------- |
| `id`            | `str`         | Unique identifier          |
| `date_created`  | `datetime`    | Creation timestamp         |
| `date_modified` | `datetime`    | Last modified timestamp    |
| `name`          | `str`         | Quickroll name             |
| `description`   | `str \| None` | Optional description       |
| `user_id`       | `str`         | Owner user ID              |
| `trait_ids`     | `list[str]`   | Trait IDs in the dice pool |

## Company Models

### Company

| Field           | Type                      | Description             |
| --------------- | ------------------------- | ----------------------- |
| `id`            | `str`                     | Unique identifier       |
| `date_created`  | `datetime`                | Creation timestamp      |
| `date_modified` | `datetime`                | Last modified timestamp |
| `name`          | `str`                     | Company name            |
| `description`   | `str \| None`             | Company description     |
| `email`         | `str`                     | Contact email           |
| `user_ids`      | `list[str]`               | Associated user IDs     |
| `settings`      | `CompanySettings \| None` | Company configuration   |

### CompanySettings

| Field                           | Type          | Description                    |
| ------------------------------- | ------------- | ------------------------------ |
| `character_autogen_xp_cost`     | `int \| None` | XP cost to autogen (0-100)     |
| `character_autogen_num_choices` | `int \| None` | Number of choices (1-10)       |
| `permission_manage_campaign`    | `str \| None` | Campaign management permission |
| `permission_grant_xp`           | `str \| None` | XP granting permission         |
| `permission_free_trait_changes` | `str \| None` | Free trait changes permission  |

## Developer Models

### Developer

| Field             | Type                               | Description             |
| ----------------- | ---------------------------------- | ----------------------- |
| `id`              | `str`                              | Unique identifier       |
| `date_created`    | `datetime`                         | Creation timestamp      |
| `date_modified`   | `datetime`                         | Last modified timestamp |
| `username`        | `str`                              | Username                |
| `email`           | `str`                              | Email address           |
| `key_generated`   | `datetime \| None`                 | API key generation time |
| `is_global_admin` | `bool`                             | Global admin status     |
| `companies`       | `list[DeveloperCompanyPermission]` | Company permissions     |

### MeDeveloper

Your own developer profile. Contains the same fields as `Developer` but excludes the `is_global_admin` field for security.

### DeveloperWithApiKey

Extends `Developer` with an `api_key` field. Only returned when generating a new API key - save it immediately as it cannot be retrieved again.

## User Models

### User

| Field                 | Type                       | Description                       |
| --------------------- | -------------------------- | --------------------------------- |
| `id`                  | `str`                      | Unique identifier                 |
| `date_created`        | `datetime`                 | Creation timestamp                |
| `date_modified`       | `datetime`                 | Last modified timestamp           |
| `name`                | `str`                      | Display name                      |
| `email`               | `str`                      | Email address                     |
| `role`                | `UserRole \| None`         | Role (ADMIN, STORYTELLER, PLAYER) |
| `company_id`          | `str`                      | Company ID                        |
| `discord_profile`     | `DiscordProfile \| None`   | Discord information               |
| `campaign_experience` | `list[CampaignExperience]` | XP per campaign                   |
| `asset_ids`           | `list[str]`                | Owned asset IDs                   |

### CampaignExperience

| Field         | Type  | Description        |
| ------------- | ----- | ------------------ |
| `campaign_id` | `str` | Campaign ID        |
| `xp_current`  | `int` | Available XP       |
| `xp_total`    | `int` | Lifetime XP earned |
| `cool_points` | `int` | Cool points earned |

### DiscordProfile

| Field         | Type          | Description      |
| ------------- | ------------- | ---------------- |
| `id`          | `str \| None` | Discord user ID  |
| `username`    | `str \| None` | Discord username |
| `global_name` | `str \| None` | Display name     |
| `avatar_url`  | `str \| None` | Avatar URL       |

## Campaign Models

### Campaign

| Field           | Type          | Description             |
| --------------- | ------------- | ----------------------- |
| `id`            | `str`         | Unique identifier       |
| `date_created`  | `datetime`    | Creation timestamp      |
| `date_modified` | `datetime`    | Last modified timestamp |
| `name`          | `str`         | Campaign name           |
| `description`   | `str \| None` | Campaign description    |
| `desperation`   | `int`         | Desperation level (0-5) |
| `danger`        | `int`         | Danger level (0-5)      |
| `company_id`    | `str`         | Company ID              |
| `asset_ids`     | `list[str]`   | Associated asset IDs    |

### CampaignBook

| Field           | Type          | Description             |
| --------------- | ------------- | ----------------------- |
| `id`            | `str`         | Unique identifier       |
| `date_created`  | `datetime`    | Creation timestamp      |
| `date_modified` | `datetime`    | Last modified timestamp |
| `name`          | `str`         | Book name               |
| `description`   | `str \| None` | Book description        |
| `number`        | `int`         | Position in campaign    |
| `campaign_id`   | `str`         | Parent campaign ID      |
| `asset_ids`     | `list[str]`   | Associated asset IDs    |

### CampaignChapter

| Field           | Type          | Description             |
| --------------- | ------------- | ----------------------- |
| `id`            | `str`         | Unique identifier       |
| `date_created`  | `datetime`    | Creation timestamp      |
| `date_modified` | `datetime`    | Last modified timestamp |
| `name`          | `str`         | Chapter name            |
| `description`   | `str \| None` | Chapter description     |
| `number`        | `int`         | Position in book        |
| `book_id`       | `str`         | Parent book ID          |
| `asset_ids`     | `list[str]`   | Associated asset IDs    |

## Character Models

### Character

| Field                 | Type                         | Description                                    |
| --------------------- | ---------------------------- | ---------------------------------------------- |
| `id`                  | `str`                        | Unique identifier                              |
| `date_created`        | `datetime`                   | Creation timestamp                             |
| `date_modified`       | `datetime`                   | Last modified timestamp                        |
| `character_class`     | `CharacterClass`             | VAMPIRE, WEREWOLF, MAGE, HUNTER, GHOUL, MORTAL |
| `type`                | `CharacterType`              | PLAYER, NPC, STORYTELLER, DEVELOPER            |
| `game_version`        | `GameVersion`                | V4 or V5                                       |
| `status`              | `CharacterStatus`            | ALIVE or DEAD                                  |
| `name_first`          | `str`                        | First name                                     |
| `name_last`           | `str`                        | Last name                                      |
| `name_nick`           | `str \| None`                | Nickname                                       |
| `name`                | `str`                        | Display name                                   |
| `name_full`           | `str`                        | Full name                                      |
| `age`                 | `int \| None`                | Age                                            |
| `biography`           | `str \| None`                | Biography                                      |
| `user_creator_id`     | `str`                        | Creator user ID                                |
| `user_player_id`      | `str`                        | Player user ID                                 |
| `company_id`          | `str`                        | Company ID                                     |
| `campaign_id`         | `str`                        | Campaign ID                                    |
| `vampire_attributes`  | `VampireAttributes \| None`  | Vampire-specific data                          |
| `werewolf_attributes` | `WerewolfAttributes \| None` | Werewolf-specific data                         |
| `hunter_attributes`   | `HunterAttributes \| None`   | Hunter-specific data                           |
| `mage_attributes`     | `MageAttributes \| None`     | Mage-specific data                             |

### CharacterTrait

| Field          | Type    | Description         |
| -------------- | ------- | ------------------- |
| `id`           | `str`   | Unique identifier   |
| `character_id` | `str`   | Parent character ID |
| `value`        | `int`   | Current trait value |
| `trait`        | `Trait` | Trait definition    |

### Trait

| Field                  | Type                   | Description             |
| ---------------------- | ---------------------- | ----------------------- |
| `id`                   | `str`                  | Unique identifier       |
| `name`                 | `str`                  | Trait name              |
| `description`          | `str \| None`          | Trait description       |
| `max_value`            | `int`                  | Maximum value           |
| `min_value`            | `int`                  | Minimum value           |
| `is_custom`            | `bool`                 | Whether custom trait    |
| `initial_cost`         | `int`                  | XP cost to acquire      |
| `upgrade_cost`         | `int`                  | XP cost per upgrade     |
| `parent_category_id`   | `str`                  | Parent category ID      |
| `parent_category_name` | `str \| None`          | Parent category name    |
| `game_versions`        | `list[GameVersion]`    | Available game versions |
| `character_classes`    | `list[CharacterClass]` | Applicable classes      |

## Blueprint Models

Blueprint models define the structure and rules for character creation across different game versions and character types.

### SheetSection

Top-level character sheet section. Organizes traits into logical groups like "Attributes", "Skills", or "Disciplines".

| Field               | Type                   | Description                |
| ------------------- | ---------------------- | -------------------------- |
| `id`                | `str`                  | Unique identifier          |
| `name`              | `str`                  | Section name               |
| `description`       | `str \| None`          | Description                |
| `game_versions`     | `list[GameVersion]`    | Available game versions    |
| `character_classes` | `list[CharacterClass]` | Applicable classes         |
| `order`             | `int`                  | Display order              |
| `show_when_empty`   | `bool`                 | Whether to show when empty |

### TraitCategory

Category within a sheet section. Groups related traits together, like "Physical Attributes" or "Social Skills".

| Field                     | Type                   | Description                |
| ------------------------- | ---------------------- | -------------------------- |
| `id`                      | `str`                  | Unique identifier          |
| `name`                    | `str`                  | Category name              |
| `description`             | `str \| None`          | Description                |
| `game_versions`           | `list[GameVersion]`    | Available game versions    |
| `parent_sheet_section_id` | `str`                  | Parent section ID          |
| `initial_cost`            | `int`                  | XP cost to acquire         |
| `upgrade_cost`            | `int`                  | XP cost per upgrade        |
| `show_when_empty`         | `bool`                 | Whether to show when empty |
| `character_classes`       | `list[CharacterClass]` | Applicable classes         |
| `order`                   | `int`                  | Display order              |

### CharacterConcept

| Field             | Type          | Description             |
| ----------------- | ------------- | ----------------------- |
| `id`              | `str`         | Unique identifier       |
| `name`            | `str`         | Concept name            |
| `description`     | `str \| None` | Description             |
| `examples`        | `list[str]`   | Example concepts        |
| `max_specialties` | `int`         | Max specialties allowed |

## Vampire Models

### VampireAttributes

| Field        | Type          | Description |
| ------------ | ------------- | ----------- |
| `clan_id`    | `str \| None` | Clan ID     |
| `clan_name`  | `str \| None` | Clan name   |
| `generation` | `int \| None` | Generation  |
| `sire`       | `str \| None` | Sire name   |

### VampireClan

| Field           | Type                | Description             |
| --------------- | ------------------- | ----------------------- |
| `id`            | `str`               | Unique identifier       |
| `name`          | `str`               | Clan name               |
| `description`   | `str \| None`       | Description             |
| `game_versions` | `list[GameVersion]` | Available game versions |

## Werewolf Models

### WerewolfAttributes

| Field          | Type          | Description  |
| -------------- | ------------- | ------------ |
| `tribe_id`     | `str \| None` | Tribe ID     |
| `tribe_name`   | `str \| None` | Tribe name   |
| `auspice_id`   | `str \| None` | Auspice ID   |
| `auspice_name` | `str \| None` | Auspice name |
| `pack_name`    | `str \| None` | Pack name    |

### WerewolfTribe

| Field           | Type                | Description             |
| --------------- | ------------------- | ----------------------- |
| `id`            | `str`               | Unique identifier       |
| `name`          | `str`               | Tribe name              |
| `description`   | `str \| None`       | Description             |
| `game_versions` | `list[GameVersion]` | Available game versions |
| `renown`        | `WerewolfRenown`    | HONOR, GLORY, or WISDOM |
| `gift_ids`      | `list[str]`         | Native gift IDs         |
| `link`          | `str \| None`       | Link to tribe page      |
| `patron_spirit` | `str \| None`       | Patron spirit name      |
| `favor`         | `str \| None`       | Favor name              |
| `ban`           | `str \| None`       | Ban name                |

### WerewolfAuspice

| Field           | Type                | Description             |
| --------------- | ------------------- | ----------------------- |
| `id`            | `str`               | Unique identifier       |
| `name`          | `str`               | Auspice name            |
| `description`   | `str \| None`       | Description             |
| `game_versions` | `list[GameVersion]` | Available game versions |
| `gift_ids`      | `list[str]`         | Native gift IDs         |
| `link`          | `str \| None`       | Link to auspice page    |

### WerewolfGift

| Field            | Type                | Description             |
| ---------------- | ------------------- | ----------------------- |
| `id`             | `str`               | Unique identifier       |
| `name`           | `str`               | Gift name               |
| `description`    | `str \| None`       | Description             |
| `game_versions`  | `list[GameVersion]` | Available game versions |
| `renown`         | `WerewolfRenown`    | HONOR, GLORY, or WISDOM |
| `cost`           | `str \| None`       | Activation cost         |
| `minimum_renown` | `int \| None`       | Required renown level   |

### WerewolfRite

| Field           | Type                | Description             |
| --------------- | ------------------- | ----------------------- |
| `id`            | `str`               | Unique identifier       |
| `name`          | `str`               | Rite name               |
| `description`   | `str \| None`       | Description             |
| `game_versions` | `list[GameVersion]` | Available game versions |
| `pool`          | `str \| None`       | Dice pool               |

## Hunter Models

### HunterAttributes

| Field   | Type               | Description  |
| ------- | ------------------ | ------------ |
| `creed` | `str \| None`      | Hunter creed |
| `edges` | `list[HunterEdge]` | Hunter edges |

### HunterEdge

| Field           | Type                     | Description                      |
| --------------- | ------------------------ | -------------------------------- |
| `id`            | `str`                    | Unique identifier                |
| `name`          | `str`                    | Edge name                        |
| `description`   | `str \| None`            | Description                      |
| `type`          | `HunterEdgeType \| None` | ASSETS, APTITUDES, or ENDOWMENTS |
| `pool`          | `str \| None`            | Dice pool                        |
| `system`        | `str \| None`            | System rules                     |
| `game_versions` | `list[GameVersion]`      | Available game versions          |
| `perk_ids`      | `list[str]`              | Perk IDs                         |

### HunterEdgePerk

| Field           | Type                | Description             |
| --------------- | ------------------- | ----------------------- |
| `id`            | `str`               | Unique identifier       |
| `name`          | `str`               | Perk name               |
| `description`   | `str \| None`       | Description             |
| `game_versions` | `list[GameVersion]` | Available game versions |
| `edge_id`       | `str \| None`       | Parent Edge ID          |

## Dice Roll Models

### DiceRoll

| Field                  | Type             | Description        |
| ---------------------- | ---------------- | ------------------ |
| `id`                   | `str`            | Unique identifier  |
| `date_created`         | `datetime`       | Creation timestamp |
| `dice_size`            | `DiceSize`       | Dice size          |
| `difficulty`           | `int \| None`    | Target difficulty  |
| `num_dice`             | `int`            | Number of dice     |
| `num_desperation_dice` | `int`            | Desperation dice   |
| `comment`              | `str \| None`    | Roll comment       |
| `trait_ids`            | `list[str]`      | Traits used        |
| `user_id`              | `str \| None`    | User ID            |
| `character_id`         | `str \| None`    | Character ID       |
| `campaign_id`          | `str \| None`    | Campaign ID        |
| `result`               | `DiceRollResult` | Roll result        |

### DiceRollResult

| Field                    | Type             | Description             |
| ------------------------ | ---------------- | ----------------------- |
| `total_result`           | `int \| None`    | Total successes         |
| `total_result_type`      | `RollResultType` | Result type             |
| `total_result_humanized` | `str \| None`    | Human-readable result   |
| `total_dice_roll`        | `list[int]`      | All dice values         |
| `player_roll`            | `list[int]`      | Player dice values      |
| `desperation_roll`       | `list[int]`      | Desperation dice values |

## Dictionary Models

### DictionaryTerm

| Field           | Type          | Description             |
| --------------- | ------------- | ----------------------- |
| `id`            | `str`         | Unique identifier       |
| `date_created`  | `datetime`    | Creation timestamp      |
| `date_modified` | `datetime`    | Last modified timestamp |
| `term`          | `str`         | Term name               |
| `definition`    | `str \| None` | Definition              |
| `link`          | `str \| None` | Reference link          |
| `synonyms`      | `list[str]`   | Synonyms                |

## Enumerations

### Character Enums

| Enum              | Values                                         |
| ----------------- | ---------------------------------------------- |
| `CharacterClass`  | VAMPIRE, WEREWOLF, MAGE, HUNTER, GHOUL, MORTAL |
| `CharacterType`   | PLAYER, NPC, STORYTELLER, DEVELOPER            |
| `CharacterStatus` | ALIVE, DEAD                                    |
| `GameVersion`     | V4, V5                                         |

### User Enums

| Enum              | Values                     |
| ----------------- | -------------------------- |
| `UserRole`        | ADMIN, STORYTELLER, PLAYER |
| `PermissionLevel` | USER, ADMIN, OWNER, REVOKE |

### Other Enums

| Enum             | Values                            |
| ---------------- | --------------------------------- |
| `WerewolfRenown` | HONOR, GLORY, WISDOM              |
| `HunterEdgeType` | ASSETS, APTITUDES, ENDOWMENTS     |
| `DiceSize`       | D4, D6, D8, D10, D12, D20         |
| `RollResultType` | SUCCESS, FAILURE, BOTCH, CRITICAL |
