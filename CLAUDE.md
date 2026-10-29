# CLAUDE.md

## Project Overview

Valentina Noir is a REST API for managing World of Darkness tabletop role-playing games. Built with Litestar (Python ASGI framework), PostgreSQL (via Tortoise ORM), and Redis for caching/sessions.

## Commands

```bash
# Always run tasks as `uv run duty ...`. A bare `duty` can resolve to another checkout's .venv
# and silently lint and test that checkout's source instead of this one's.

# Stack (each checkout has its own Compose stack: api, postgres, redis, s3 on its slot's ports)
uv run duty up                # Build and start, fill an empty db (main populates, worktree copies main), migrate
uv run duty up debug=true     # Same, API under debugpy on port +7 (no reload)
uv run duty down              # Stop the stack and its test servers, keep data
uv run duty reset             # Delete data and rebuild (main: populate, worktree: recopy main)
uv run duty reset fresh=true  # Worktree: rebuild from populate with new IDs and keys
uv run duty info              # Print .dev/connection.md (URLs, ports, API keys, company/user IDs)
uv run duty envs              # List every stack on this machine
uv run duty logs              # Follow stack logs
uv run duty psql              # psql on this checkout's database
uv run duty redis-cli         # redis-cli on this checkout's Redis
uv run duty migrate           # Apply migrations, then seed reference data (in the api container)
uv run duty seed              # Re-seed reference data without migrating
uv run duty makemigrations    # Generate migration files from model changes
uv run duty populate          # Replace all data with test data and new keys (script options after `--`)
uv run duty developer username=<u> email=<e> [admin=true]  # Create a developer, record its key
# NOTE: The app runs only in the api container. migrate/seed/makemigrations/populate/developer need
#       the stack up. Ports: 24100 + 10 * slot (main is slot 0), offsets in CONTRIBUTING.md

# Worktrees (each gets its own slot, stack, and copy of main's data)
uv run duty worktree branch=<name>          # Create .worktrees/<name>; then `cd` there and `uv run duty up`
uv run duty worktree-teardown [branch=<name>]  # Remove the worktree, its containers and volumes; keeps the branch
uv run duty worktree-prune                  # Remove stacks of worktrees that no longer exist

# Quality
uv run duty lint              # Run all linters (ruff, ty, typos, prek)
uv run duty fix               # Apply ruff autofixes and formatting
uv run duty format            # Check code formatting with ruff
uv run duty test              # Start this checkout's test servers, run tests with coverage
uv run duty test -- -n 0 -v -s -x  # Serial, verbose, show output, stop on first failure
uv run duty check             # Run lint + full test suite (what the pre-push hook runs)
# NOTE: lint/test checks run through gate-cache and skip when they already passed on identical
#       content. Force a re-run with GATE_CACHE_DISABLE=1 (e.g. `GATE_CACHE_DISABLE=1 uv run duty test`)

# Other
uv run duty docs              # Serve the docs site at http://localhost:8100
uv run duty dev-setup         # Install deps and git hooks
uv run duty update            # Update dependencies and pre-commit hooks
uv run duty clean             # Remove build artifacts, coverage, caches, and dev logs
```

## Workflow Rules

