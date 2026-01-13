[![Changelog](https://img.shields.io/github/v/release/natelandau/valentina-noir?include_prereleases&label=changelog)](https://github.com/natelandau/valentina-noir/releases)[![Tests](https://github.com/natelandau/valentina-noir/actions/workflows/automated-tests.yml/badge.svg)](https://github.com/natelandau/valentina-noir/actions/workflows/automated-tests.yml)[![codecov](https://codecov.io/gh/natelandau/valentina-noir/graph/badge.svg?token=jxh4KfYKk7)](https://codecov.io/gh/natelandau/valentina-noir)

# Valentina Noir

Valentina Noir is a comprehensive API for managing World of Darkness tabletop role-playing games.

## Technologies

Valentina is built using the following core technologies:

-   [Litestar](https://litestar.dev/) - Lightweight and flexible Python ASGI framework
-   [MongoDB](https://www.mongodb.com/) - NoSQL database
-   [Beanie](https://beanie-orm.dev/) - MongoDB ORM for Python
-   [Redis](https://redis.io/) - In-memory data structure store
-   [Granian](https://github.com/emmett-framework/granian) - ASGI server for Python

## Getting Started Developing Valentina Noir

We use [uv](https://docs.astral.sh/uv/) for dependency management. To start developing:

1. Install uv using the [recommended method](https://docs.astral.sh/uv/getting-started/installation/) for your operating system
2. Clone this repository: `git clone https://github.com/natelandau/valentina-noir`
3. Navigate to the repository: `cd valentina-noir`
4. Install dependencies with uv: `uv sync --all-groups`
5. Activate your virtual environment: `source .venv/bin/activate`
6. Install [prek](https://prek.j178.dev/) git hooks: `prek install` y

## Running the development environment

1. Configure the necessary environment variables in `.env` and `.env.secret` (See `.env.example` for required variables)
2. Two encryption keys are required which can be generated using the following command: `python3 -c 'import secrets; print(secrets.token_hex(32))'`
3. Optionally, start MongoDB and Redis from Docker: `docker compose -f compose-db.yml up -d`. The filestore for these containers will be stored in the `.dev` directory.
4. Bootstrap the database:
    - Create the required database collections: `duty bootstrap`
    - Optionally, run `duty populate` to populate the database with dummy data including developers and API keys, companies, users, campaigns, and characters
5. Run the development server: `duty run`

### Required Environment Variables

Valentina Noir is configured via environment variables. View the `.env.example` file for the required variables and edit `.env` and `.env.secret` to set the values.

### Running Tasks

A cli tool is included in the project to help interact with litestar. Run `uv app --help` for more information.

We use [Duty](https://pawamoy.github.io/duty/) as a task runner.

-   `duty --list` - List all available tasks
-   `duty lint` - Run all linters
-   `duty test` - Run all tests
-   `duty clean` - Clean the project of all temporary files
-   `duty run` - Run the development server locally (requires MongoDB and Redis to be running)
-   `duty bootstrap` - Bootstrap the development database
-   `duty populate` - Populate the database with dummy data. This will create developers, companies, users, campaigns, and characters.
-   `duty dev-clean` - Clean the development environment
-   `duty dev-setup` - Set up the development environment in `.dev` including storage for logs, the development database, and Redis instance all of which are mounted as volumes.

## Development Guidelines

When developing for valentina, please follow these guidelines:

-   Write full docstrings
-   All code should use type hints
-   Write unit tests for all new functions
-   Write integration tests for all new features
-   Follow the existing code style

## Commit Process

1. Create a branch for your feature or fix
2. Make your changes
3. Ensure code passes linting with `duty lint`
4. Ensure tests pass with `duty test`
5. Commit using [Commitizen](https://github.com/commitizen-tools/commitizen): `cz c`
6. Create a pull request

We use [Semantic Versioning](https://semver.org/) for version management.

## AI Usage

We do not use AI to generate application code. However, the use of AI in generating tests and documentation is permitted.
