#!/usr/bin/env python3
import os
import sys
import psycopg2.extras

# Ensure src module can be imported
sys.path.append(os.getcwd())

from src.utils.db import get_db_connection, get_cursor
from src.utils.urls import unify_url
from src.utils.logging_config import setup_logging
from config.settings import LOG_DIR

def populate_url_hash(batch_size=10000, force_repopulate=True):
    logger = setup_logging('populate_url_hash', f"{LOG_DIR}/populate_url_hash.log")
    logger.info("Starting population/unification of url_hash column in scr_scrape_queue...")

    conn = get_db_connection()
    total_updated = 0

    try:
        while True:
            with get_cursor(conn) as cur:
                if force_repopulate:
                    cur.execute("""
                        SELECT queue_id, url
                        FROM scr_scrape_queue
                        WHERE url_hash IS NULL OR url_hash LIKE 'http%%' OR url_hash LIKE 'www.%%'
                        LIMIT %s
                    """, (batch_size,))
                else:
                    cur.execute("""
                        SELECT queue_id, url
                        FROM scr_scrape_queue
                        WHERE url_hash IS NULL
                        LIMIT %s
                    """, (batch_size,))
                rows = cur.fetchall()

            if not rows:
                logger.info("No more rows to update found.")
                break

            updates = [(row['queue_id'], unify_url(row['url'])) for row in rows]

            with get_cursor(conn, dict_cursor=False) as cur:
                query = """
                    UPDATE scr_scrape_queue AS q
                    SET url_hash = v.norm_url
                    FROM (VALUES %s) AS v(queue_id, norm_url)
                    WHERE q.queue_id = v.queue_id
                """
                psycopg2.extras.execute_values(cur, query, updates, template="(%s, %s)", page_size=batch_size)
                conn.commit()

            total_updated += len(updates)
            logger.info(f"Populated/Unified {total_updated} url_hash entries...")

    except Exception as e:
        logger.error(f"Error populating url_hash: {e}", exc_info=True)
    finally:
        conn.close()

    logger.info(f"Finished populating url_hash! Total rows updated: {total_updated}.")

if __name__ == '__main__':
    populate_url_hash()
