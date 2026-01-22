import psycopg2
from psycopg2.extras import RealDictCursor
from config.settings import DATABASE_URL
import time

def get_db_connection(max_retries=3, retry_delay=2):
    """Vytvoří DB connection s retry logikou"""
    for attempt in range(max_retries):
        try:
            return psycopg2.connect(DATABASE_URL)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                raise e

def get_cursor(conn, dict_cursor=True):
    """Vytvoří cursor"""
    if dict_cursor:
        return conn.cursor(cursor_factory=RealDictCursor)
    return conn.cursor()
