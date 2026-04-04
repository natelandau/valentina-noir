# CLAUDE.md

## Project Overview

Valentina Noir is a REST API for managing World of Darkness tabletop role-playing games. Built with Litestar (Python ASGI framework), PostgreSQL (via Tortoise ORM), and Redis for caching/sessions.

## Commands

```bash
# Development
duty run                      # Start dev server (requires PostgreSQL + Redis)
uv run app                    # Full CLI with all options
duty lint                     # Run all linters (ruff, mypy, typos, prek)
duty format                   # Check code formatting with ruff
duty test                     # Run tests with coverage
duty test -- -n 0             # Run tests serially (for debugging)
duty test -- -n 0 -v -s -x    # Serial, verbose, show output, stop on first failure
# NOTE: Docker must be running for tests (PostgreSQL + Redis containers)

# Database
docker compose -f compose-db.yml up -d   # Start PostgreSQL + Redis
duty bootstrap                           # Create database schema and seed data
duty populate                            # Delete existing data and populate with test data

# Maintenance
duty clean                    # Clean project artifacts
duty update                   # Update dependencies and pre-commit hooks
duty dev-setup                # Initialize development environment
```

## Workflow Rules

- **Never commit plans, designs, or implementation specs written to docs/superpowers/** These are working documents only - do not stage or commit them to the repository.
- **Work on branches, not worktrees.** All development is done on git branches in the main repo checkout unless the user gives explicit instructions to use worktrees.
- All changes to the shape of the API must be documented in `api-changes.md`. api-changes.md is never committed to git.

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

## Critical Files

- `pyproject.toml` - All project configuration
- `duties.py` - Task automation
- `.env.example` - Required environment variables

## Testing

- Docker required (PostgreSQL + Redis run in containers via pytest-databases)
- Tests run in parallel by default (`-n auto --dist loadfile`)
- Custom markers: `@pytest.mark.serial`
- The full test suite is slow. During development on a branch with multiple commits, run individual test files (e.g., `uv run pytest tests/unit/domain/services/test_character_trait_svc.py -v -n 0`) and commit with `--no-verify` to skip pre-commit hooks. Run the full test suite once at the end of the session before finalizing.
- **Never use `pytest.skip()` or `pytest.mark.skip`.** All seed data is expected to be present. If a query for seed data returns nothing, the test should fail - not skip. Only assert in the `# Then` section, not to guard seed data existence.
- **Always use factories to create database objects in tests.** Never call `Model.create()` or `Model.save()` directly in test bodies. Use the factory fixtures in `tests/fixture_models.py`. Factories that create constant data (traits, concepts, or any other data created when bootstrapping the database.) must clean up after themselves since the per-test cleanup only deletes non-constant tables.

## Documentation

Documentation is stored in the `docs/` directory. The documentation is written in Markdown and uses the [Zensical](https://zensical.org/) static site generator. The documentation is hosted on [GitHub Pages](https://pages.github.com/).

**IMPORTANT:** Always check the documentation after every change to ensure it is correct and up to date.
