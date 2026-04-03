# PostgreSQL Integration Guide

Living document describing how the PostgreSQL-based architecture is structured.

## Database Setup

- PostgreSQL 18 runs in Docker (`compose-db.yml`)
- TortoiseORM (asyncpg backend) connects via `lib/postgres_database.py`
- `TortoisePlugin` in `server/tortoise_plugin.py` manages lifecycle in the Litestar app
- Configuration in `config/base.py` → `PostgresSettings`

## Bootstrap

The database is seeded by a single command: `duty bootstrap` / `uv run app bootstrap`.

**Flow:**

1. `_bootstrap_all()` initializes Tortoise and calls `pg_bootstrap_async()`
2. `pg_bootstrap_async()` orchestrates all PG syncers in dependency order

**Bootstrap order:**

1. `PgTraitSyncer().sync()` — sections → categories → subcategories → traits
2. `PgVampireClanSyncer().sync()` — clans + discipline M2M linking
3. `PgWerewolfAuspiceSyncer().sync()`
4. `PgWerewolfTribeSyncer().sync()`
5. `pg_resolve_gift_trait_references()` — resolves tribe/auspice FKs on gift traits + M2M
6. `PgCharacterConceptSyncer().sync()`
7. `PgDictionaryService().sync_all()` — generates dictionary terms from all entities

**Syncer code lives in:** `src/vapi/cli/lib/pg/`

- `__init__.py` — `SyncCounts` dataclass (shared by all syncers)
- `fixture_syncer.py` — `PgFixtureSyncer` base + `PgVampireClanSyncer`, `PgWerewolfAuspiceSyncer`, `PgWerewolfTribeSyncer`, `PgCharacterConceptSyncer`
- `trait_syncer.py` — `PgTraitSyncer`, `pg_resolve_gift_trait_references`, `_build_gift_fixture_map`
- `dictionary.py` — `PgDictionaryService`

## Test Infrastructure

### Session-scoped setup (runs once per test session)

In `tests/conftest.py`:

- `init_test_postgres` — creates test database, initializes Tortoise, generates schemas, runs `pg_bootstrap_async()` to seed constant data

The database is fully seeded before any tests run.

### Constant data (preserved across tests)

These tables are seeded by bootstrap and **never cleaned** between tests:

- `char_sheet_section`, `trait_category`, `trait_subcategory`, `trait`
- `vampire_clan`, `werewolf_auspice`, `werewolf_tribe`
- `character_concept`, `dictionary_term`
- M2M junction tables: `vampire_clan_disciplines`, `werewolf_auspice_gifts`, `werewolf_tribe_gifts`

### Non-constant data (cleaned after every test)

The `cleanup_database` fixture (autouse) runs `DELETE FROM` on all non-constant tables after every test. This prevents data leaks between tests. Uses DELETE (not TRUNCATE CASCADE) to avoid cascading into constant tables that have nullable FK relationships.

Tables cleaned: `audit_log`, `campaign`, `campaign_book`, `campaign_chapter`, `character`, `character_trait`, `character_inventory`, `specialty`, `vampire_attributes`, `werewolf_attributes`, `mage_attributes`, `hunter_attributes`, `campaign_experience`, `company_settings`, `developer_company_permission`, `developer`, `"user"` (quoted — reserved word), `company`, `dice_roll`, `dice_roll_result`, `quick_roll`, `note`, `s3_asset`, `chargen_session`, `chargen_session_characters`

### Bootstrap tests

`tests/integration/cli/pg/test_pg_bootstrap.py` — 26 tests that verify the pre-seeded data is correct. They do NOT re-run bootstrap (except the idempotency test). Organized by domain:

- `TestPgTraitBootstrap` — sections, categories, subcategories, traits, gift traits
- `TestPgVampireClanBootstrap` — clans, field matching, discipline M2M
- `TestPgWerewolfBootstrap` — auspices, tribes, field matching, gift M2M
- `TestPgCharacterConceptBootstrap` — concepts, field matching
- `TestPgDictionaryBootstrap` — dictionary terms, source types, lowercase
- `TestPgBootstrapIdempotency` — runs bootstrap again, verifies no duplicates

### Model validators

`src/vapi/db/sql_models/validators.py` has `validate_character_classes` and `validate_game_versions` — field-level validators on all models with `character_classes` or `game_versions` ArrayField columns. Tested in `tests/unit/db/sql_models/test_validators.py`.

### Test factories for Tortoise models

`tests/fixture_models.py` — Tortoise test factories registered as a pytest plugin in `conftest.py`.

Factories that create constant data (traits, concepts) use the yield + cleanup pattern to avoid polluting bootstrap data:

