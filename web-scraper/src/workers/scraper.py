import asyncio
import json
import time
import socket
from datetime import datetime, timedelta
from crawlee.crawlers import PlaywrightCrawler
from crawlee import Request
from src.utils.db import get_db_connection, get_cursor
from src.utils.language import detect_language
from src.utils.urls import extract_domain
from src.utils.logging_config import setup_logging
from src.utils.multipage import find_promising_links
from config.settings import SCRAPE_DELAY, USER_AGENT, MAX_RETRIES, PLAYWRIGHT_HEADLESS, LOG_DIR, SCRAPE_TIMEOUT, REQUEUE_INTERVAL_DAYS

class Scraper:
    def __init__(self):
        self.conn = get_db_connection()
        self.logger = setup_logging('scraper', f'{LOG_DIR}/scraper.log')

    def fetch_batch(self, batch_size=10):
        """Fetch batch of URLs from DB"""
        self.conn.rollback() # Ensure fresh transaction
        self.logger.debug(f"Fetching batch of {batch_size} URLs...")
        with get_cursor(self.conn) as cur:
            cur.execute("""
                SELECT id, url, uni_listing_id, retry_count, depth
                FROM scr_scrape_queue
                WHERE status = 'pending'
                  AND next_scrape_at <= NOW()
                  AND NOT EXISTS (
                      SELECT 1 FROM scr_domain_blacklist 
                      WHERE url LIKE '%%' || domain || '%%'
                  )
                ORDER BY priority DESC, added_at ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            """, (batch_size,))
            rows = cur.fetchall()
            self.logger.debug(f"Fetched {len(rows)} rows from DB")
            return rows

    def update_queue_status_sync(self, queue_id, status, retry_count=None, next_scrape_at=None):
        """Sync update queue status"""
        self.logger.debug(f"Updating queue {queue_id} status to {status}")
        conn = get_db_connection()
        try:
            with get_cursor(conn, dict_cursor=False) as cur:
                updates = ["status = %s"]
                params = [status]
                
                if retry_count is not None:
                    updates.append("retry_count = %s")
                    params.append(retry_count)
                    
                if next_scrape_at is not None:
                    updates.append("next_scrape_at = %s")
                    params.append(next_scrape_at)
                
                params.append(queue_id)
                
                cur.execute(f"""
                    UPDATE scr_scrape_queue
                    SET {', '.join(updates)}
                    WHERE id = %s
                """, tuple(params))
                conn.commit()
        finally:
            conn.close()

    def save_result_sync(self, queue_id, url, scrape_result):
        """Sync save result"""
        self.logger.debug(f"Saving result for {url} (queue_id: {queue_id})")
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
                self.logger.debug(f"Result saved with ID {result_id}")
                return result_id
        finally:
            conn.close()

    def add_subpages_sync(self, parent_id, parent_url, html, language, uni_listing_id, depth):
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
                        (url, uni_listing_id, parent_scrape_id, depth, priority)
                        VALUES (%s, %s, %s, %s, 5)
                        ON CONFLICT (url) DO NOTHING
                     """, (url, uni_listing_id, parent_id, depth + 1))
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
        uni_listing_id = request.user_data.get('uni_listing_id')
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
            self.logger.debug(f"Waiting for content from {request.url}")
            content = await page.content()
            result['html'] = content
            
            # Extract more info from the page/response
            # In PlaywrightCrawler, context.response is available
            if hasattr(context, 'response') and context.response:
                result['status_code'] = context.response.status
                result['headers'] = context.response.headers
                server_addr = await context.response.server_addr()
                if server_addr:
                    result['ip_address'] = server_addr.get('ipAddress')

            if not result['status_code']:
                result['status_code'] = 200

            self.logger.debug(f"Got content for {request.url}, saving result...")

            # Save result (run in executor to not block loop)
            loop = asyncio.get_running_loop()
            result_id = await loop.run_in_executor(None, self.save_result_sync, queue_id, request.url, result)

            # Update status
            next_scrape = datetime.now() + timedelta(days=REQUEUE_INTERVAL_DAYS)
            await loop.run_in_executor(None, self.update_queue_status_sync, queue_id, 'completed', None, next_scrape)

            # Subpages
            if uni_listing_id:
                self.logger.debug(f"Checking for subpages on {request.url}")
                lang, _ = detect_language(content)
                await loop.run_in_executor(None, self.add_subpages_sync, result_id, request.url, content, lang, uni_listing_id, depth)

        except Exception as e:
            self.logger.error(f"Error scraping {request.url}: {e}", exc_info=True)
            result['error'] = str(e)

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.save_result_sync, queue_id, request.url, result)

            if retry_count >= MAX_RETRIES:
                 await loop.run_in_executor(None, self.update_queue_status_sync, queue_id, 'failed')
            else:
                 next_try = datetime.now() + timedelta(hours=1)
                 await loop.run_in_executor(None, self.update_queue_status_sync, queue_id, 'pending', retry_count + 1, next_try)

    async def failed_request_handler(self, context, error):
        """Handle failed requests"""
        request = context.request
        
        queue_id = request.user_data['queue_id']
        retry_count = request.user_data['retry_count']
        
        self.logger.error(f"Request failed for {request.url}: {error}")
        
        result = {
            'html': None,
            'status_code': 0,
            'headers': {},
            'ip_address': None,
            'redirected_from': None,
            'error': str(error)
        }

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.save_result_sync, queue_id, request.url, result)

        if retry_count >= MAX_RETRIES:
             await loop.run_in_executor(None, self.update_queue_status_sync, queue_id, 'failed')
        else:
             next_try = datetime.now() + timedelta(hours=1)
             await loop.run_in_executor(None, self.update_queue_status_sync, queue_id, 'pending', retry_count + 1, next_try)

    def process_one(self):
        """Zpracuje jedno URL (pro testování a debugging)"""
        self.logger.debug("Starting process_one")
        batch = self.fetch_batch(1)
        if not batch:
            self.logger.debug("No items found in batch")
            return False

        item = batch[0]
        self.logger.info(f"Processing one: {item['url']}")

        # Mark as processing
        self.update_queue_status_sync(item['id'], 'processing')

        request_list = [
            Request.from_url(
                item['url'],
                user_data={
                    "queue_id": item['id'],
                    "retry_count": item['retry_count'],
                    "uni_listing_id": item['uni_listing_id'],
                    "depth": item['depth']
                }
            )
        ]

        async def run_crawler():
            self.logger.debug("Initializing PlaywrightCrawler")
            crawler = PlaywrightCrawler(
                request_handler=self.request_handler,
                max_requests_per_crawl=1,
                headless=PLAYWRIGHT_HEADLESS,
                request_handler_timeout=timedelta(seconds=SCRAPE_TIMEOUT),
                browser_launch_options={"args": ["--no-sandbox"]},
            )
            crawler.failed_request_handler = self.failed_request_handler
            self.logger.debug("Running crawler")
            await crawler.run(request_list)
            self.logger.debug("Crawler finished")

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
            request_handler_timeout=timedelta(seconds=SCRAPE_TIMEOUT),
            browser_launch_options={"args": ["--no-sandbox"]},
        )
        crawler.failed_request_handler = self.failed_request_handler

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
                request_list.append(
                    Request.from_url(
                        item['url'],
                        user_data={
                            "queue_id": item['id'],
                            "retry_count": item['retry_count'],
                            "uni_listing_id": item['uni_listing_id'],
                            "depth": item['depth']
                        }
                    )
                )

            # Run crawler on this batch
            await crawler.run(request_list)

if __name__ == '__main__':
    scraper = Scraper()
    asyncio.run(scraper.run())
