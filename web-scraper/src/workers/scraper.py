import asyncio
import json
import time
import socket
from datetime import datetime, timedelta
from crawlee.crawlers import PlaywrightCrawler
from src.utils.db import get_db_connection, get_cursor
from src.utils.language import detect_language
from src.utils.urls import extract_domain
from src.utils.logging_config import setup_logging
from src.utils.multipage import find_promising_links
from config.settings import SCRAPE_DELAY, USER_AGENT, MAX_RETRIES, PLAYWRIGHT_HEADLESS, LOG_DIR

class Scraper:
    def __init__(self):
        self.conn = get_db_connection()
        self.logger = setup_logging('scraper', f'{LOG_DIR}/scraper.log')

    def fetch_batch(self, batch_size=10):
        """Fetch batch of URLs from DB"""
        with get_cursor(self.conn) as cur:
            cur.execute("""
                SELECT id, url, unit_listing_id, retry_count, depth
                FROM scr_scrape_queue
                WHERE status = 'pending'
                  AND next_scrape_at <= NOW()
                  AND url NOT LIKE ANY(
                      SELECT '%' || domain || '%' FROM scr_domain_blacklist
                  )
                ORDER BY priority DESC, added_at ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            """, (batch_size,))
            return cur.fetchall()

    def update_queue_status_sync(self, queue_id, status, retry_count=None, next_scrape_at=None):
        """Sync update queue status"""
        conn = get_db_connection()
        try:
            with get_cursor(conn, dict_cursor=False) as cur:
                if retry_count is not None:
                    cur.execute("""
                        UPDATE scr_scrape_queue
                        SET status = %s, retry_count = %s, next_scrape_at = %s
                        WHERE id = %s
                    """, (status, retry_count, next_scrape_at, queue_id))
                else:
                    cur.execute("""
                        UPDATE scr_scrape_queue SET status = %s WHERE id = %s
                    """, (status, queue_id))
                conn.commit()
        finally:
            conn.close()

    def save_result_sync(self, queue_id, url, scrape_result):
        """Sync save result"""
        conn = get_db_connection()
        try:
            with get_cursor(conn, dict_cursor=False) as cur:
                lang, lang_conf = 'unknown', 0.0
                if scrape_result.get('html'):
                    lang, lang_conf = detect_language(scrape_result['html'])

                cur.execute("""
                    INSERT INTO scr_scrape_results
                    (queue_id, url, html, status_code, headers, ip_address,
                     redirected_from, detected_language, language_confidence, error_message)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    queue_id, url, scrape_result.get('html'), scrape_result.get('status_code'),
                    json.dumps(scrape_result.get('headers')) if scrape_result.get('headers') else None,
                    scrape_result.get('ip_address'),
                    scrape_result.get('redirected_from'), lang, lang_conf,
                    scrape_result.get('error')
                ))
                result_id = cur.fetchone()[0]
                conn.commit()
                return result_id
        finally:
            conn.close()

    def add_subpages_sync(self, parent_id, parent_url, html, language, unit_listing_id, depth):
         conn = get_db_connection()
         try:
             # get max depth
             domain = extract_domain(parent_url)
             max_depth = 2
             with get_cursor(conn) as cur:
                 cur.execute("SELECT max_depth FROM scr_domain_multipage_rules WHERE domain = %s AND enabled = TRUE", (domain,))
                 row = cur.fetchone()
                 if row: max_depth = row['max_depth']

             if depth >= max_depth: return

             promising = find_promising_links(html, parent_url, language)
             with get_cursor(conn, dict_cursor=False) as cur:
                 for url, category in promising:
                     cur.execute("""
                        INSERT INTO scr_scrape_queue
                        (url, unit_listing_id, parent_scrape_id, depth, priority)
                        VALUES (%s, %s, %s, %s, 5)
                        ON CONFLICT (url, unit_listing_id) DO NOTHING
                     """, (url, unit_listing_id, parent_id, depth + 1))
                 conn.commit()

             if promising:
                 self.logger.info(f"  -> Added {len(promising)} sub-pages to queue")
         finally:
             conn.close()

    async def request_handler(self, context):
        request = context.request
        page = context.page

        # User data passed via request.user_data
        queue_id = request.user_data['queue_id']
        retry_count = request.user_data['retry_count']
        unit_listing_id = request.user_data.get('unit_listing_id')
        depth = request.user_data.get('depth', 0)

        self.logger.info(f"Processing {request.url}")

        result = {
            'html': None,
            'status_code': 0,
            'headers': {},
            'ip_address': None,
            'redirected_from': None,
            'error': None
        }

        try:
            # Wait for content
            content = await page.content()
            result['html'] = content
            result['status_code'] = 200 # Assumed success if page loaded

            # Try to get real status if possible via page.request.response(), but crawlee handles basic load

            # Save result (run in executor to not block loop)
            loop = asyncio.get_running_loop()
            result_id = await loop.run_in_executor(None, self.save_result_sync, queue_id, request.url, result)

            # Update status
            await loop.run_in_executor(None, self.update_queue_status_sync, queue_id, 'completed')

            # Subpages
            if unit_listing_id:
                lang, _ = detect_language(content)
                await loop.run_in_executor(None, self.add_subpages_sync, result_id, request.url, content, lang, unit_listing_id, depth)

        except Exception as e:
            self.logger.error(f"Error scraping {request.url}: {e}")
            result['error'] = str(e)

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.save_result_sync, queue_id, request.url, result)

            if retry_count >= MAX_RETRIES:
                 await loop.run_in_executor(None, self.update_queue_status_sync, queue_id, 'failed')
            else:
                 next_try = datetime.now() + timedelta(hours=1)
                 await loop.run_in_executor(None, self.update_queue_status_sync, queue_id, 'pending', retry_count + 1, next_try)

    def process_one(self):
        """Zpracuje jedno URL (pro testování a debugging)"""
        batch = self.fetch_batch(1)
        if not batch:
            return False

        item = batch[0]
        self.logger.info(f"Processing one: {item['url']}")

        # Mark as processing
        self.update_queue_status_sync(item['id'], 'processing')

        request_list = [{
            "url": item['url'],
            "user_data": {
                "queue_id": item['id'],
                "retry_count": item['retry_count'],
                "unit_listing_id": item['unit_listing_id'],
                "depth": item['depth']
            }
        }]

        async def run_crawler():
            crawler = PlaywrightCrawler(
                request_handler=self.request_handler,
                max_requests_per_crawl=1,
                headless=PLAYWRIGHT_HEADLESS,
            )
            await crawler.run(request_list)

        try:
             # Check if there is a running loop
             try:
                 loop = asyncio.get_running_loop()
             except RuntimeError:
                 loop = None

             if loop and loop.is_running():
                 # This shouldn't happen in normal synchronous call, but if so, we create task
                 future = asyncio.run_coroutine_threadsafe(run_crawler(), loop)
                 future.result()
             else:
                 asyncio.run(run_crawler())

             return True
        except Exception as e:
             self.logger.error(f"Error in process_one: {e}")
             return False

    async def run(self):
        self.logger.info("Starting Crawlee Scraper...")

        # Configure Crawler with masking features
        crawler = PlaywrightCrawler(
            request_handler=self.request_handler,
            max_requests_per_crawl=50,
            headless=PLAYWRIGHT_HEADLESS,
            # Crawlee for Python uses smart defaults for masking.
            # We can enable more robust fingerprinting here if API supports it explicitly,
            # but usually it's automatic with PlaywrightCrawler.
        )

        while True:
            # Fetch batch
            batch = self.fetch_batch(10)
            if not batch:
                self.logger.info("Queue empty, waiting...")
                await asyncio.sleep(60)
                continue

            self.logger.info(f"Fetched {len(batch)} URLs")

            request_list = []
            for item in batch:
                # Mark as processing immediately
                self.update_queue_status_sync(item['id'], 'processing')
                request_list.append({
                    "url": item['url'],
                    "user_data": {
                        "queue_id": item['id'],
                        "retry_count": item['retry_count'],
                        "unit_listing_id": item['unit_listing_id'],
                        "depth": item['depth']
                    }
                })

            # Run crawler on this batch
            await crawler.run(request_list)

if __name__ == '__main__':
    scraper = Scraper()
    asyncio.run(scraper.run())
