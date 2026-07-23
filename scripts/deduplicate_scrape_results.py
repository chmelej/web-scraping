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
    total_relinked_parsed = 0

    try:
        while True:
            # Direct self-join finding rapid-fire duplicates (scraped within 5 minutes of another result for the same queue_id)
            with get_cursor(conn) as cur:
                cur.execute("""
                    SELECT DISTINCT ON (a.result_id)
                        a.result_id AS del_id, 
                        a.html_path AS del_path, 
                        b.result_id AS keep_id,
                        b.html_path AS keep_path
                    FROM scr_scrape_results a
                    JOIN scr_scrape_results b 
                      ON a.queue_id = b.queue_id 
                     AND a.scraped_at < b.scraped_at 
                     AND a.scraped_at > b.scraped_at - INTERVAL '5 minutes'
                    WHERE a.status_code = 200 AND b.status_code = 200
                    LIMIT %s
                """, (batch_size,))
                rows = cur.fetchall()

            if not rows:
                break

            del_ids = [r['del_id'] for r in rows]

            # 1. Delete FS files for duplicate results
            for r in rows:
                del_path = r['del_path']
                keep_path = r['keep_path']
                if del_path and del_path != keep_path:
                    full_path = os.path.abspath(del_path)
                    if os.path.exists(full_path):
                        try:
                            os.remove(full_path)
                            total_deleted_files += 1
                        except Exception as e:
                            logger.warning(f"Failed to delete file {full_path}: {e}")

            # 2. Re-link foreign keys in scr_parsed_data to keep_id and delete from scr_scrape_results
            with get_cursor(conn, dict_cursor=False) as cur:
                for r in rows:
                    cur.execute("""
                        UPDATE scr_parsed_data
                        SET result_id = %s
                        WHERE result_id = %s
                    """, (r['keep_id'], r['del_id']))
                    total_relinked_parsed += cur.rowcount

                del_placeholders = ','.join(['%s'] * len(del_ids))
                cur.execute(f"DELETE FROM scr_scrape_results WHERE result_id IN ({del_placeholders})", tuple(del_ids))
                total_deleted_db += cur.rowcount
                conn.commit()

            logger.info(f"Progress: removed {total_deleted_db} DB rows, {total_deleted_files} files from FS, relinked {total_relinked_parsed} parsed rows...")

    except Exception as e:
        logger.error(f"Error during deduplication: {e}", exc_info=True)
    finally:
        conn.close()

    logger.info(f"Deduplication completed! Total DB rows removed: {total_deleted_db}, FS files deleted: {total_deleted_files}, Relinked parsed records: {total_relinked_parsed}.")

if __name__ == '__main__':
    deduplicate_results()
