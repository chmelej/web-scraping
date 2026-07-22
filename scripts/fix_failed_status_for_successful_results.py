#!/usr/bin/env python3
import os
import sys

# Ensure src module can be imported
sys.path.append(os.getcwd())

from src.utils.db import get_db_connection, get_cursor
from src.utils.logging_config import setup_logging
from config.settings import LOG_DIR

def fix_queue_status_for_successful_results():
    logger = setup_logging('fix_queue_status', f"{LOG_DIR}/fix_queue_status.log")
    logger.info("Starting cleanup of failed queue statuses for HTTP 200 results...")

    conn = get_db_connection()
    try:
        with get_cursor(conn, dict_cursor=False) as cur:
            cur.execute("""
                UPDATE scr_scrape_queue q
                SET status = 'completed'
                FROM scr_scrape_results r
                WHERE q.queue_id = r.queue_id
                  AND q.status = 'failed'
                  AND r.status_code = 200;
            """)
            updated_count = cur.rowcount
            conn.commit()
            logger.info(f"Successfully updated {updated_count} queue items from 'failed' to 'completed'.")
    except Exception as e:
        logger.error(f"Error updating queue statuses: {e}", exc_info=True)
    finally:
        conn.close()

if __name__ == '__main__':
    fix_queue_status_for_successful_results()
