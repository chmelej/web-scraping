from unittest.mock import MagicMock, patch
from src.utils.db import get_db_connection

@patch('src.utils.db.psycopg2.connect')
def test_db_connection(mock_connect):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cur
    mock_cur.fetchone.return_value = [1]

    conn = get_db_connection()
    assert conn is not None
    cur = conn.cursor()
    cur.execute("SELECT 1")
    assert cur.fetchone()[0] == 1

    conn.close()
