#!/usr/bin/env python3
import os
import sys
import re

# Ensure src module can be imported
sys.path.append(os.getcwd())

from src.utils.db import get_db_connection, get_cursor
from src.utils.logging_config import setup_logging
from config.settings import LOG_DIR

def fix_url(bad_url: str) -> str:
    url = bad_url
    if url.startswith('http://s.www.'):
        url = 'https://www.' + url[len('http://s.www.'):]
    elif url.startswith('http://s.'):
        url = 'https://' + url[len('http://s.'):]
    elif url.startswith('https://s.www.'):
        url = 'https://www.' + url[len('https://s.www.'):]
    elif url.startswith('https://s.'):
        url = 'https://' + url[len('https://s.'):]
    elif url.startswith('http://htts.www.'):
        url = 'https://www.' + url[len('http://htts.www.'):]
    elif url.startswith('http://htts.'):
        url = 'https://' + url[len('http://htts.'):]
    elif url.startswith('https://htts.www.'):
        url = 'https://www.' + url[len('https://htts.www.'):]
    elif url.startswith('https://htts.'):
        url = 'https://' + url[len('https://htts.'):]
    return url

def fix_bad_urls(batch_size=1000):
    logger = setup_logging('fix_bad_urls', f"{LOG_DIR}/fix_bad_urls.log")
    logger.info("Starting cleanup of bad imported URLs in scr_scrape_queue and scr_scrape_results...")

    conn = get_db_connection()
    total_updated = 0
    total_merged = 0

    try:
        while True:
            with get_cursor(conn) as cur:
                cur.execute("""
                    SELECT queue_id, url
                    FROM scr_scrape_queue
                    WHERE url LIKE 'http://s.%%' OR url LIKE 'https://s.%%' OR url LIKE '%%htts.%%'
                    ORDER BY queue_id ASC
                    LIMIT %s
                """, (batch_size,))
                rows = cur.fetchall()

            if not rows:
                logger.info("No more bad URLs found in scr_scrape_queue.")
                break

            logger.info(f"Processing batch of {len(rows)} bad URL records...")

            with get_cursor(conn, dict_cursor=False) as cur:
                for row in rows:
                    bad_queue_id = row['queue_id']
                    bad_url = row['url']
                    corrected_url = fix_url(bad_url)

                    if corrected_url == bad_url:
                        continue

                    # Check if corrected_url already exists in scr_scrape_queue
                    cur.execute("SELECT queue_id FROM scr_scrape_queue WHERE url = %s", (corrected_url,))
                    existing_row = cur.fetchone()

                    if existing_row:
                        existing_queue_id = existing_row[0]
                        # Transfer results dependency
                        cur.execute("""
                            UPDATE scr_scrape_results
                            SET queue_id = %s, url = %s
                            WHERE queue_id = %s
                        """, (existing_queue_id, corrected_url, bad_queue_id))
                        # Delete bad queue row
                        cur.execute("DELETE FROM scr_scrape_queue WHERE queue_id = %s", (bad_queue_id,))
                        total_merged += 1
                    else:
                        # Update queue row
                        cur.execute("UPDATE scr_scrape_queue SET url = %s WHERE queue_id = %s", (corrected_url, bad_queue_id))
                        # Update results row for consistency
                        cur.execute("""
                            UPDATE scr_scrape_results
                            SET url = %s
                            WHERE queue_id = %s AND url = %s
                        """, (corrected_url, bad_queue_id, bad_url))
                        total_updated += 1

                conn.commit()

            logger.info(f"Progress: {total_updated} updated, {total_merged} merged/deleted...")

    except Exception as e:
        logger.error(f"Error fixing bad URLs: {e}", exc_info=True)
    finally:
        conn.close()

    logger.info(f"URL cleanup finished! Total updated: {total_updated}, Total merged & deleted: {total_merged}.")

if __name__ == '__main__':
    fix_bad_urls()
