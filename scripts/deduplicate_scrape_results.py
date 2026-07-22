#!/usr/bin/env python3
import os
import sys

# Ensure src module can be imported
sys.path.append(os.getcwd())

from src.utils.db import get_db_connection, get_cursor
from src.utils.logging_config import setup_logging
from config.settings import LOG_DIR

def deduplicate_results(batch_size=1000):
    logger = setup_logging('deduplicate_results', f"{LOG_DIR}/deduplicate_results.log")
    logger.info("Starting cleanup of rapid-fire duplicate scrape_results (DB & FileSystem)...")

    conn = get_db_connection()
    total_deleted_db = 0
    total_deleted_files = 0

    try:
        while True:
            # 1. Fetch batch of duplicate result_ids and their html_paths
            with get_cursor(conn) as cur:
                cur.execute("""
                    SELECT r1.result_id, r1.html_path
                    FROM scr_scrape_results r1
                    JOIN scr_scrape_results r2 
                      ON r1.queue_id = r2.queue_id 
                     AND r1.result_id < r2.result_id
                     AND ABS(EXTRACT(EPOCH FROM (r2.scraped_at - r1.scraped_at))) <= 300
                    LIMIT %s
                """, (batch_size,))
                rows = cur.fetchall()

            if not rows:
                break

            result_ids = [r['result_id'] for r in rows]

            # 2. Delete corresponding HTML files from FS/NFS
            for r in rows:
                html_path = r.get('html_path')
                if html_path:
                    full_path = os.path.abspath(html_path)
                    if os.path.exists(full_path):
                        try:
                            os.remove(full_path)
                            total_deleted_files += 1
                        except Exception as e:
                            logger.warning(f"Failed to delete file {full_path}: {e}")

            # 3. Delete duplicate DB rows
            with get_cursor(conn, dict_cursor=False) as cur:
                placeholders = ','.join(['%s'] * len(result_ids))
                cur.execute(f"DELETE FROM scr_scrape_results WHERE result_id IN ({placeholders})", tuple(result_ids))
                conn.commit()

            total_deleted_db += len(result_ids)
            logger.info(f"Progress: removed {total_deleted_db} DB rows, {total_deleted_files} files from FS...")

    except Exception as e:
        logger.error(f"Error during deduplication: {e}", exc_info=True)
    finally:
        conn.close()

    logger.info(f"Deduplication completed! Total DB rows removed: {total_deleted_db}, FS files deleted: {total_deleted_files}.")

if __name__ == '__main__':
    deduplicate_results()
