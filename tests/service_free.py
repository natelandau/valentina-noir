"""Stand-ins for the database and Redis fixtures, for tests that need neither server.

`tests/conftest.py` connects every test to PostgreSQL and Redis through autouse fixtures. A
conftest or test module that imports these fixtures shadows those, so its tests collect and run
with the test servers stopped.
"""

import pytest


@pytest.fixture(scope="session")
def init_test_postgres() -> None:
    """Skip creating, migrating, and seeding the test database."""


@pytest.fixture
def cleanup_pg_database() -> None:
    """Skip deleting test rows, since these tests write none."""


@pytest.fixture(name="redis")
def fx_redis() -> None:
    """Skip connecting to the Redis test server."""