- **Never commit plans, designs, or implementation specs written to docs/superpowers/** These are working documents only - do not stage or commit them to the repository.

## Architecture

**Layered structure in `src/vapi/`:**

- `domain/controllers/` - API endpoints organized by feature (typically `controllers.py`, `dto.py`, `docs.py`; some have guards or multiple controller files)
- `domain/services/` - Business logic services
- `domain/handlers/` - Event/lifecycle handlers
- `domain/deps.py` - Dependency injection
- `db/` - Database models (Tortoise ORM) in `sql_models/`
- `lib/` - Shared infrastructure (database helpers, stores, guards, exceptions, scheduled tasks, DTOs)
- `utils/` - Utility functions (auth, math, string manipulation, asset handling)
- `middleware/` - Auth (API key, basic, JWT), rate limiting, idempotency, cache headers
- `config/` - Environment-based configuration (pydantic-settings)
- `server/` - Litestar app assembly
- `cli/` - Command-line interface
- `openapi/` - OpenAPI/Swagger customization

**Key patterns:**

- Feature-based module organization
- DTO pattern for API contracts (separate from database models)
- Dependency injection via Litestar's DI system
- Async-first (all code uses async/await)
- **Do not use `from __future__ import annotations`** in controller files, dependency provider files, or any file where types appear in Litestar handler signatures. Litestar resolves type hints at runtime — the future import breaks this and forces `# noqa: TC002` suppressions.
- **Archived (soft-deleted) items must never appear in API responses** outside the global admin domain. All queries must filter `is_archived=False` — this includes list endpoints, detail-by-ID lookups (via `_find_or_404`), and child resources embedded via `active_prefetch`. Never add query parameters, include options, or any other mechanism that allows callers to request archived rows.
- **Audit logging via `post_data_update_hook`** — all mutating endpoints wire `after_response=hooks.post_data_update_hook`, which auto-populates structured fields (entity_type, operation, FK columns, description) from path params and HTTP method. Controllers can enrich entries by setting `request.state.audit_description` (custom text) and/or `request.state.audit_changes` (dict of `{"field": {"old": x, "new": y}}`). See `src/vapi/domain/hooks/audit_helpers.py` for the mapping logic and full documentation.
- **`acting_user` on guarded endpoints for OpenAPI visibility** — when a mutating endpoint uses a guard that requires the `On-Behalf-Of` header (e.g. `user_can_manage_campaign`, `user_character_player_or_storyteller_guard`), always include `acting_user: User` in the handler signature even if the value is unused in the method body. This ensures the OpenAPI spec correctly documents the header as required. Mark the unused parameter with `# noqa: ARG002`.
- **Join (M2M through) tables use a `j_` prefix** — always set `through="j_<model>_<field>"` explicitly on every `ManyToManyField`. The prefix clusters generated join tables together in the schema and disambiguates them from domain tables (whose own names contain underscores). Renaming a `through=` value generates a safe `AlterField` migration (a pure `ALTER TABLE ... RENAME TO ...`, no data loss).
- **Modeling game concepts "one level deeper than a trait"** — the deciding axis is character ownership, not display. Three shapes, pick by rule:
    - If a character can own the thing at a value (buy with XP, place on a sheet, roll it), it must be a `Trait` — grouped under a `TraitSubcategory` when it needs a parent (merits/flaws under thematic subcategories, Hunter Edge perks under their Edge, background advantages under their background). Only `Trait`/`CharacterTrait` carry the cost/value/pool/sheet machinery.
    - If it only describes what a rating means and is never owned directly, it is reference data hanging off the parent: variable-size sets are `TraitPower`-style child rows (Discipline/path dot powers); small fixed named sets are nullable columns on the reference model (clan bane/compulsion, `gift_*`).
    - Never mix the two: no cost/value fields on descriptive child tables, and no generic "sub-trait" entity that serves both ownable and descriptive rows behind discriminator flags.
    - Known accepted strain: Hunter Edges are trait-like (they carry `pool`/`system` and are rolled in play) but are modeled as `TraitSubcategory` because their Perks must be ownable `Trait`s and traits have no trait-to-trait parent link. If "character owns Edge X" ever needs to be recorded directly, that is a deliberate refactor to weigh at that time — do not bolt on workarounds.

## Critical Files

- `pyproject.toml` - All project configuration
- `duties.py` - Task automation
- `.env.example` - Required environment variables

## Testing

- Docker required: `uv run duty test` starts this checkout's own `postgres-test` and `redis-test` Compose services and leaves them running. A bare `uv run pytest <file>` finds this checkout's test services by itself, but `uv run duty test` must have run once in the checkout to start them (and again after `uv run duty down`). `VAPI_TEST_POSTGRES_PORT` and `VAPI_TEST_REDIS_PORT` (set both or neither) point the suite at other servers
- Tests run in parallel by default (`-n auto --dist loadfile`)
- Custom markers: `@pytest.mark.serial`
- The full test suite is slow. During development on a branch with multiple commits, run individual test files (e.g., `uv run pytest tests/unit/domain/services/test_character_trait_svc.py -v -n 0`). The full suite runs in the pre-push hook, not on commit, so commit normally. Run `uv run duty test` once at the end of the session before finalizing; a pass on the same tree lets the push hook skip it.
- **Never use `pytest.skip()` or `pytest.mark.skip`.** All seed data is expected to be present. If a query for seed data returns nothing, the test should fail - not skip. Only assert in the `# Then` section, not to guard seed data existence.
- **Always use factories to create database objects in tests.** Never call `Model.create()` or `Model.save()` directly in test bodies. Use the factory fixtures in `tests/fixture_models.py`. Factories that create constant data (traits, concepts, or any other data created when bootstrapping the database.) must clean up after themselves since the per-test cleanup only deletes non-constant tables.
- **Minimize integration tests; prefer unit tests.** Integration tests are slow, so reserve them for verifying an entire endpoint (routing, auth/guards, status codes, overall request/response wiring). Test specifics within an endpoint (individual field behavior, defaults, normalization, DTO serialization, patch logic) with unit tests against the model, DTO, or service instead. When an endpoint is already covered by an integration test, add unit tests for new field-level behavior rather than new integration tests.

## Documentation

Documentation is stored in the `docs/` directory. The documentation is written in Markdown and uses the [Zensical](https://zensical.org/) static site generator. The documentation is hosted on [GitHub Pages](https://pages.github.com/).

**IMPORTANT:** Always check the documentation after every change to ensure it is correct and up to date.

**Audience:** `docs/` is for end-user API developers only. They consume the public API via an `X-API-KEY` and have no access to the server, its environment variables, deployment config, or source. Never document maintainer- or operator-facing concerns (env vars, server config, deployment, migrations, internal architecture) in `docs/`. All maintainer-facing documentation goes in `README.md`.