```python
@pytest.fixture
async def trait_factory():
    created: list[Trait] = []
    async def _factory(**kwargs) -> Trait:
        ...
        trait = await Trait.create(**defaults)
        created.append(trait)
        return trait
    yield _factory
    for trait in created:
        await trait.delete()
```

Available factories:

- `trait_factory` — creates Tortoise `Trait` instances, auto-populates `category` and `sheet_section` if not provided
- `character_concept_factory` — creates Tortoise `CharacterConcept` instances
- `dictionary_term_factory` — creates Tortoise `DictionaryTerm` instances, self-cleaning (constant table)
- `developer_factory` — creates Tortoise `Developer` instances, supports `is_global_admin`, auto-cleaned
- `developer_company_permission_factory` — creates `DeveloperCompanyPermission` rows, auto-cleaned
- `user_factory` — creates Tortoise `User` instances, auto-cleaned
- `campaign_factory` — creates Tortoise `Campaign` instances (for FK resolution in experience tests), auto-cleaned
- `campaign_book_factory` — creates Tortoise `CampaignBook` instances, auto-assigns number
- `campaign_chapter_factory` — creates Tortoise `CampaignChapter` instances, auto-assigns number
- `campaign_experience_factory` — creates Tortoise `CampaignExperience` instances, auto-cleaned
- `company_factory` — creates Tortoise `Company` instances; auto-creates a `CompanySettings` row (since `CompanySettings` is a separate table in PostgreSQL, unlike the previous embedded subdocument approach)
- `character_factory` — creates Tortoise `Character` instances; auto-creates a `User` and `Campaign` if not provided; `company` kwarg is required
- `character_inventory_factory` — creates Tortoise `CharacterInventory` instances
- `specialty_factory` — creates Tortoise `Specialty` instances
- `character_trait_factory` — creates Tortoise `CharacterTrait` instances with prefetched trait relations
- `vampire_attributes_factory` — creates Tortoise `VampireAttributes` OneToOne instances
- `werewolf_attributes_factory` — creates Tortoise `WerewolfAttributes` OneToOne instances
- `chargen_session_factory` — creates Tortoise `ChargenSession` instances with auto-created user/company/campaign, self-cleaning
- `quickroll_factory` — creates Tortoise `QuickRoll` instances, auto-cleaned
- `note_factory` — creates Tortoise `Note` instances, supports all parent FK fields (character, campaign, book, chapter, user), auto-cleaned
- `diceroll_factory` — creates Tortoise `DiceRoll` and `DiceRollResult` instances together, auto-cleaned
- `s3asset_factory` — creates Tortoise `S3Asset` instances, supports all parent FK fields (character, campaign, book, chapter, user), auto-cleaned

Non-constant data factories (companies, users, characters, etc.) don't need self-cleanup because `cleanup_database` handles those tables.

## Auth Middleware

Auth middleware uses Tortoise `Developer` model for verification and a `CachedDeveloper` msgspec Struct for Redis caching.

- `connection.user` is a `CachedDeveloper` Struct with `id: UUID` and `is_global_admin: bool`
- Redis cache uses `msgspec.json.encode/decode` for serialization
- `DeveloperService.verify_api_key()` handles API key verification
- JWT and basic auth middleware follow the same pattern: deserialize to `CachedDeveloper` Struct from cache or query Tortoise on cache miss

Guards read `.id` and `.is_global_admin` from the `CachedDeveloper` Struct.

## After-Response Hooks

`after_response_hooks.py` uses Tortoise throughout:

- `add_audit_log` creates Tortoise `AuditLog` records via `.create()`
- `post_data_update_hook` queries Tortoise `Company` to resolve the company name for the audit log

## Archive Handlers

`archive_handlers.py` uses Tortoise throughout:

- `archive_s3_assets` takes `fk_field: str` and `object_ids: list[UUID]`. Callers pass the FK field name as a string (e.g., `"character_id"`) and a list of UUIDs to archive
- All handler classes (`CampaignArchiveHandler`, `CharacterArchiveHandler`, `UserArchiveHandler`, etc.) accept Tortoise model instances
- `archive_user_cascade` accepts `UUID`
- Cascade archival of Character, CharacterTrait, CharacterInventory, Specialty, and Attribute rows is handled via Tortoise bulk updates

## CLI

CLI modules use Tortoise models throughout:

- `developer.py`, `development.py`, and `population.py` all use Tortoise models for database operations
- `PopulationService` uses `Developer.create()`, `Company.create()`, etc.
- The `purge_db` CLI command purges all PostgreSQL tables via `Tortoise.execute_script()`

## Tortoise Models

All models in `src/vapi/db/sql_models/`. Key patterns:

