#!/usr/bin/env python3
import os
import sys
from datetime import timedelta
import psycopg2.extras

# Ensure src module can be imported
sys.path.append(os.getcwd())

from src.utils.db import get_db_connection, get_cursor
from src.utils.urls import clean_url, unify_url
from src.utils.logging_config import setup_logging
from config.settings import LOG_DIR, REQUEUE_INTERVAL_DAYS

def sync_missing_results_to_queue(batch_size=10000):
    """
    Finds URLs in scr_scrape_results with status_code=200 that are missing from scr_scrape_queue,
    and inserts them into scr_scrape_queue as status='completed'. Also links results.queue_id.
    """
    logger = setup_logging('sync_missing_results', f"{LOG_DIR}/sync_missing_results.log")
    logger.info("Starting sync of missing scrape_results (HTTP 200) to scr_scrape_queue...")

    conn = get_db_connection()
    total_inserted = 0
    total_relinked = 0

    try:
        while True:
            # 1. Fetch batch of missing URLs from scr_scrape_results
            with get_cursor(conn) as cur:
                cur.execute("""
                    SELECT r.url, MAX(r.scraped_at) as max_scraped, MIN(r.scraped_at) as min_scraped
                    FROM scr_scrape_results r
                    WHERE r.status_code = 200
                      AND NOT EXISTS (
                          SELECT 1 FROM scr_scrape_queue q WHERE q.url = r.url
                      )
                    GROUP BY r.url
                    LIMIT %s
                """, (batch_size,))
                rows = cur.fetchall()

            if not rows:
                logger.info("No more missing URLs found.")
                break

            insert_tuples = []
            requeue_days = int(REQUEUE_INTERVAL_DAYS)

            for r in rows:
                raw_url = r['url']
                c_url = clean_url(raw_url)
                norm_url = unify_url(raw_url)
                max_scraped = r['max_scraped']
                min_scraped = r['min_scraped']
                next_scrape = max_scraped + timedelta(days=requeue_days) if max_scraped else None

                insert_tuples.append((
                    c_url, norm_url, 'completed', 0, next_scrape, min_scraped, 5, max_scraped
                ))

            # Deduplicate insert tuples by c_url in this batch
            seen_urls = set()
            unique_tuples = []
            for t in insert_tuples:
                u = t[0]
                if u not in seen_urls:
                    seen_urls.add(u)
                    unique_tuples.append(t)

            # 2. Bulk insert into scr_scrape_queue
            with get_cursor(conn, dict_cursor=False) as cur:
                query = """
                    INSERT INTO scr_scrape_queue
                    (url, url_hash, status, retry_count, next_scrape_at, added_at, priority, last_scrape_at)
                    VALUES %s
                    ON CONFLICT (url) DO UPDATE
                    SET url_hash = EXCLUDED.url_hash,
                        status = COALESCE(scr_scrape_queue.status, EXCLUDED.status),
                        last_scrape_at = COALESCE(scr_scrape_queue.last_scrape_at, EXCLUDED.last_scrape_at)
                """
                psycopg2.extras.execute_values(cur, query, unique_tuples, template="(%s, %s, %s, %s, %s, %s, %s, %s)", page_size=batch_size)
                total_inserted += len(unique_tuples)
                conn.commit()

            logger.info(f"Progress: inserted/updated {total_inserted} URLs in scr_scrape_queue...")

        # 3. Relink scr_scrape_results.queue_id to newly inserted queue_ids
        logger.info("Relinking scr_scrape_results.queue_id to scr_scrape_queue...")
        with get_cursor(conn, dict_cursor=False) as cur:
            cur.execute("""
                UPDATE scr_scrape_results r
                SET queue_id = q.queue_id
                FROM scr_scrape_queue q
                WHERE r.url = q.url
                  AND (r.queue_id IS NULL OR r.queue_id != q.queue_id);
            """)
            total_relinked = cur.rowcount
            conn.commit()

        logger.info(f"Relinked {total_relinked} rows in scr_scrape_results to their queue_id.")

    except Exception as e:
        logger.error(f"Error syncing missing results to queue: {e}", exc_info=True)
    finally:
        conn.close()

    logger.info(f"Sync completed! Total queue items inserted: {total_inserted}, Results relinked: {total_relinked}.")

if __name__ == '__main__':
    sync_missing_results_to_queue()
