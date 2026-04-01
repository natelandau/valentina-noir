# PostgreSQL Integration Guide

Living document tracking how the PostgreSQL migration is structured. Update this as each session progresses.

## Database Setup

- PostgreSQL 18 runs alongside MongoDB in Docker (`compose-db.yml`)
- TortoiseORM (asyncpg backend) connects via `lib/postgres_database.py`
- `TortoisePlugin` in `server/tortoise_plugin.py` manages lifecycle in the Litestar app
- Configuration in `config/base.py` → `PostgresSettings`

## Bootstrap

Both databases are seeded by a single command: `duty bootstrap` / `uv run app bootstrap`.

**Flow:**
1. `bootstrap_async()` seeds MongoDB via Beanie (existing, unchanged)
2. `_bootstrap_all()` then initializes Tortoise and calls `pg_bootstrap_async()`
3. `pg_bootstrap_async()` orchestrates all PG syncers in dependency order

**PG bootstrap order:**
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
- `init_test_database` — same for MongoDB (existing, unchanged)

Both databases are fully seeded before any tests run. This mirrors how the MongoDB bootstrap works — seed once, query many times.

### Constant data (preserved across tests)

These tables are seeded by bootstrap and **never cleaned** between tests:
- `char_sheet_section`, `trait_category`, `trait_subcategory`, `trait`
- `vampire_clan`, `werewolf_auspice`, `werewolf_tribe`
- `character_concept`, `dictionary_term`
- M2M junction tables: `vampire_clan_disciplines`, `werewolf_auspice_gifts`, `werewolf_tribe_gifts`

### Non-constant data (cleaned after every test)

The `cleanup_pg_database` fixture (autouse) runs `DELETE FROM` on all non-constant tables after every test. This prevents data leaks between tests. Uses DELETE (not TRUNCATE CASCADE) to avoid cascading into constant tables that have nullable FK relationships.

Tables cleaned: `audit_log`, `campaign`, `campaign_book`, `campaign_chapter`, `character`, `character_trait`, `character_inventory`, `specialty`, `vampire_attributes`, `werewolf_attributes`, `mage_attributes`, `hunter_attributes`, `campaign_experience`, `company_settings`, `developer_company_permission`, `developer`, `"user"` (quoted — reserved word), `company`, `dice_roll`, `quick_roll`, `note`, `s3_asset`, `chargen_session`, `chargen_session_characters`

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

`tests/pg_fixture_models.py` — Tortoise-equivalent of `tests/fixture_models.py` (Beanie). Registered as a pytest plugin in `conftest.py`.

Factories that create constant data (traits, concepts) use the yield + cleanup pattern to avoid polluting bootstrap data:

```python
@pytest.fixture
async def pg_trait_factory():
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
- `pg_trait_factory` — creates Tortoise `Trait` instances, auto-populates `category` and `sheet_section` if not provided
- `pg_character_concept_factory` — creates Tortoise `CharacterConcept` instances
- `pg_dictionary_term_factory` — creates Tortoise `DictionaryTerm` instances, self-cleaning (constant table)
- `pg_developer_factory` — creates Tortoise `Developer` instances, supports `is_global_admin`, auto-cleaned
- `pg_developer_company_permission_factory` — creates `DeveloperCompanyPermission` rows, auto-cleaned
- `pg_user_factory` — creates Tortoise `User` instances, auto-cleaned
- `pg_campaign_factory` — creates Tortoise `Campaign` instances (for FK resolution in experience tests), auto-cleaned
- `pg_campaign_book_factory` — creates Tortoise `CampaignBook` instances, auto-assigns number
- `pg_campaign_chapter_factory` — creates Tortoise `CampaignChapter` instances, auto-assigns number
- `pg_campaign_experience_factory` — creates Tortoise `CampaignExperience` instances, auto-cleaned

Add new factories here as domains migrate. Non-constant data factories (companies, users, characters, etc.) don't need self-cleanup because `cleanup_pg_database` handles those tables.

### Bridge Fixtures (Session 6+)

- `pg_mirror_user` — creates Tortoise User mirroring Beanie `base_user`
- `pg_mirror_user_storyteller` — storyteller role variant
- `pg_mirror_user_admin` — admin role variant
- `pg_mirror_campaign` — creates Tortoise Campaign mirroring Beanie `base_campaign`

The `_patch_pg_bridge` fixture patches `CampaignController`, `CampaignBookController`, and `CampaignChapterController` in addition to the Session 5-6 controllers.

### Archive Handler Bridge (User Domain)

`archive_user_cascade(user_id)` in `archive_handlers.py` performs cascade-only archival of QuickRoll, S3Asset, and Character data (all still in MongoDB) for a given user ID. The Tortoise `UserService` archives the User record itself, then calls this function. The existing `UserArchiveHandler.handle()` method is preserved for `CompanyArchiveHandler`.

### Validation Service Bridge (User Domain)

`GetModelByIdValidationService.get_user_by_id()` routes by ID format: UUID → Tortoise, ObjectId → Beanie fallback. This bridge exists because unmigrated domains (character_trait) still pass PydanticObjectId. Remove the fallback when all callers are migrated.

### Mid-migration xfail state

After Session 6: `test_post_data_update_hook` in `test_after_response_hooks.py` is xfailed — the after-response hooks query Beanie Company with a Tortoise UUID. This will be resolved when hooks migrate in Session 10.

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

**Previous DTOs:** `PydanticDTO[BeanieModel]` wrappers in `lib/dto.py` with `dto_config()` — still used by domains that haven't migrated yet.

## Do Not Use `from __future__ import annotations` in Litestar Files

Litestar resolves type hints at runtime via `get_type_hints()` for handler signatures, dependency providers, and return types. `from __future__ import annotations` makes all annotations lazy strings, which breaks this resolution and forces imports out of `TYPE_CHECKING` with `# noqa: TC002` suppressions.