- `BaseModel` — abstract base with UUID v7 PK, timestamps, archive fields
- FK relationships use `fields.ForeignKeyField` with explicit `related_name` and `on_delete`
- M2M uses `fields.ManyToManyField` with explicit `through` table names
- `pre_save` signals in `signals.py` handle slugification and term normalization
- `character_classes` and `game_versions` use `ArrayField(element_type="text")` from `tortoise.contrib.postgres.fields` — PostgreSQL-native `TEXT[]` columns with `@>` containment queries. Validators in `validators.py` enforce enum membership at save time

## DTO Strategy: msgspec Structs

Established in Session 3.5. All API response DTOs are hand-crafted `msgspec.Struct` classes with `from_model()` classmethods for converting Tortoise model instances.

**Pattern:**

- Each entity type gets a `*Response` Struct in its controller's `dto.py`
- Structs define the exact API response shape — field names match the pre-migration API
- Where Tortoise FK names differ from the API (e.g., `category_id` vs `parent_category_id`), `from_model()` handles the mapping
- **FK ID access:** Tortoise dynamically creates `_id` suffixed attributes for FK fields (e.g., `m.category_id`), but mypy doesn't know about them. When the relation is prefetched (required by the `from_model()` contract), access the ID via the related object: `m.category.id`. For FK fields that are NOT prefetched (e.g., `company_id` on `DictionaryTerm`), use `m.company_id` with `# type: ignore[attr-defined]`
- Litestar serializes Structs natively — no `return_dto` wrapper needed on `@get()` decorators
- Nested Structs (`GiftAttributesResponse`, `NameDescriptionResponse`) handle embedded data

**Conversion boundary:** Services return Tortoise model instances. Controllers convert to Structs before returning. This keeps services ORM-focused and framework-agnostic.

**Request DTOs (CRUD domains):** For domains with write operations (POST/PATCH), define separate `*Create` and `*Patch` Structs. Create Structs list required and optional fields with defaults. Patch Structs use `msgspec.UNSET` as default for all fields to distinguish "not sent" from "sent as null." The controller checks `isinstance(data.field, msgspec.UnsetType)` before applying each field.

## Do Not Use `from __future__ import annotations` in Litestar Files

Litestar resolves type hints at runtime via `get_type_hints()` for handler signatures, dependency providers, and return types. `from __future__ import annotations` makes all annotations lazy strings, which breaks this resolution and forces imports out of `TYPE_CHECKING` with `# noqa: TC002` suppressions.

**Rule:** Do not use `from __future__ import annotations` in:

- Controller files (`domain/controllers/**/controllers.py`)
- Dependency provider files (`domain/deps.py`)
- Any file where types appear in Litestar handler signatures or `Provide()` return types

Without the future import, annotations evaluate at definition time, ruff's TC rules work correctly, and no noqa suppressions are needed. Use string quotes for forward references if needed (rare in controllers).

## Dependency Providers

`domain/deps.py` — Tortoise-based dependency providers for all domains.

`deps.py` has its own `_find_or_404` helper using `model.filter(id=..., is_archived=False).first()`. Providers that return models used in Struct conversion prefetch related objects for `@property` name fields and M2M ID lists.

### Guards

`lib/guards.py` — Tortoise-based authorization guards for checking company membership and permissions.

Guards query the `DeveloperCompanyPermission` table directly instead of iterating through `Developer.companies`. Guards read `.id` and `.is_global_admin` from the authenticated developer (`CachedDeveloper` Struct).

`user_character_player_or_storyteller_guard` — checks that the authenticated user is the character's owner (player) or a storyteller for the character's campaign.

`user_storyteller_guard` — for the chargen autogenerate route. Queries the `User` table to check role, matching the pattern of `user_not_unapproved_guard`.

## DeveloperService

`DeveloperService` — centralized service for API key generation and verification. Used by controllers for developer CRUD operations.

## Character Domain

### OneToOne attribute pattern

