# Contributing to Valentina Noir

Thanks for your interest in improving Valentina Noir. This guide walks you through setting up a local development environment, running the app and its tests, and getting your changes merged. If you are new to Python tooling, read the [Troubleshooting](#troubleshooting) section at the end. It covers the pitfalls that trip people up most often.

## Prerequisites

Install these tools before you start:

- **Python 3.13** - the only supported version. `uv` installs and manages it for you (the pinned version lives in `.python-version`), so you don't need a system Python.
- **[uv](https://docs.astral.sh/uv/)** - handles the Python toolchain, the virtual environment, and every dependency. Install it with the [recommended method](https://docs.astral.sh/uv/getting-started/installation/) for your operating system.
- **Docker** - runs PostgreSQL and Redis locally, and runs the test suite. Docker must be running before you start the database or run tests.
- **git** - to clone the repository and manage branches.

We use `uv` exclusively for dependency management. Do not use `pip`, Poetry, or Conda in this project.

## Getting started

Set up the project in six steps:

1. Clone the repository: `git clone https://github.com/natelandau/valentina-noir`
2. Enter the directory: `cd valentina-noir`
3. Install all dependencies, including dev and docs groups: `uv sync --all-groups`. This creates a virtual environment in `.venv/` and installs the pinned Python version if it is missing.
4. Activate the virtual environment: `source .venv/bin/activate`. Activation puts the project's tools (`duty`, `prek`, `pytest`, `ruff`) on your `PATH` so you can call them by name. If you skip this step, prefix each command with `uv run` (for example, `uv run duty run`).
5. Install the [prek](https://prek.j178.dev/) git hooks: `prek install`. These run linters and formatters automatically before each commit.
6. Configure your environment and database (see the next two sections).

## Configuring the environment

The application reads configuration from environment variables. For local development, put them in a `.env.secret` file at the repository root.

1. Copy the example file to see every available variable: `cp .env.example .env.secret`. Variables in `.env.example` that are not commented out are required; commented variables show their default value.
2. Generate the two required 32-byte encryption keys (`VAPI_AUTHENTICATION_ENCRYPTION_KEY` and `VAPI_RATE_LIMIT__ENCRYPTION_KEY`). Run this command once per key and paste the output into `.env.secret`:

   ```bash
   python3 -c 'import secrets; print(secrets.token_hex(32))'
   ```

3. Set `VAPI_NAME` to any display name. It is required and namespaces the application's cache keys.

## Setting up the database

The app needs PostgreSQL and Redis. The quickest way to get both is the bundled Docker Compose file.

1. Start PostgreSQL and Redis in Docker: `docker compose -f compose-db.yml up -d`. Their data is stored under the `.dev/` directory.
2. The Redis container requires a password, so add this line to `.env.secret`:

   ```bash
   VAPI_REDIS__URL=redis://:redispassword@localhost:6379/0
   ```

3. Apply the database migrations to create the schema: `duty migrate`
4. Seed the reference data (traits, concepts, clans, and similar constants): `duty seed`
5. Optional: fill the database with believable test data (companies, users of every role, campaigns, characters, dice rolls, and more): `duty populate`. This drops, recreates, and reseeds the database, then generates the test data. It prints generated API keys to the console and writes them to `.dev/api_keys.txt`.

## Running the development server

Start the local development server with a live reload watcher on `src/`:

```bash
duty run
```

For the full stack (API, PostgreSQL, and Redis) entirely in Docker, use `duty up`. This wraps `docker compose up --build`. Always let it rebuild: a plain `docker compose up` can serve stale code against a database whose schema has already moved on.

## Task runner

We use [Duty](https://pawamoy.github.io/duty/) as the task runner. Run `duty --list` to see every task. The most common ones:

| Task                  | What it does                                                             |
| --------------------- | ------------------------------------------------------------------------ |
| `duty run`            | Run the development server locally (needs PostgreSQL and Redis running)  |
| `duty up`             | Build and run the full stack (API, PostgreSQL, Redis) in Docker          |
| `duty lint`           | Run all linters (ruff, ty, typos, prek hooks)                            |
| `duty format`         | Check code formatting with ruff                                          |
| `duty test`           | Run the test suite with coverage                                         |
| `duty migrate`        | Apply pending database migrations                                        |
| `duty makemigrations` | Generate migration files from model changes                             |
| `duty seed`           | Seed the database with reference data                                    |
| `duty populate`       | Reset the database and fill it with varied test data                    |
| `duty reset`          | Drop, recreate, and seed the database with no test data                 |
| `duty update`         | Upgrade dependencies and prek hooks                                      |
| `duty clean`          | Remove temporary files and caches                                        |

Both `duty populate` and `duty reset` drop and recreate the database, so they prompt for confirmation first.

### Application CLI

A command-line tool ships with the project for tasks the task runner doesn't cover, such as managing developer accounts and restoring database backups. See every command with:

```bash
uv run app --help
```

Useful subcommands include `developer` (create, list, and delete API developer accounts), `migrate`, `seed`, `restore`, and `routes`.

## Running tests

Docker must be running before you run the tests, because the suite spins up PostgreSQL and Redis in containers.

Run the full suite with coverage:

```bash
duty test
```

Tests run in parallel by default using [pytest-xdist](https://pytest-xdist.readthedocs.io/en/stable/) (`-n auto`), which makes the full suite faster but interleaves output. When debugging, run the suite serially and with more output by passing pytest flags after `--`:

```bash
duty test -- -n 0 -v -s -x
```

- `-n 0` - run serially instead of in parallel (makes output readable)
- `-v` - verbose output (repeat for more detail)
- `-s` - show `print` and log output as tests run
- `-x` - stop on the first failure

To run a single test file while iterating, call pytest through `uv run`:

```bash
uv run pytest tests/unit/domain/services/test_character_trait_svc.py -v -n 0
```

Run `uv run pytest --help` for all options.

## Development guidelines

Follow these conventions when writing code:

- Write Google-style docstrings for public functions, classes, and methods.
- Add type hints to every function signature.
- Prefer unit tests. They are fast and cover field-level behavior, service methods, and DTO logic. Add them against the model, DTO, or service.
- Reserve integration tests for verifying a whole endpoint: routing, auth and guards, status codes, and request/response wiring. They are slow, so keep them minimal. When an endpoint already has an integration test, cover new field-level behavior with unit tests instead of new integration tests.
- Match the style of the surrounding code.

## Commit process

We use [Conventional Commits](https://www.conventionalcommits.org/) with [Commitizen](https://github.com/commitizen-tools/commitizen), and squash each pull request into a single commit on merge. Follow these steps:

1. Create a branch for your feature or fix.
2. Make your changes.
3. Confirm the code passes linting: `duty lint`.
4. Confirm the tests pass: `duty test`.
5. Commit with Commitizen, which prompts you through the required format: `cz c`.
6. Open a pull request. Its title and description must follow the same commit format, because the squashed commit inherits them.

Commit subjects use the form `<type>(<scope>): <subject>`, where `type` is one of `build`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `style`, or `test`. We follow [Semantic Versioning](https://semver.org/) for releases.

## Troubleshooting

### `command not found: duty` (or `prek`, `pytest`, `ruff`)

The tool is installed, but your shell can't find it because the virtual environment isn't active. Fix it either way:

- Activate the environment for the session: `source .venv/bin/activate`, then run the command normally.
- Or run the command through uv without activating: `uv run duty run`.

### `No module named vapi` or an import error at startup

The dependencies are out of sync with the lockfile, usually after pulling new commits that changed `pyproject.toml` or `uv.lock`. Reinstall them:

```bash
uv sync --all-groups
```

Run this whenever a teammate adds or upgrades a dependency. It reconciles your `.venv` with the committed lockfile.

### Dependencies changed upstream and I want the latest versions

`uv sync` installs the exact versions from `uv.lock`. To upgrade the locked versions themselves, run:

```bash
duty update
```

This runs `uv lock --upgrade`, re-syncs the environment, and updates the prek hooks. Commit the resulting `uv.lock` change.

### Tests or the dev server fail with a database or connection error

Docker isn't running, or the database containers aren't up. Start Docker Desktop (or your Docker daemon), then start the containers:

```bash
docker compose -f compose-db.yml up -d
```

Confirm Docker is reachable with `docker info`.

### Redis authentication errors

The bundled Redis container requires a password. Make sure `.env.secret` contains:

```bash
VAPI_REDIS__URL=redis://:redispassword@localhost:6379/0
```

### `relation does not exist` or other schema errors

Your database schema is behind the current models. Apply the pending migrations:

```bash
duty migrate
```

If you also need the reference data, follow up with `duty seed`. To start completely fresh, run `duty reset`.

### prek hooks didn't run on commit

The git hooks aren't installed in your clone. Install them once:

```bash
prek install
```

### Wrong Python version

This project requires Python 3.13, pinned in `.python-version`. `uv` reads that file and installs the correct interpreter automatically during `uv sync`, so you rarely need to manage Python yourself. If a command reports the wrong version, re-run `uv sync --all-groups`.
