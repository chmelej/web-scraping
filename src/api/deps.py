import contextlib
import psycopg2
from psycopg2.extras import DictCursor
from typing import Iterator
from config.settings import DATABASE_URL

def get_db_connection() -> Iterator[psycopg2.extensions.connection]:
    """Dependency to get a database connection."""
    conn = psycopg2.connect(DATABASE_URL)
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
