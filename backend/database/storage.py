
"""SQLite database initialization and connection management for WP6."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent / "aamen.sqlite3"


def get_database_path() -> Path:
    configured = os.getenv("AAMEN_DB_PATH")

    if configured:
        return Path(configured).expanduser().resolve()

    return DEFAULT_DATABASE_PATH


@contextmanager
def database_connection() -> Iterator[sqlite3.Connection]:
    path = get_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path, timeout=10.0)

    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")

        yield connection
        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def initialize_database() -> None:
    with database_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS user_preferences (
                device_id TEXT PRIMARY KEY NOT NULL,
                location INTEGER NOT NULL DEFAULT 0
                    CHECK(location IN (0, 1)),
                photos INTEGER NOT NULL DEFAULT 0
                    CHECK(photos IN (0, 1)),
                banking_information INTEGER NOT NULL DEFAULT 0
                    CHECK(banking_information IN (0, 1)),
                third_party_sharing INTEGER NOT NULL DEFAULT 0
                    CHECK(third_party_sharing IN (0, 1)),
                updated_at INTEGER NOT NULL DEFAULT
                    (CAST(strftime('%s', 'now') AS INTEGER))
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_cache (
                cache_key TEXT PRIMARY KEY NOT NULL,
                device_id TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at INTEGER NOT NULL DEFAULT
                    (CAST(strftime('%s', 'now') AS INTEGER)),
                expires_at INTEGER NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_analysis_cache_expires_at
            ON analysis_cache(expires_at)
            """
        )
