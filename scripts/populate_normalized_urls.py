#!/usr/bin/env python3
import os
import sys
import psycopg2.extras

# Ensure src module can be imported
sys.path.append(os.getcwd())

from src.utils.db import get_db_connection, get_cursor
from src.utils.urls import normalize_url
from src.utils.logging_config import setup_logging
from config.settings import LOG_DIR

def populate_normalized_urls(batch_size=10000):
    logger = setup_logging('populate_normalized_urls', f"{LOG_DIR}/populate_normalized_urls.log")
    logger.info("Starting population of normalized_url column in scr_scrape_queue...")

    conn = get_db_connection()
    total_updated = 0

    try:
        while True:
            with get_cursor(conn) as cur:
                cur.execute("""
                    SELECT queue_id, url
                    FROM scr_scrape_queue
                    WHERE normalized_url IS NULL
                    LIMIT %s
                """, (batch_size,))
                rows = cur.fetchall()

            if not rows:
                logger.info("No more rows with NULL normalized_url found.")
                break

            updates = [(row['queue_id'], normalize_url(row['url'])) for row in rows]

            with get_cursor(conn, dict_cursor=False) as cur:
                query = """
                    UPDATE scr_scrape_queue AS q
                    SET normalized_url = v.norm_url
                    FROM (VALUES %s) AS v(queue_id, norm_url)
                    WHERE q.queue_id = v.queue_id
                """
                psycopg2.extras.execute_values(cur, query, updates, template="(%s, %s)", page_size=batch_size)
                conn.commit()

            total_updated += len(updates)
            logger.info(f"Populated {total_updated} normalized_url entries...")

    except Exception as e:
        logger.error(f"Error populating normalized_url: {e}", exc_info=True)
    finally:
        conn.close()

    logger.info(f"Finished populating normalized_url! Total rows updated: {total_updated}.")

if __name__ == '__main__':
    populate_normalized_urls()