`VampireAttributes`, `WerewolfAttributes`, `MageAttributes`, and `HunterAttributes` are each separate Tortoise models with a `OneToOneField` pointing to `Character`. Attribute rows are created on-demand (when a character's type is set), not at character creation time. Access is via `await character.vampire_attributes` (returns `None` if the row does not exist).

## DiceRollResult

`DiceRollResult` is a OneToOne model with a `OneToOneField` pointing to `DiceRoll`. It stores the structured outcome of a dice roll: `total_result`, `total_result_type`, `total_result_humanized`, `total_dice_roll`, `player_roll`, `desperation_roll`, plus computed emoji/shortcode fields.

The `DiceRoll` model itself holds the roll parameters (pool size, difficulty, roll type, etc.) while `DiceRollResult` holds the computed outcome. They are created together atomically — no `DiceRoll` row exists without a corresponding `DiceRollResult` row.

Access via `await dice_roll.result` (returns the `DiceRollResult` instance). The `DiceRollResponse.from_model()` classmethod expects the result to be prefetched.

## S3Asset Normalized FKs

`S3Asset` uses five explicit nullable FK fields instead of a `parent_type`/`parent_id` polymorphic pair:

- `character` — FK to `Character`, nullable
- `campaign` — FK to `Campaign`, nullable
- `book` — FK to `CampaignBook`, nullable
- `chapter` — FK to `CampaignChapter`, nullable
- `user_parent` — FK to `User`, nullable (named `user_parent` to avoid conflict with `user` reserved word)

Exactly one of these FKs is non-null per asset row. Services use keyword arguments to set the appropriate FK when creating assets. The `S3AssetResponse.from_model()` classmethod reads the `_id` suffix attributes to populate the nullable ID fields in the response.

## Character Generation Domain

### Transaction wrapping

`CharacterAutogenerationHandler.generate_character()` wraps the entire character creation flow in `in_transaction()`. This ensures atomicity — if any step fails, the entire character (including all traits, attributes, etc.) is rolled back.

### OneToOne attribute creation

The handler creates `VampireAttributes`, `WerewolfAttributes`, and `HunterAttributes` as separate table rows via `.create()` instead of embedding them as subdocuments on the Character. Attributes are created on-demand within the transaction.

### `CHARGEN_SESSION_PREFETCH`

Module-level constant in the chargen controller for nested prefetching of characters and their relations (vampire_attributes, werewolf_attributes, concept, specialties, etc.).

## Character Traits Domain

### Derived-trait sync constants

Module-level constants in `character_trait_svc.py` centralize the trait names used for derived-trait calculations:

- `WILLPOWER_COMPONENTS = frozenset({"Composure", "Resolve", "Courage"})` — traits that contribute to Willpower
- `WILLPOWER_TRAIT = "Willpower"` — the derived trait name
- `RENOWN_COMPONENTS = frozenset({"Honor", "Wisdom", "Glory"})` — traits that contribute to total renown

### `after_save` signature change

The service's `after_save()` method takes `(character_trait, character)` instead of just `(character_trait)`. The willpower and renown sync methods now take `Character` directly since they query by character, not by individual trait.

### `_guard_permissions_free_trait_changes` is now async

This method queries `CompanySettings` from PostgreSQL. All call sites must `await` it.

### `character_create_trait_to_character_traits()` sync

The method in `character_svc.py` calls `CharacterTraitService.after_save()` after `bulk_create()` to sync willpower and total renown.

### UserXPService for XP operations

The service uses `UserXPService` (from `user_svc.py`) for `add_xp()`, `spend_xp()`, and `get_or_create_campaign_experience()`.

## Supporting Entities Domain

### Utils

`domain/utils.py` uses Tortoise ORM throughout. The `get_user_by_id()` and `get_character_by_id()` helpers query PostgreSQL. All UUID-based lookups go directly to Tortoise.

### Scheduled tasks

The `collect_quickroll_stats()` and `collect_diceroll_stats()` scheduled tasks query Tortoise `QuickRoll` and `DiceRoll` models respectively. The task functions live in `lib/scheduled_tasks.py`.

### `AssetParentType` removal

The `AssetParentType` enum (previously used as the `parent_type` discriminator on S3Asset) was removed. All code that previously checked `asset.parent_type` now null-checks the individual FK ID fields on the response DTO (`character_id`, `campaign_id`, `book_id`, `chapter_id`, `user_parent_id`).

## Migration Status

| Session | Status   | Description                                      |
| ------- | -------- | ------------------------------------------------ |
| 1       | Complete | Dual database infrastructure                     |
| 2       | Complete | All Tortoise model definitions                   |
| 3       | Complete | Bootstrap constants into PostgreSQL              |
| 3.5     | Complete | Migrate character blueprint domain to PostgreSQL |
| 4       | Complete | Constants domain migration (dictionary)          |
| 5       | Complete | Company and Developer domain migration           |
| 6       | Complete | User domain migration                            |
| 7       | Complete | Campaign domain migration                        |
| 8       | Complete | Character domain migration                       |
| 8.5     | Complete | Character traits domain migration                |
| 9       | Complete | Character generation domain migration            |
| 9.5     | Complete | Supporting entities domain migration             |
| 10      | Complete | Handlers, DI, middleware, CLI cleanup            |
| 11      | Complete | Remove MongoDB                                   |
| 12      | Complete | Post-migration cleanup                           |
