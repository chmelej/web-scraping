import contextlib
import psycopg2
from psycopg2.extras import DictCursor
import os
from typing import Iterator

def get_db_connection() -> Iterator[psycopg2.extensions.connection]:
    """Dependency to get a database connection."""
    # Assuming config is loaded from environment variables in .env
    conn = psycopg2.connect(
        dbname=os.environ.get("DB_NAME", "scraper_db"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "postgres"),
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432")
    )
    try:
        yield conn
    finally:
        conn.close()

def get_cursor(conn: psycopg2.extensions.connection) -> Iterator[DictCursor]:
    cursor = conn.cursor(cursor_factory=DictCursor)
    try:
        yield cursor
    finally:
        cursor.close()
