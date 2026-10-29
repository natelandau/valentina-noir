# Contributing to Valentina Noir

Thanks for your interest in improving Valentina Noir. This guide shows you how to run the API on your computer, run the tests, and get your changes merged.

Each checkout of the repository runs its own stack of Docker containers: the API, PostgreSQL, Redis, and S3-compatible storage. The main checkout and each [git worktree](https://git-scm.com/docs/git-worktree) get their own ports, data, and test servers, so two branches never share a database. If a command fails, read the [Troubleshooting](#troubleshooting) section at the end.

## Prerequisites

Install these tools before you start:

- [uv](https://docs.astral.sh/uv/getting-started/installation/). It installs Python 3.13 (pinned in `.python-version`), creates the virtual environment, and installs every dependency. Do not use `pip`, Poetry, or Conda in this project.
- Docker, with Docker Compose v2. Docker must be running before you start a stack or run the tests.
- git.
- `lsof`, which is preinstalled on macOS. `uv run duty up` uses it to find the process that holds a port.

You do not need a local PostgreSQL, Redis, or system Python. You also do not need any credentials: every secret in a local stack is generated on your computer or is a fixed local-only value.

## Getting started

Do these steps one time in a new clone:

1. Clone the repository: `git clone https://github.com/natelandau/valentina-noir`
2. Go into the directory: `cd valentina-noir`
3. Install the dependencies and the [prek](https://prek.j178.dev/) git hooks: `uv run duty dev-setup`
4. Start the stack: `uv run duty up`

The first `uv run duty up` builds the API image, starts the containers, and fills the empty database with test data. When it finishes, it prints the API URL and the path of the connection sheet:

```text
✓ vapi-main is up
  API:              http://127.0.0.1:24100
  Connection sheet: /path/to/valentina-noir/.dev/connection.md
```

The API serves its routes under `/api/v1`. Open `.dev/connection.md` to get an API key, then send a request:

```bash
curl -H "X-API-KEY: API_KEY" http://127.0.0.1:24100/api/v1/companies
```

Run every task in this guide as `uv run duty TASK`. A bare `duty` can resolve to the virtual environment of a different checkout, and then it runs the code of that checkout. To see every task, run `uv run duty --list`.

## The connection sheet

Each checkout has a connection sheet at `.dev/connection.md`. It holds everything that you need to call the API of that checkout:

- The Compose project name, the data origin (`populated` or `copied-from-main`), and the time the sheet was written.
- The API URL from the host, and the API URL from a container (`http://host.docker.internal:PORT/api/v1`).
- Every port of the stack.
- A `psql` command and a `redis-cli` command that connect from the host.
- One section per developer, with the ID, email, access level, API key, and a `curl` example.
- Every company with its ID, and every user with its ID, name, role, and company ID. Use these IDs in paths and in the `On-Behalf-Of` header.

The file `.dev/connection.json` holds the same data for scripts. Do not edit either file. `uv run duty up`, `reset`, `populate`, and `developer` write them again from the database each time, so the sheet always shows the IDs and keys that exist. To print the sheet in the terminal, run `uv run duty info`.

The database stores only hashed API keys. The raw keys are in `.dev/api-keys.json`, and the sheet reads them from there. Both files contain raw keys, so only your user can read them.

## Ports

Each checkout holds a slot number. The main checkout is always slot 0, and each worktree takes the lowest free slot. A slot owns a block of ten ports that starts at `24100 + 10 * slot`. Every port binds to `127.0.0.1` only.

| Offset | Service                                   | Main (slot 0) | Slot 1 |
| ------ | ----------------------------------------- | ------------- | ------ |
| +0     | API                                       | 24100         | 24110  |
| +1     | PostgreSQL                                | 24101         | 24111  |
| +2     | Redis                                     | 24102         | 24112  |
| +3     | S3 API (RustFS)                           | 24103         | 24113  |
| +4     | S3 web console                            | 24104         | 24114  |
| +5     | PostgreSQL for tests                      | 24105         | 24115  |
| +6     | Redis for tests                           | 24106         | 24116  |
| +7     | Debugger (`debugpy`)                      | 24107         | 24117  |

The connection sheet lists the ports of its checkout, so you do not need to calculate them.

The stack always publishes the debugger port, but the debugger listens on it only in debug mode. If a different process holds the debugger port, a normal `uv run duty up` also fails.

## Stack tasks

Each task acts on the stack of the checkout where you run it.

| Task                                                  | What it does                                                                                                     |
| ----------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `uv run duty up`                                      | Build and start the stack, fill an empty database, apply migrations, and write the connection sheet              |
| `uv run duty up debug=true`                           | The same as `up`, but the API runs under `debugpy` with no auto-reload                                           |
| `uv run duty down`                                    | Stop the stack and its test servers. The data is kept                                                            |
| `uv run duty reset`                                   | Delete the data of the stack and build it again. Main populates. A worktree copies main again                    |
| `uv run duty reset fresh=true`                        | In a worktree, delete the data and populate it with new test data, IDs, and keys instead of a copy of main       |
| `uv run duty info`                                    | Print the connection sheet                                                                                       |
| `uv run duty envs`                                    | List every stack on this computer, with its slot, API URL, state, and connection sheet                           |
| `uv run duty logs`                                    | Follow the logs of the stack. Press Ctrl+C to stop                                                               |
| `uv run duty psql`                                    | Open a `psql` shell on the database of this checkout                                                             |
| `uv run duty redis-cli`                               | Open a `redis-cli` shell on the Redis of this checkout                                                           |
| `uv run duty migrate`                                 | Apply pending migrations, then seed the reference data                                                           |
| `uv run duty seed`                                    | Seed the reference data without migrating                                                                        |
| `uv run duty makemigrations`                          | Generate migration files from model changes into `src/vapi/db/migrations`                                        |
| `uv run duty populate`                                | Replace all data with new test data and new API keys. Put script options after `--`                              |
| `uv run duty developer username=NAME email=EMAIL`     | Create a developer, record its API key, and add it to the connection sheet. Add `admin=true` for a global admin |

`reset` and `populate` delete data, so they ask for confirmation first.

The API runs only in its container. `migrate`, `seed`, `makemigrations`, `populate`, and `developer` run inside the `api` container, so the stack must be up. The container mounts `src/` and `scripts/`, and the server reloads when you save a file. `uv run duty up` always rebuilds the image, so a change to `pyproject.toml`, `uv.lock`, or the `Dockerfile` takes effect at the next `up`. The build cache makes this fast when nothing changed.

### Test data

On the first start of the main checkout, `uv run duty up` runs `scripts/populate_dev_db.py`. It creates companies, users of every role, campaigns, characters, dice rolls, and other records, plus three developers: a global admin, a company admin, and a developer with no admin access. Image assets are database rows whose URLs point at `picsum.photos`. No file is uploaded.

To use custom counts, put the script options after `--`. The task writes the connection sheet again when it finishes:

```bash
uv run duty populate -- --companies 3 --users 5
```

To see every option, run the script help in the `api` container. Get the project name from the connection sheet:

```bash
docker compose -p vapi-main exec api python -m scripts.populate_dev_db --help
```

### The application CLI

The `app` CLI ships in the image. Its commands include `migrate`, `seed`, `restore`, `developer`, and `routes`. Run it in the `api` container:

```bash
docker compose -p vapi-main exec api app --help
```

To create a developer whose key shows on the connection sheet, use `uv run duty developer` instead of `app developer create`.

## Settings

The stack needs no settings file from you. Its settings come from these sources, in this order. A later source overrides an earlier one.

| Source                | In git | What it holds                                                                                                 |
| --------------------- | ------ | ------------------------------------------------------------------------------------------------------------- |
| `compose.dev.env`     | Yes    | Settings that every local stack shares, such as the rate-limit policies and the OAuth audiences               |
| `.dev/generated.env`  | No     | The two encryption keys, generated on the first `up`                                                          |
| `.env.local`          | No     | Your personal overrides. Optional                                                                             |
| `compose.yml`         | Yes    | The connection values: PostgreSQL, Redis, S3, and the server address. You cannot override them in `.env.local` |

To change a setting for your checkout, add it to `.env.local` in the repository root, then run `uv run duty up`:

```bash
VAPI_LOG__LEVEL=DEBUG
VAPI_STORES__TTL=60
```

`.env.example` lists every variable that the application reads.

> **CAUTION:** Do not delete or edit `.dev/generated.env`. The encryption keys in it protect data in the database and Redis of the stack, and new keys cannot read that data. If you lose the file, run `uv run duty reset`.

Local uploads go to the `vapi-dev` bucket in the RustFS container of the stack, never to a hosted bucket or CDN. The bucket allows anonymous reads, so asset URLs open in a browser. To browse the bucket, open the S3 web console port and sign in with the user `vapi` and the password `vapi-local-secret`.

The data of the stack is in Docker named volumes that belong to its Compose project. `uv run duty down` keeps them. `uv run duty reset` and `uv run duty worktree-teardown` delete them.

## Working in worktrees

A worktree gets its own stack, with a copy of the data of the main checkout. You can change the schema, delete data, or run the tests in a worktree, and the main checkout is not affected.

1. From any checkout, create the worktree:

    ```bash
    uv run duty worktree branch=my-feature
    ```

    The task creates `.worktrees/my-feature` on a new branch `my-feature` from the current commit of the main checkout. It reserves a slot, copies `CLAUDE.local.md` if you have one, and runs `uv sync --all-groups` in the worktree. It does not start the stack.

2. Go into the worktree and start its stack:

    ```bash
    cd .worktrees/my-feature
    uv run duty up
    ```

    On the first start, the task copies the database, the bucket, `.dev/api-keys.json`, and `.dev/generated.env` from the main checkout. The API keys and IDs on the connection sheet of the worktree are therefore the same as on main. If the PostgreSQL and S3 containers of main are stopped, the task starts them for the copy. It never starts the API of main.

The main checkout must have data before a worktree can copy it. If it has none, run `uv run duty up` in the main checkout first.

If main has a migration that your branch does not have, the migrations of the worktree fail after the copy. In that case, build the worktree data from new test data:

```bash
uv run duty reset fresh=true
```

When you finish with a worktree, remove it. Run the first command in the worktree, or the second command from any checkout:

```bash
uv run duty worktree-teardown
uv run duty worktree-teardown branch=my-feature
```

The task deletes the containers and volumes of the stack, removes the worktree directory, and frees the slot. It keeps the branch. If the worktree has uncommitted or untracked files, the task stops and deletes nothing.

If you removed a worktree directory in a different way, its stack still exists. To delete the stacks of all worktrees whose directory is gone, run `uv run duty worktree-prune`.

## Attaching a debugger

The API can run under [debugpy](https://github.com/microsoft/debugpy). In debug mode the server does not reload on file changes, because a reload starts a new process and drops the debugger session.

1. Start the stack in debug mode:

    ```bash
    uv run duty up debug=true
    ```

2. Attach your editor to `127.0.0.1` on the debugger port of the checkout (offset +7, which is `24107` on main). Map the remote path `/app/src` to the local `src/` directory.
3. To go back to the auto-reloading server, run `uv run duty up`.

For VS Code, add this configuration to `.vscode/launch.json`:

```json
{
    "name": "Attach to the local API",
    "type": "debugpy",
    "request": "attach",
    "connect": { "host": "127.0.0.1", "port": 24107 },
    "pathMappings": [{ "localRoot": "${workspaceFolder}/src", "remoteRoot": "/app/src" }]
}
```

In a worktree, change the port to the debugger port on its connection sheet.

## Running tests

The tests run on the host, against two test servers that belong to the checkout: `postgres-test` and `redis-test`. These servers keep no data between runs. They do not use the PostgreSQL and Redis of your stack.

Run the full suite with coverage:

```bash
uv run duty test
```

`uv run duty test` starts the test servers of the checkout and leaves them running for the next run. The API stack does not need to be up. Tests run in parallel with [pytest-xdist](https://pytest-xdist.readthedocs.io/en/stable/) (`-n auto`). Each worker gets its own database, and the Redis test server has enough databases for 63 workers.

To debug, run the suite in series with more output. Put pytest options after `--`:

```bash
uv run duty test -- -n 0 -v -s -x
```

- `-n 0` runs the tests in series, so the output is readable.
- `-v` shows each test name.
- `-s` shows `print` and log output.
- `-x` stops at the first failure.

To run one file, call pytest directly:

```bash
uv run pytest tests/unit/domain/services/test_character_trait_svc.py -v -n 0
```

A direct `uv run pytest` finds the test servers of its checkout. The main checkout uses slot 0. A worktree uses the slot that it holds in the registry. The test servers must be running, so run `uv run duty test` one time first. `uv run duty down` also stops the test servers.

To point the tests at other servers, set these variables. Set both port variables, or neither:

| Variable                  | Default                      |
| ------------------------- | ---------------------------- |
| `VAPI_TEST_SERVICES_HOST` | `127.0.0.1`                  |
| `VAPI_TEST_POSTGRES_PORT` | The `postgres-test` port of the slot |
| `VAPI_TEST_REDIS_PORT`    | The `redis-test` port of the slot    |

When both port variables are set, the tests read neither git nor the registry.

### Running under the security-audit sandbox

The tests need no Docker socket, no network access outside the computer, and no real credentials. They connect only to the two test server ports on loopback. This makes it possible to run them in a restricted sandbox:

1. Outside the sandbox, start the test servers: `uv run duty test`, or `docker compose -p vapi-main --profile test up -d --wait postgres-test redis-test`.
2. In the sandbox, set the port variables, and move the pytest cache and the coverage data to a directory that the sandbox can write. Replace `SCRATCH` with that directory:

    ```bash
    VAPI_TEST_POSTGRES_PORT=24105 VAPI_TEST_REDIS_PORT=24106 COVERAGE_FILE=SCRATCH/coverage \
        uv run pytest -o cache_dir=SCRATCH/pytest-cache
    ```

    The command collects coverage only if you add `--cov`. To write the XML report to the scratch directory too, add `--cov --cov-report=xml:SCRATCH/coverage.xml`.

The sandbox can use an isolated loopback that does not reach ports that Docker Desktop publishes on the host. In that case, review the source and run only the tests that need no servers. Report the other tests as blocked by the sandbox:

```bash
COVERAGE_FILE=SCRATCH/coverage uv run pytest -o cache_dir=SCRATCH/pytest-cache \
    tests/unit/scripts tests/unit/test_services.py
```

These tests shadow the database and Redis fixtures with the stand-ins in `tests/service_free.py`. To let more tests run without the servers, import those fixtures in the tests' `conftest.py` or test module. Do this only for tests that touch no database, no Redis, and no `client`.

## Using a local stack from another project

A project that uses this API, such as an API client, can find every local stack in one file. The registry is at `~/.local/state/valentina-noir/environments.json`. The stack tasks write it, and it is never in git. To use a different path, set `VAPI_DEV_REGISTRY`.

The registry looks like this:

```json
{
  "schema_version": 1,
  "description": "Local Valentina Noir dev stacks on this machine. ...",
  "slots": {
    "main": { "slot": 0, "checkout": "/path/to/valentina-noir" }
  },
  "environments": {
    "main": {
      "key": "main",
      "checkout": "/path/to/valentina-noir",
      "branch": "main",
      "slot": 0,
      "project": "vapi-main",
      "ports": {
        "api": 24100, "postgres": 24101, "redis": 24102, "s3": 24103, "s3_console": 24104,
        "postgres_test": 24105, "redis_test": 24106, "debugpy": 24107
      },
      "api_url": "http://127.0.0.1:24100",
      "api_url_from_containers": "http://host.docker.internal:24100",
      "healthz_url": "http://127.0.0.1:24100/healthz",
      "connection_sheet": "/path/to/valentina-noir/.dev/connection.md",
      "keys_file": "/path/to/valentina-noir/.dev/api-keys.json",
      "developers": [
        {
          "id": "DEVELOPER_ID",
          "username": "dev-admin",
          "email": "admin@test.dev",
          "is_global_admin": false,
          "api_key": "API_KEY",
          "permissions": [["COMPANY_ID", "ADMIN"]]
        }
      ]
    }
  }
}
```

Use these fields:

- `environments` has one entry per checkout. The main checkout has the key `main`. A worktree has its branch name as the key.
- `api_url` is the base URL from the host. `api_url_from_containers` is the base URL from a different Docker container. Add `/api/v1` for the API routes.
- `keys_file` is the `.dev/api-keys.json` file of the checkout, which holds the raw API keys that the stack tasks recorded.
- `developers` is the same list as in `.dev/connection.json` of the checkout, raw API keys included. `api_key` is `null` when no key was recorded for that developer. `permissions` holds pairs of company ID and permission.
- The registry does not record whether a stack runs. Send a request to `healthz_url`. A running stack returns status 200 with `{"status": "ok"}`.

The registry contains raw API keys, so only your user can read it. The keys belong to local test developers and change each time the stack is populated.

Paste this snippet into the `CLAUDE.md` or `AGENTS.md` of a project that calls a local Valentina Noir API:

```markdown
## Local Valentina Noir API

Local Valentina Noir stacks are listed in `~/.local/state/valentina-noir/environments.json`
(JSON, `schema_version` 1). Do not edit that file.

- Use `environments.main` for the main checkout, or `environments.<branch>` for a worktree.
- Base URL: `api_url` from the host, or `api_url_from_containers` from a container. API routes are
  under `/api/v1`.
- API keys: `developers[].api_key`, sent in the `X-API-KEY` header. `is_global_admin` and
  `permissions` (pairs of company ID and permission) give the access of each key.
- Before you send requests, make sure that the stack runs: `curl -fsS <healthz_url>` must return
  `{"status": "ok"}`. If it fails, ask the user to run `uv run duty up` in the `checkout` directory.
- Keys and IDs change when the stack is populated again. Read the file again after a 401 or 404.
- Company and user IDs for paths and the `On-Behalf-Of` header are in the `connection_sheet`
  file of the entry.
```

## Other tasks

We use [Duty](https://pawamoy.github.io/duty/) as the task runner. These tasks do not use a stack:

| Task                       | What it does                                                                 |
| -------------------------- | ---------------------------------------------------------------------------- |
| `uv run duty dev-setup`    | Install the dependencies and the git hooks                                   |
| `uv run duty lint`         | Run all linters: ruff, ty, typos, and the prek hooks                         |
| `uv run duty fix`          | Apply the ruff autofixes and format the code                                 |
| `uv run duty format`       | Check the code format with ruff                                              |
| `uv run duty check`        | Run `lint` and `test`, the same checks as the pre-push hook                  |
| `uv run duty docs`         | Serve the documentation site at `http://localhost:8100` with live reload     |
| `uv run duty update`       | Upgrade the dependencies and the prek hooks                                  |
| `uv run duty clean`        | Remove build artifacts, coverage reports, caches, and development logs       |

### Skipped checks

`uv run duty lint` and `uv run duty test` run each check through [gate-cache](https://github.com/natelandau/gate-cache). When a check passes, gate-cache records the pass for the exact content of the working copy. If you run the same check again on the same content, gate-cache skips it and prints `already passed on tree ..., skipping`. A change to any file that git does not ignore makes the check run again. The prek hooks call the same tasks, so a check that passed in your terminal is skipped at commit or push time.

`uv run duty test` with pytest options, for example `uv run duty test -- -k unit`, always runs, because a filtered run must not skip the full suite.

To make every check run, set `GATE_CACHE_DISABLE=1`, or delete all records with `uv run gate-cache clear`. Caching is off when the `CI` variable is set.

## Development guidelines

Obey these conventions when you write code:

- Write Google-style docstrings for public functions, classes, and methods.
- Add type hints to every function signature.
- Prefer unit tests. They are fast, and they cover field-level behavior, service methods, and DTO logic. Write them against the model, DTO, or service.
- Use integration tests only to verify a whole endpoint: routing, auth and guards, status codes, and request and response wiring. They are slow. When an endpoint already has an integration test, cover new field-level behavior with unit tests.
- Match the style of the surrounding code.

## Commit process

We use [Conventional Commits](https://www.conventionalcommits.org/) with [Commitizen](https://github.com/commitizen-tools/commitizen), and squash each pull request into a single commit on merge. Do these steps:

1. Create a branch for your feature or fix.
2. Make your changes.
3. Make sure that the linters pass: `uv run duty lint`.
4. Make sure that the tests pass: `uv run duty test`.
5. Commit with Commitizen, which prompts you for each part of the format: `uv run cz c`.
6. Open a pull request. Its title and description must use the same commit format, because the squashed commit gets them.

Commit subjects use the form `<type>(<scope>): <subject>`, where `type` is one of `build`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `style`, or `test`. We use [Semantic Versioning](https://semver.org/) for releases.

## Troubleshooting

### `Port 24100 is in use by ...`

A process or container outside the stack listens on a port of the slot. The message names the process, and the container if there is one. Stop it, then run `uv run duty up` again.

### `This checkout has no stack yet`

The task needs a stack, and this checkout has never started one. Run `uv run duty up`.

### `api is not running for this checkout`

`migrate`, `seed`, `makemigrations`, `populate`, and `developer` run in the `api` container. Run `uv run duty up`, then run the task again.

### `Main's stack has no data to copy`

A worktree copies its first data from the main checkout. Run `uv run duty up` in the main checkout, then run `uv run duty up` in the worktree again.

### `Database migrations failed` in a worktree

The data was copied from main, and main has a migration that this branch does not have. Run `uv run duty reset fresh=true` to build the data from new test data.

### `relation does not exist` or other schema errors

The database schema is older than the models. Apply the pending migrations with `uv run duty migrate`. To start with new data, run `uv run duty reset`.

### `test services are not running` or `this worktree has no stack slot yet`

The tests cannot reach the test servers of this checkout. Run `uv run duty test` one time to start them, then run pytest again.

### Tests or a stack task fail with a Docker error

Docker is not running. Start Docker Desktop or the Docker daemon, then run the task again. To make sure that Docker responds, run `docker info`.

### `No module named vapi` or an import error

The dependencies do not match the lockfile, for example after you pull commits that change `pyproject.toml` or `uv.lock`. Run `uv sync --all-groups`. The containers get the new dependencies at the next `uv run duty up`.

### You want newer versions of the dependencies

`uv sync` installs the exact versions in `uv.lock`. To upgrade the locked versions, run `uv run duty update`, then commit the change to `uv.lock`.

### The prek hooks did not run on commit or push

The git hooks are not installed in your clone. Run `uv run prek install`.
