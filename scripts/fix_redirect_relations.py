#!/usr/bin/env python3
import os
import sys

# Ensure src module can be imported
sys.path.append(os.getcwd())

from src.utils.db import get_db_connection, get_cursor
from src.utils.logging_config import setup_logging
from config.settings import LOG_DIR

def fix_redirect_relations():
    """
    Creates temporary table fix_relations and performs 3 control & repair actions:
    1) Fix scr_scrape_results.queue_id to match working_queue_id for HTTP 200
    2) Set scr_scrape_queue.following_queue_id = working_queue_id for redirected orig_queue_id
    3) Update orig_queue_id status = 'redirected' if it was marked as 'completed'
    """
    logger = setup_logging('fix_redirect_relations', f"{LOG_DIR}/fix_redirect_relations.log")
    logger.info("Starting check and repair of redirect relations...")

    conn = get_db_connection()
    try:
        with get_cursor(conn, dict_cursor=False) as cur:
            # Create temp table fix_relations
            logger.info("Building temporary table fix_relations...")
            cur.execute("""
                CREATE TEMPORARY TABLE fix_relations AS
                SELECT 
                    qp.queue_id AS orig_queue_id, 
                    qf.queue_id AS working_queue_id, 
                    r.result_id, 
                    qp.status AS orig_status, 
                    qf.status AS working_status, 
                    r.status_code, 
                    r.queue_id AS response_queue_id, 
                    qp.following_queue_id 
                FROM scr_scrape_results r
                JOIN scr_scrape_queue qp ON qp.url = r.redirected_from
                JOIN scr_scrape_queue qf ON qf.url = r.url 
                WHERE qp.queue_id != qf.queue_id;
            """)

            # Control & Fix 1: response_queue_id vs working_queue_id
            cur.execute("""
                UPDATE scr_scrape_results r
                SET queue_id = f.working_queue_id
                FROM fix_relations f
                WHERE r.result_id = f.result_id
                  AND f.status_code = 200
                  AND f.working_queue_id IS DISTINCT FROM f.response_queue_id;
            """)
            cnt1 = cur.rowcount
            logger.info(f"Control 1: Fixed {cnt1} rows in scr_scrape_results.queue_id.")

            # Control & Fix 2: following_queue_id vs working_queue_id
            cur.execute("""
                UPDATE scr_scrape_queue q
                SET following_queue_id = f.working_queue_id
                FROM (
                    SELECT DISTINCT orig_queue_id, working_queue_id
                    FROM fix_relations
                    WHERE working_queue_id IS DISTINCT FROM following_queue_id
                ) f
                WHERE q.queue_id = f.orig_queue_id;
            """)
            cnt2 = cur.rowcount
            logger.info(f"Control 2: Fixed {cnt2} rows in scr_scrape_queue.following_queue_id.")

            # Control & Fix 3: orig_status should be 'redirected'
            cur.execute("""
                UPDATE scr_scrape_queue q
                SET status = 'redirected'
                FROM (
                    SELECT DISTINCT orig_queue_id
                    FROM fix_relations
                    WHERE orig_status != 'redirected'
                ) f
                WHERE q.queue_id = f.orig_queue_id;
            """)
            cnt3 = cur.rowcount
            logger.info(f"Control 3: Fixed {cnt3} rows in scr_scrape_queue.status -> 'redirected'.")

            conn.commit()
            logger.info("Redirect relations repair completed successfully!")

    except Exception as e:
        logger.error(f"Error repairing redirect relations: {e}", exc_info=True)
    finally:
        conn.close()

if __name__ == '__main__':
    fix_redirect_relations()
