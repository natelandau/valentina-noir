"""Verify the PostgreSQL schema created by Tortoise generate_schemas.

These tests run against the test PostgreSQL database that is initialized
by the `init_test_postgres` session fixture in conftest.py.
"""

from __future__ import annotations

import pytest
from tortoise import Tortoise


@pytest.fixture
async def pg_conn():
    """Get the default Tortoise database connection."""
    return Tortoise.get_connection("default")


EXPECTED_TABLES = [
    "audit_log",
    "campaign",
    "campaign_book",
    "campaign_chapter",
    "campaign_experience",
    "char_sheet_section",
    "character",
    "character_concept",
    "character_inventory",
    "character_trait",
    "chargen_session",
    "chargen_session_characters",
    "company",
    "company_settings",
    "developer",
    "developer_company_permission",
    "dice_roll",
    "dice_roll_result",
    "dice_roll_traits",
    "dictionary_term",
    "hunter_attributes",
    "mage_attributes",
    "note",
    "quick_roll",
    "quick_roll_traits",
    "s3_asset",
    "specialty",
    "trait",
    "trait_category",
    "trait_subcategory",
    "user",
    "vampire_attributes",
    "vampire_clan",
    "vampire_clan_disciplines",
    "werewolf_attributes",
    "werewolf_auspice",
    "werewolf_auspice_gifts",
    "werewolf_tribe",
    "werewolf_tribe_gifts",
]


class TestSchemaCreation:
    """Verify that all expected tables exist in PostgreSQL."""

    @pytest.mark.anyio
    async def test_all_tables_exist(self, pg_conn) -> None:
        """Verify every expected table was created."""
        _, result = await pg_conn.execute_query(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        )
        actual_tables = sorted(row["table_name"] for row in result)
        for table in EXPECTED_TABLES:
            assert table in actual_tables, f"Table '{table}' not found in PostgreSQL"

    @pytest.mark.anyio
    async def test_table_count(self, pg_conn) -> None:
        """Verify the exact number of tables matches expectations."""
        _, result = await pg_conn.execute_query(
            "SELECT COUNT(*) as cnt FROM information_schema.tables WHERE table_schema = 'public'"
        )
        actual_count = result[0]["cnt"]
        assert actual_count == len(EXPECTED_TABLES), (
            f"Expected {len(EXPECTED_TABLES)} tables, found {actual_count}"
        )


class TestPrimaryKeys:
    """Verify UUID primary keys on all model tables."""

    @pytest.mark.anyio
    @pytest.mark.parametrize(
        "table",
        [
            t
            for t in EXPECTED_TABLES
            if t
            not in {
                "chargen_session_characters",
                "dice_roll_traits",
                "quick_roll_traits",
                "vampire_clan_disciplines",
                "werewolf_auspice_gifts",
                "werewolf_tribe_gifts",
            }
        ],
    )
    async def test_uuid_primary_key(self, pg_conn, table: str) -> None:
        """Each model table should have a UUID primary key column named 'id'."""
        _, result = await pg_conn.execute_query(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = $1 AND column_name = 'id'",
            [table],
        )
        assert len(result) == 1, f"Table '{table}' missing 'id' column"
        assert result[0]["data_type"] == "uuid", (
            f"Table '{table}' id column is {result[0]['data_type']}, expected uuid"
        )


class TestForeignKeys:
    """Verify key foreign key constraints exist."""

    @pytest.fixture
    async def fk_map(self, pg_conn) -> dict[str, list[tuple[str, str]]]:
        """Build a mapping of table -> [(column, referenced_table), ...]."""
        _, result = await pg_conn.execute_query(
            "SELECT "
            "  tc.table_name, "
            "  kcu.column_name, "
            "  ccu.table_name AS referenced_table "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON tc.constraint_name = kcu.constraint_name "
            "JOIN information_schema.constraint_column_usage ccu "
            "  ON tc.constraint_name = ccu.constraint_name "
            "WHERE tc.constraint_type = 'FOREIGN KEY' "
            "  AND tc.table_schema = 'public'"
        )
        fk_dict: dict[str, list[tuple[str, str]]] = {}
        for row in result:
            fk_dict.setdefault(row["table_name"], []).append(
                (row["column_name"], row["referenced_table"])
            )
        return fk_dict

    @pytest.mark.anyio
    @pytest.mark.parametrize(
        ("table", "column", "referenced_table"),
        [
            ("trait_category", "sheet_section_id", "char_sheet_section"),
            ("trait", "category_id", "trait_category"),
            ("trait", "sheet_section_id", "char_sheet_section"),
            ("character", "company_id", "company"),
            ("character", "campaign_id", "campaign"),
            ("character", "user_creator_id", "user"),
            ("character", "user_player_id", "user"),
            ("character_trait", "character_id", "character"),
            ("character_trait", "trait_id", "trait"),
            ("campaign_book", "campaign_id", "campaign"),
            ("campaign_chapter", "book_id", "campaign_book"),
            ("campaign_experience", "user_id", "user"),
            ("campaign_experience", "campaign_id", "campaign"),
            ("company_settings", "company_id", "company"),
            ("vampire_attributes", "character_id", "character"),
            ("werewolf_attributes", "character_id", "character"),
            ("note", "company_id", "company"),
        ],
    )
    async def test_foreign_key_exists(
        self, fk_map, table: str, column: str, referenced_table: str
    ) -> None:
        """Verify specific foreign key constraints exist."""
        fks = fk_map.get(table, [])
        match = [(c, r) for c, r in fks if c == column and r == referenced_table]
        assert match, (
            f"FK {table}.{column} -> {referenced_table} not found. Actual FKs for {table}: {fks}"
        )


class TestUniqueConstraints:
    """Verify unique constraints on key tables."""

    @pytest.mark.anyio
    async def test_developer_username_unique(self, pg_conn) -> None:
        """Developer.username should have a unique constraint."""
        _, result = await pg_conn.execute_query(
            "SELECT COUNT(*) as cnt FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON tc.constraint_name = kcu.constraint_name "
            "WHERE tc.constraint_type = 'UNIQUE' "
            "  AND tc.table_name = 'developer' "
            "  AND kcu.column_name = 'username'"
        )
        assert result[0]["cnt"] >= 1

    @pytest.mark.anyio
    async def test_developer_email_unique(self, pg_conn) -> None:
        """Developer.email should have a unique constraint."""
        _, result = await pg_conn.execute_query(
            "SELECT COUNT(*) as cnt FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON tc.constraint_name = kcu.constraint_name "
            "WHERE tc.constraint_type = 'UNIQUE' "
            "  AND tc.table_name = 'developer' "
            "  AND kcu.column_name = 'email'"
        )
        assert result[0]["cnt"] >= 1
