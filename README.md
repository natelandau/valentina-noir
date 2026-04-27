[![Changelog](https://img.shields.io/github/v/release/natelandau/valentina-noir?include_prereleases&label=changelog)](https://github.com/natelandau/valentina-noir/releases) [![Tests](https://github.com/natelandau/valentina-noir/actions/workflows/automated-tests.yml/badge.svg)](https://github.com/natelandau/valentina-noir/actions/workflows/automated-tests.yml) [![codecov](https://codecov.io/gh/natelandau/valentina-noir/graph/badge.svg?token=jxh4KfYKk7)](https://codecov.io/gh/natelandau/valentina-noir)

# Valentina Noir

Valentina Noir is a comprehensive API for managing World of Darkness tabletop role-playing games. Developer documentation is available at [docs.valentina-noir.com](https://docs.valentina-noir.com).

## Technologies

Valentina is built using the following core technologies:

- [Litestar](https://litestar.dev/) - Lightweight and flexible Python ASGI framework
- [PostgreSQL](https://www.postgresql.org/) - Relational database
- [Tortoise ORM](https://tortoise.github.io/) - Async Python ORM
- [Redis](https://redis.io/) - In-memory data structure store
- [Granian](https://github.com/emmett-framework/granian) - ASGI server for Python

## Running with Docker

The Docker image is available at `ghcr.io/natelandau/valentina-noir`. The container requires PostgreSQL and Redis to be available. See `compose.yml` for a full stack example.

### Docker-Specific Environment Variables

These variables are used by the container entrypoint and are also available in `.env.example`.

| Variable                       | Default | Description                                                                                                                                                                           |
| ------------------------------ | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `PUID`                         | `1000`  | UID for the application user inside the container                                                                                                                                     |
| `PGID`                         | `1000`  | GID for the application user inside the container                                                                                                                                     |
| `VAPI_DOCKER_MIGRATE`          | `false` | Set to `true` to run database migrations on startup                                                                                                                                   |
| `VAPI_DOCKER_SEED`             | `false` | Set to `true` to seed reference data on startup                                                                                                                                       |
| `VAPI_APIUSER_USERNAME`        |         | Username for a developer account created on startup                                                                                                                                   |
| `VAPI_APIUSER_EMAIL`           |         | Email for the developer account                                                                                                                                                       |
| `VAPI_APIUSER_IS_GLOBAL_ADMIN` | `false` | Set to `true` to grant global admin to the startup developer                                                                                                                          |
| `VAPI_DOCKER_RESTORE`          | `false` | Set to `true` to restore the database from the most recent S3 backup on startup. Don't forget to set `VAPI_DOCKER_MIGRATE=true` to bring the schema up to date with the current code. |

Set `PUID` and `PGID` to match the host user's UID/GID when using bind-mounted volumes to avoid permission issues. Find your UID and GID with:

```bash
id -u  # UID
id -g  # GID
```

All application configuration variables from `.env.example` are also supported and should be passed to the container via an env file or environment variables.

### Database Backups

Valentina Noir can automatically back up the PostgreSQL database to S3 on a daily schedule. Backups use `pg_dump` in custom format (`.dump`) and are stored under `db_backups/` in the configured S3 bucket.

**Requirements:**

- `pg_dump` must be available in the environment (included in the Docker image)
- AWS credentials and S3 bucket must be configured (the same `VAPI_AWS__*` variables used for asset storage)

**Enable backups** by setting `VAPI_BACKUP__ENABLED=true`. Backups are disabled by default.

| Variable                      | Default     | Description                                  |
| ----------------------------- | ----------- | -------------------------------------------- |
| `VAPI_BACKUP__ENABLED`        | `false`     | Enable automatic database backups            |
| `VAPI_BACKUP__CRON`           | `0 3 * * *` | Cron schedule (default: 3 AM daily)          |
| `VAPI_BACKUP__RETAIN_DAILY`   | `7`         | Number of daily backups to keep              |
| `VAPI_BACKUP__RETAIN_WEEKLY`  | `4`         | Weekly backups to keep (oldest per ISO week) |
| `VAPI_BACKUP__RETAIN_MONTHLY` | `6`         | Monthly backups to keep (oldest per month)   |
| `VAPI_BACKUP__RETAIN_YEARLY`  | `2`         | Yearly backups to keep (oldest per year)     |

**Retention policy:** Every backup is a daily backup. At prune time, the retention logic selects which backups to keep: the N most recent for daily, and the oldest backup from each week/month/year for the other tiers. A single backup can satisfy multiple tiers. Backups not covered by any tier are deleted.

### Restoring from a backup

The scheduled backup task (see `src/vapi/lib/scheduled_tasks.py`) uploads a
daily `pg_dump -Fc` file to S3 under `db_backups/`. The `app restore` command
replaces the current database with one of these backups.

```bash
# Restore the most recent S3 backup (default)
uv run app restore

# Restore a specific backup from S3
uv run app restore --s3-path db_backups/2026-04-15.dump

# Restore from a local .dump file
uv run app restore --file /path/to/backup.dump

# Skip the confirmation prompt (used by scripts / docker entrypoint)
uv run app restore --yes
```

**Two-step flow for older backups.** A restore loads the schema and data that
were in the dump file. If the backup predates the current code, follow up with
a migration:

```bash
uv run app restore
uv run app migrate
```

**Running in Docker.** Set `VAPI_DOCKER_RESTORE=true` in the container
environment to pull the most recent S3 backup on startup, before migrations
run. Typically pair it with `VAPI_DOCKER_MIGRATE=true` so the schema is also
brought up to date:

```
VAPI_DOCKER_RESTORE=true
VAPI_DOCKER_MIGRATE=true
```

`app restore` reuses `VAPI_AWS_*` credentials. If those are not set and `--file`
is not provided, the command exits with an error.

## Getting Started Developing Valentina Noir

We use [uv](https://docs.astral.sh/uv/) for dependency management. To start developing:

1. Install uv using the [recommended method](https://docs.astral.sh/uv/getting-started/installation/) for your operating system
2. Clone this repository: `git clone https://github.com/natelandau/valentina-noir`
3. Navigate to the repository: `cd valentina-noir`
4. Install dependencies with uv: `uv sync --all-groups`
5. Activate your virtual environment: `source .venv/bin/activate`
6. Install [prek](https://prek.j178.dev/) git hooks: `prek install`

## Running the development environment

1. Configure the necessary environment variables in `.env.secret` (See `.env.example` for all possible variables)
2. Two encryption keys are required which can be generated using the following command: `python3 -c 'import secrets; print(secrets.token_hex(32))'`
3. Optionally, start PostgreSQL and Redis from Docker: `docker compose -f compose-db.yml up -d`. The filestore for these containers will be stored in the `.dev` directory.
4. Set up the database:
    - Apply database migrations: `duty migrate`
    - Seed with reference data: `duty seed`
    - Optionally, run `duty populate` to populate the database with dummy data including developers and API keys, companies, users, campaigns, and characters
5. Run the development server: `duty run`

### Running Tasks

A cli tool is included in the project to help interact with litestar. Run `uv app --help` for more information.

We use [Duty](https://pawamoy.github.io/duty/) as a task runner.

- `duty --list` - List all available tasks
- `duty lint` - Run all linters
- `duty test` - Run all tests
- `duty clean` - Clean the project of all temporary files
- `duty run` - Run the development server locally (requires PostgreSQL and Redis to be running)
- `duty seed` - Seed the database with reference data (traits, concepts, clans, etc.)
- `duty migrate` - Apply pending database migrations
- `duty makemigrations` - Generate migration files from model changes
- `duty populate` - Populate the database with dummy data. This will create developers, companies, users, campaigns, and characters.
- `duty dev-clean` - Clean the development environment
- `duty dev-setup` - Set up the development environment in `.dev` including storage for logs, the development database, and Redis instance all of which are mounted as volumes.

## Running Tests

To run all tests in the project, use the following command:

```bash
duty test -- -n 0
```

This will run all tests in the project in parallel using [pytest-xdist](https://pytest-xdist.readthedocs.io/en/stable/).

During development, it is often useful to run tests in serial mode and with more verbose output. You can do this by running pytest directly and appending these flags to the command:

- `-n 0` - Run tests in serial mode
- `-v` - Verbose output. Append more `-v`s for more verbose output.
- `-s` - Show test output as it runs.
- `-x` - Stop running tests on the first failure.

Run `pytest --help` for more information and options.

## Development Guidelines

When developing for valentina, please follow these guidelines:

- Write full docstrings
- All code should use type hints
- Write unit tests for all new functions
- Write integration tests for all new features
- Follow the existing code style

## Commit Process

1. Create a branch for your feature or fix
2. Make your changes
3. Ensure code passes linting with `duty lint`
4. Ensure tests pass with `duty test`
5. Commit using [Commitizen](https://github.com/commitizen-tools/commitizen): `cz c`
6. Create a pull request

We use [Semantic Versioning](https://semver.org/) for version management.
