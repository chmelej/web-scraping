import os
import sys

# Add project root to sys.path
sys.path.append(os.getcwd())

from src.utils.db import get_db_connection, get_cursor

def check_queue():
    conn = get_db_connection()
    with get_cursor(conn) as cur:
        cur.execute("SELECT status, COUNT(*) FROM scr_scrape_queue GROUP BY status")
        rows = cur.fetchall()
        print("Queue Status Counts:")
        for row in rows:
            print(f"  {row['status']}: {row['count']}")

if __name__ == "__main__":
    check_queue()