**Rule:** Do not use `from __future__ import annotations` in:
- Controller files (`domain/controllers/**/controllers.py`)
- Dependency provider files (`domain/pg_deps.py`, `domain/deps.py`)
- Any file where types appear in Litestar handler signatures or `Provide()` return types

Without the future import, annotations evaluate at definition time, ruff's TC rules work correctly, and no noqa suppressions are needed. Use string quotes for forward references if needed (rare in controllers).

Existing Beanie controller files still have it — they'll be cleaned up when each domain migrates.

## Dependency Providers: Dual-file Pattern

During migration, two dependency provider files coexist:

- `domain/deps.py` — Beanie-based providers for domains still on MongoDB
- `domain/pg_deps.py` — Tortoise-based providers for migrated domains

Controllers may import from both (e.g., blueprint controller uses `deps.provide_company_by_id` + `pg_deps.provide_trait_by_id`).

`pg_deps.py` has its own `_find_or_404` helper using `model.filter(id=..., is_archived=False).first()`. Providers that return models used in Struct conversion prefetch related objects for `@property` name fields and M2M ID lists.

**Cleanup (Session 4):** Removed Beanie constant providers from `deps.py` — `provide_character_blueprint_section_by_id`, `provide_trait_by_id`, `provide_trait_subcategory_by_id`, `provide_vampire_clan_by_id`, `provide_werewolf_tribe_by_id`, `provide_werewolf_auspice_by_id`, `provide_character_concept_by_id`, `provide_dictionary_term_by_id`. Only `provide_trait_category_by_id` remains (used by character controller until Session 8).

**Cleanup (Session 11):** Delete `deps.py`, rename `pg_deps.py` → `deps.py`.

### Tortoise Guards

`lib/pg_guards.py` — Tortoise-based authorization guards, parallel to `lib/guards.py` (Beanie). Migrated controllers use Tortoise guards for checking company membership and permissions.

Guards query the `DeveloperCompanyPermission` table directly instead of iterating through `Developer.companies`. The `connection.user` object remains Beanie — guards only read `.id` and `.is_global_admin` from the authenticated developer.

## DeveloperService

`DeveloperService` — centralized service for API key generation and verification. Functionality was previously methods on the Beanie `Developer` model; it's now a dedicated service class used by migrated controllers.

## Beanie/Tortoise Bridge for Integration Tests

During the migration period, integration tests mixing Beanie and Tortoise need both databases synchronized. A bridge pattern handles this:

**`tests/integration/domain/conftest.py`** — bridge fixtures that create Tortoise mirror objects matching Beanie auth developers:
- `pg_mirror_company` — creates Tortoise `Company` and returns `(beanie_company, pg_company)` tuple
- `pg_mirror_global_admin` — creates Beanie `Developer` with `is_global_admin=True` and mirrors in Tortoise
- `pg_mirror_company_owner` — creates Beanie `Developer`, adds to company as owner, mirrors in Tortoise
- `pg_mirror_company_user` — creates Beanie `Developer`, adds to company as user, mirrors in Tortoise
- `neutralize_after_response_hook` — resets `after_response_hooks` fixture for tests using migrated controllers with Beanie auth middleware

This is a temporary bridge pattern — it will be removed when the auth middleware migrates to Tortoise.

## Migration Status

| Session | Status | Description |
|---------|--------|-------------|
| 1 | Complete | Dual database infrastructure |
| 2 | Complete | All Tortoise model definitions |
| 3 | Complete | Bootstrap constants into PostgreSQL |
| 3.5 | Complete | Migrate character blueprint domain to PostgreSQL |
| 4 | Complete | Constants domain migration (dictionary) |
| 5 | Complete | Company and Developer domain migration |
| 6 | Complete | User domain migration |
| 7 | Complete | Campaign domain migration |
| 8-9 | Pending | Domain migrations (character, supporting) |
| 10 | Pending | Handlers, DI, middleware, CLI cleanup |
| 11 | Pending | Remove MongoDB |
| 12 | Pending | Post-migration cleanup |
