import psycopg2
from psycopg2.extras import RealDictCursor
from config.settings import DATABASE_URL

def get_db_connection():
    """Vytvoř DB connection"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn

def get_cursor(conn, dict_cursor=True):
    """Vytvoř cursor"""
    if dict_cursor:
        return conn.cursor(cursor_factory=RealDictCursor)
    return conn.cursor()
