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
3. Optionally, start PostgreSQL and Redis from Docker: `docker compose -f compose-db.yml up -d`. The filestore for these containers will be stored in the `.dev` directory. The Redis container requires authentication, so when using it, set the following in `.env.secret`: `VAPI_REDIS__URL=redis://:redispassword@localhost:6379/0`
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

### Running Tests

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
