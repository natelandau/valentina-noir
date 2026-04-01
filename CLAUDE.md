# CLAUDE.md

## Project Overview

Valentina Noir is a REST API for managing World of Darkness tabletop role-playing games. Built with Litestar (Python ASGI framework), MongoDB (via Beanie ORM), and Redis for caching/sessions.

## Commands

```bash
# Development
duty run                      # Start dev server (requires MongoDB + Redis)
uv run app                    # Full CLI with all options
duty lint                     # Run all linters (ruff, mypy, typos, prek)
duty format                   # Check code formatting with ruff
duty test                     # Run tests with coverage
duty test -- -n 0             # Run tests serially (for debugging)
duty test -- -n 0 -v -s -x    # Serial, verbose, show output, stop on first failure
# NOTE: Docker must be running for tests (MongoDB + Redis containers)

# Database
docker compose -f compose-db.yml up -d   # Start MongoDB + Redis
duty bootstrap                           # Create database collections
duty populate                            # Delete existing data and populate with test data

# Maintenance
duty clean                    # Clean project artifacts
duty update                   # Update dependencies and pre-commit hooks
duty dev-setup                # Initialize development environment
```

## Workflow Rules

- **Never commit plans, designs, or implementation specs.** These are working documents only - do not stage or commit them to the repository.
- **Work on branches, not worktrees.** All development is done on git branches in the main repo checkout unless the user gives explicit instructions to use worktrees.
- **Never delete git tags.** Session checkpoint tags (e.g., `session-1-done`) and release tags must not be deleted, moved, or force-updated. This applies to all agents and subagents — no agent should run `git tag -d`, `git tag -f`, or any command that removes or overwrites an existing tag.

## Architecture

**Layered structure in `src/vapi/`:**

- `domain/controllers/` - API endpoints organized by feature (typically `controllers.py`, `dto.py`, `docs.py`; some have guards or multiple controller files)
- `domain/services/` - Business logic services
- `domain/handlers/` - Event/lifecycle handlers
- `domain/deps.py` - Dependency injection
- `db/` - Database models and repositories (Beanie ODM)
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
- Use Beanie's native query operators instead of raw MongoDB dicts. Beanie supports Python comparison operators on nested Pydantic BaseModel fields (e.g., `Trait.gift_attributes.tribe_id == tribe_id` not `{"gift_attributes.tribe_id": tribe_id}`).

## Critical Files

- `pyproject.toml` - All project configuration
- `duties.py` - Task automation
- `.env.example` - Required environment variables

## Testing

- Docker required (MongoDB + Redis run in containers via pytest-databases)
- Tests run in parallel by default (`-n auto --dist loadfile`)
- Custom markers: `@pytest.mark.serial`
- The full test suite is slow. During development on a branch with multiple commits, run individual test files (e.g., `uv run pytest tests/unit/domain/services/test_character_trait_svc.py -v -n 0`) and commit with `--no-verify` to skip pre-commit hooks. Run the full test suite once at the end of the session before finalizing.
- **Never use `pytest.skip()` or `pytest.mark.skip`.** All seed data is expected to be present. If a query for seed data returns nothing, the test should fail - not skip. Only assert in the `# Then` section, not to guard seed data existence.

## Documentation

Documentation is stored in the `docs/` directory. The documentation is written in Markdown and uses the [Zensical](https://zensical.org/) static site generator. The documentation is hosted on [GitHub Pages](https://pages.github.com/).

**IMPORTANT:** Always check the documentation after every change to ensure it is correct and up to date.
