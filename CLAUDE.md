# CLAUDE.md

## Project Overview

Valentina Noir is a REST API for managing World of Darkness tabletop role-playing games. Built with Litestar (Python ASGI framework), MongoDB (via Beanie ORM), and Redis for caching/sessions.

## Commands

```bash
# Development
duty run                      # Start dev server (requires MongoDB + Redis)
duty lint                     # Run all linters (ruff, mypy, typos, prek)
duty test                     # Run tests with coverage
duty test -- -n 0             # Run tests serially (for debugging)
duty test -- -n 0 -v -s -x    # Serial, verbose, show output, stop on first failure

# Database
docker compose -f compose-db.yml up -d   # Start MongoDB + Redis
duty bootstrap                           # Create database collections
duty populate                            # Populate with test data

# Maintenance
duty clean                    # Clean project artifacts
duty update                   # Update dependencies and pre-commit hooks
duty dev-setup                # Initialize development environment
```

## Architecture

**Layered structure in `src/vapi/`:**

- `domain/controllers/` - API endpoints organized by feature (each has `controllers.py`, `dto.py`, `docs.py`)
- `domain/` - Business logic, dependency injection (`deps.py`), lifecycle hooks
- `db/` - Database models and repositories (Beanie ODM)
- `middleware/` - Auth (API key, basic, JWT), rate limiting, idempotency, cache headers
- `config/` - Environment-based configuration (pydantic-settings)
- `server/` - Litestar plugins, stores, SAQ job queue setup
- `cli/` - Command-line interface
- `openapi/` - OpenAPI/Swagger customization

**Key patterns:**

- Feature-based module organization
- DTO pattern for API contracts (separate from database models)
- Dependency injection via Litestar's DI system
- Async-first (all code uses async/await)

## Critical Files

- `pyproject.toml` - All project configuration
- `duties.py` - Task automation
- `env.example` - Required environment variables

## Documentation

Documentation is stored in the `docs/` directory. The documentation is written in Markdown and uses the [Zensical](https://zensical.org/) static site generator. The documentation is hosted on [GitHub Pages](https://pages.github.com/).

**IMPORTANT:** Always check the documentation after every change to ensure it is correct and up to date.
