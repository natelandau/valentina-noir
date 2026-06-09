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

## Populate dev data

Fill a local development database with believable, varied test data (companies, users with every role, campaigns/books/chapters, a vampire/werewolf/mortal/hunter character mix, dice rolls, quick rolls, notes, inventory, and placeholder image assets). This is dev-only tooling and is not shipped in the production image.

Image assets are not uploaded anywhere: they are database rows whose public URL points at `picsum.photos`, attached to characters, books, and chapters.

```bash
duty populate                 # reset + seed + populate (prompts to confirm)
duty reset                    # reset + seed only, no test data (prompts to confirm)

# Direct invocation with custom counts:
uv run python -m scripts.populate_dev_db --companies 3 --users 5 --campaigns 2 --characters 8
```

Both `duty populate` and `duty reset` drop and recreate the configured database, and prompt for confirmation first. The script refuses to run against a production-like target (when the Postgres host is not local); pass `--force` to override, or `--yes` to skip the confirmation prompt in non-interactive use.

Generated API keys (one global-admin developer, one company-admin, one non-admin) are printed to the console and written to `~/.dev/api_keys.txt`, each annotated with its access tier so you can pick the right key when testing different permission levels.

## Database Backups

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

## Request logging

Every HTTP request emits a single combined log entry containing both request and response data. The fields included in that entry are controlled by `VAPI_LOG__LOG_FIELDS`, an ordered list whose order also determines the order fields appear in the log line.

```bash
VAPI_LOG__LOG_FIELDS='["path","method","query","path_params","client","status_code","duration_ms","request_id","developer_id","error_type","error_detail","invalid_parameters"]'
```

Available fields:

| Source   | Fields                                                                                                                     |
| -------- | -------------------------------------------------------------------------------------------------------------------------- |
| Request  | `path`, `method`, `query`, `path_params`, `client`, `content_type`, `scheme`, `cookies`, `request_body`, `request_headers` |
| Response | `status_code`, `response_body`, `response_headers`                                                                         |
| Computed | `duration_ms`                                                                                                              |
| Scope    | `request_id`, `developer_id`, `operation_id`, `idempotency_key`, `acting_user_id`, `error_type`, `error_detail`, `invalid_parameters` |

The entry's log level follows the response status, so a failed request is one line at the right severity rather than a separate error line:

- `< 400` and routine 4xx (validation, not-found, conflict) → **INFO**
- `401`, `403`, `429` (auth failures, rate-limit rejections) → **WARNING**
- `5xx` (server faults) → **ERROR**

Notes on the scope-derived fields:

- `request_id` matches the `X-Request-Id` response header and the `request_id` stored on audit-log rows, so a single value ties together the log line, the client's response, and the audit trail.
- `developer_id` is the authenticated API client. It is absent on unauthenticated routes (docs, schema, public).
- `operation_id` groups entries by endpoint independent of path-param values, and is present only when the handler defines one.
- `idempotency_key` is logged only on requests that send the `Idempotency-Key` header, and only on cache misses (a cache hit short-circuits before this middleware runs).
- `acting_user_id` is the user a developer acts on behalf of, present only on endpoints whose guard resolves the `On-Behalf-Of` header.
- `error_type` and `error_detail` carry the class and message of a handled error (e.g. `ConflictError` / `already exists`). They are present only on requests that returned a handled error, and they replace the separate error log line that handled errors previously emitted.
- `invalid_parameters` carries the field-level detail of a validation error (`[{"field": ..., "message": ...}]`). It is present only on validation errors that have field detail, so it never appears as an empty list.

### Unhandled exceptions

A handled error becomes a clean response and is captured entirely in the combined entry above. An *unhandled* exception (a bug, e.g. a `KeyError`) is different: it produces two lines. `VAPI_LOG__LOG_EXCEPTIONS` (default `always`) controls this.

- A dedicated **`Uncaught exception`** line at ERROR with the full traceback in the `exception` field, plus the `request_id` and `developer_id` so it correlates with the combined entry.
- The combined request entry itself, at ERROR (the response is a 500), with `error_type` set to the exception class.

Expected client errors (the 4xx classes) are excluded from this traceback logging, so only genuine faults produce a stack trace.

Enabling `request_headers` or `request_body` can log sensitive values. Header and cookie obfuscation is controlled by `VAPI_LOG__OBFUSCATE_HEADERS` and `VAPI_LOG__OBFUSCATE_COOKIES`. Note that `request_headers` logs the raw `Cookie` header unless `Cookie` is added to the obfuscate list.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines and commit process.
