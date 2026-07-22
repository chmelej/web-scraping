#!/usr/bin/env python3
import os
import sys
import time

# Ensure src module can be imported
sys.path.append(os.getcwd())

from src.utils.db import get_db_connection, get_cursor
from src.utils.storage import save_raw_html
from src.utils.logging_config import setup_logging
from config.settings import LOG_DIR

def migrate_html_to_disk(batch_size=500):
    logger = setup_logging('migrate_html', f"{LOG_DIR}/migrate_html.log")
    logger.info("Starting migration of raw HTML from database to disk/NFS...")

    conn = get_db_connection()
    total_migrated = 0
    total_bytes_saved = 0

    try:
        while True:
            with get_cursor(conn) as cur:
                cur.execute("""
                    SELECT result_id, url, html
                    FROM scr_scrape_results
                    WHERE html IS NOT NULL AND html != '' AND html_path IS NULL
                    ORDER BY result_id ASC
                    LIMIT %s
                """, (batch_size,))
                rows = cur.fetchall()

            if not rows:
                logger.info("No more HTML records in DB to migrate.")
                break

            logger.info(f"Processing batch of {len(rows)} HTML records...")

            with get_cursor(conn, dict_cursor=False) as cur:
                for row in rows:
                    result_id = row['result_id']
                    url = row['url']
                    html_str = row['html']

                    try:
                        rel_path, uncompressed_size = save_raw_html(url, html_str, result_id=result_id)

                        cur.execute("""
                            UPDATE scr_scrape_results
                            SET html_path = %s,
                                html_size = %s,
                                html = NULL
                            WHERE result_id = %s
                        """, (rel_path, uncompressed_size, result_id))

                        total_migrated += 1
                        total_bytes_saved += len(html_str.encode('utf-8'))
                    except Exception as e:
                        logger.error(f"Error migrating result_id {result_id} ({url}): {e}")

                conn.commit()

            logger.info(f"Migrated {total_migrated} records so far ({total_bytes_saved / (1024*1024):.2f} MB saved from DB)...")

    except Exception as e:
        logger.error(f"Migration error: {e}")
    finally:
        conn.close()

    logger.info(f"Migration completed! Total records moved to disk: {total_migrated}, DB bytes freed: {total_bytes_saved / (1024*1024):.2f} MB.")

if __name__ == '__main__':
    migrate_html_to_disk()
