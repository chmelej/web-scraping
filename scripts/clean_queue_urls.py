#!/usr/bin/env python3
import os
import sys
import psycopg2.extras

# Ensure src module can be imported
sys.path.append(os.getcwd())

from src.utils.db import get_db_connection, get_cursor
from src.utils.urls import clean_url, unify_url
from src.utils.logging_config import setup_logging
from config.settings import LOG_DIR

def clean_queue_urls():
    """
    Cleans queue URLs containing tracking parameters or uncleaned query strings in bulk.
    If cleaning results in an existing URL, relinks scrape results & following_queue_id
    and deletes the duplicate queue entry.
    """
    logger = setup_logging('clean_queue_urls', f"{LOG_DIR}/clean_queue_urls.log")
    logger.info("Starting bulk cleanup of tracking/uncleaned URLs in scr_scrape_queue...")

    conn = get_db_connection()
    try:
        # 1. Fetch all candidate rows with '?'
        with get_cursor(conn) as cur:
            cur.execute("""
                SELECT queue_id, url, url_hash
                FROM scr_scrape_queue
                WHERE url LIKE '%%?%%'
            """)
            rows = cur.fetchall()

        logger.info(f"Loaded {len(rows)} candidate rows with '?' from scr_scrape_queue.")

        if not rows:
            return

        # 2. Build existing URL lookups from DB for fast in-memory matching
        logger.info("Building in-memory URL map from scr_scrape_queue...")
        with get_cursor(conn) as cur:
            cur.execute("SELECT queue_id, url, url_hash FROM scr_scrape_queue")
            all_queue = cur.fetchall()

        url_map = {}
        norm_map = {}
        for r in all_queue:
            q_id = r['queue_id']
            url_map[r['url']] = q_id
            if r['url_hash']:
                norm_map[r['url_hash']] = q_id

        updates_in_place = [] # list of (queue_id, clean_url, norm_url)
        merges = [] # list of (bad_queue_id, target_queue_id, clean_url)

        logger.info("Analyzing URLs for cleaning and merging...")
        for r in rows:
            q_id = r['queue_id']
            raw_url = r['url']

            c_url = clean_url(raw_url)
            n_url = unify_url(raw_url)

            if c_url == raw_url:
                continue

            target_id = url_map.get(c_url) or norm_map.get(n_url)
            if target_id and target_id != q_id:
                merges.append((q_id, target_id, c_url))
            else:
                updates_in_place.append((q_id, c_url, n_url))
                url_map[c_url] = q_id
                norm_map[n_url] = q_id

        logger.info(f"Analysis completed: {len(updates_in_place)} in-place updates, {len(merges)} merges/deletions.")

        # 3. Execute in-place updates
        if updates_in_place:
            logger.info("Executing in-place queue updates...")
            with get_cursor(conn, dict_cursor=False) as cur:
                query_q = """
                    UPDATE scr_scrape_queue AS q
                    SET url = v.c_url, url_hash = v.n_url
                    FROM (VALUES %s) AS v(queue_id, c_url, n_url)
                    WHERE q.queue_id = v.queue_id
                """
                psycopg2.extras.execute_values(cur, query_q, updates_in_place, template="(%s, %s, %s)", page_size=10000)

                results_tuples = [(t[0], t[1]) for t in updates_in_place]
                query_r = """
                    UPDATE scr_scrape_results AS r
                    SET url = v.c_url
                    FROM (VALUES %s) AS v(queue_id, c_url)
                    WHERE r.queue_id = v.queue_id
                """
                psycopg2.extras.execute_values(cur, query_r, results_tuples, template="(%s, %s)", page_size=10000)
                conn.commit()

        # 4. Execute merges and deletions
        if merges:
            logger.info("Executing merges and deletions...")
            with get_cursor(conn, dict_cursor=False) as cur:
                query_relink = """
                    UPDATE scr_scrape_results AS r
                    SET queue_id = v.target_id, url = v.c_url
                    FROM (VALUES %s) AS v(bad_id, target_id, c_url)
                    WHERE r.queue_id = v.bad_id
                """
                psycopg2.extras.execute_values(cur, query_relink, merges, template="(%s, %s, %s)", page_size=10000)

                flk_tuples = [(t[0], t[1]) for t in merges]
                query_flk = """
                    UPDATE scr_scrape_queue AS q
                    SET following_queue_id = v.target_id
                    FROM (VALUES %s) AS v(bad_id, target_id)
                    WHERE q.following_queue_id = v.bad_id
                """
                psycopg2.extras.execute_values(cur, query_flk, flk_tuples, template="(%s, %s)", page_size=10000)

                bad_ids = [(t[0],) for t in merges]
                query_del = """
                    DELETE FROM scr_scrape_queue AS q
                    USING (VALUES %s) AS v(bad_id)
                    WHERE q.queue_id = v.bad_id
                """
                psycopg2.extras.execute_values(cur, query_del, bad_ids, template="(%s)", page_size=10000)
                conn.commit()

        logger.info(f"Cleanup completed! Updated in-place: {len(updates_in_place)}, Merged/Deleted: {len(merges)}.")

    except Exception as e:
        logger.error(f"Error during queue URL cleanup: {e}", exc_info=True)
    finally:
        conn.close()

if __name__ == '__main__':
    clean_queue_urls()
