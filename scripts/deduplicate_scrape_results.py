#!/usr/bin/env python3
import os
import sys

# Ensure src module can be imported
sys.path.append(os.getcwd())

from src.utils.db import get_db_connection, get_cursor
from src.utils.logging_config import setup_logging
from config.settings import LOG_DIR

def deduplicate_results(batch_queue_size=200):
    logger = setup_logging('deduplicate_results', f"{LOG_DIR}/deduplicate_results.log")
    logger.info("Starting cleanup of rapid-fire duplicate scrape_results (DB & FileSystem)...")

    conn = get_db_connection()
    total_deleted_db = 0
    total_deleted_files = 0
    total_relinked_parsed = 0

    try:
        while True:
            # 1. Fetch a batch of queue_ids that have duplicate results
            with get_cursor(conn) as cur:
                cur.execute("""
                    SELECT queue_id
                    FROM scr_scrape_results
                    GROUP BY queue_id
                    HAVING COUNT(*) > 1
                    LIMIT %s
                """, (batch_queue_size,))
                queue_rows = cur.fetchall()

            if not queue_rows:
                break

            queue_ids = [r['queue_id'] for r in queue_rows]

            with get_cursor(conn, dict_cursor=False) as cur:
                for qid in queue_ids:
                    # Select all results for this queue_id, prioritizing processed/parsed records
                    cur.execute("""
                        SELECT r.result_id, r.html_path, r.processing_status,
                               EXISTS (SELECT 1 FROM scr_parsed_data p WHERE p.result_id = r.result_id) as is_parsed
                        FROM scr_scrape_results r
                        WHERE r.queue_id = %s
                        ORDER BY (CASE WHEN r.processing_status = 'processed' THEN 2 
                                       WHEN EXISTS (SELECT 1 FROM scr_parsed_data p WHERE p.result_id = r.result_id) THEN 1 
                                       ELSE 0 END) DESC, 
                                 r.result_id DESC
                    """, (qid,))
                    results = cur.fetchall()

                    if len(results) <= 1:
                        continue

                    # Kept record is the first element
                    kept_id = results[0][0]
                    kept_path = results[0][1]

                    to_delete_ids = []
                    for row in results[1:]:
                        del_id = row[0]
                        del_path = row[1]
                        to_delete_ids.append(del_id)

                        # Delete FS file if path exists and differs from kept_path
                        if del_path and del_path != kept_path:
                            full_path = os.path.abspath(del_path)
                            if os.path.exists(full_path):
                                try:
                                    os.remove(full_path)
                                    total_deleted_files += 1
                                except Exception as e:
                                    logger.warning(f"Failed to delete file {full_path}: {e}")

                    # Re-link any foreign keys in scr_parsed_data to kept_id
                    del_placeholders = ','.join(['%s'] * len(to_delete_ids))
                    cur.execute(f"""
                        UPDATE scr_parsed_data
                        SET result_id = %s
                        WHERE result_id IN ({del_placeholders})
                    """, [kept_id] + to_delete_ids)
                    total_relinked_parsed += cur.rowcount

                    # Delete duplicate DB rows from scr_scrape_results
                    cur.execute(f"""
                        DELETE FROM scr_scrape_results
                        WHERE result_id IN ({del_placeholders})
                    """, tuple(to_delete_ids))
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
