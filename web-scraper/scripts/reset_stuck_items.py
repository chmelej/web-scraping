import os
import sys

# Add project root to sys.path
sys.path.append(os.getcwd())

from src.utils.db import get_db_connection, get_cursor

def reset_stuck_items():
    conn = get_db_connection()
    with get_cursor(conn) as cur:
        cur.execute("""
            UPDATE scr_scrape_queue 
            SET status = 'pending' 
            WHERE status = 'processing'
        """)
        count = cur.rowcount
        conn.commit()
        print(f"Reset {count} items from 'processing' to 'pending'.")

if __name__ == "__main__":
    reset_stuck_items()
