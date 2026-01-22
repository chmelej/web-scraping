import asyncio
import json
import time
import socket
import logging
import shutil
import glob
import tempfile
import os
import sys
import subprocess
from datetime import datetime, timedelta
from crawlee import Request
from crawlee.crawlers import PlaywrightCrawler
from crawlee import Request
from crawlee.storage_clients import MemoryStorageClient
from crawlee.configuration import Configuration
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
        # Suppress verbose Crawlee errors (stack traces for 404s/DNS)
        # logging.getLogger('crawlee.crawlers._playwright._playwright_crawler').setLevel(logging.CRITICAL)

    def cleanup_temp_dirs(self):
        """Clean up temporary directories created by Playwright/Crawlee and kill zombies"""
        try:
            # 1. Kill zombie chromium processes (Linux only)
            if sys.platform.startswith('linux'):
                try:
                    subprocess.run(["pkill", "-f", "chromium"], capture_output=True)
                    subprocess.run(["pkill", "-f", "chrome"], capture_output=True)
                except Exception:
                    pass

            # 2. Clean temp dirs
            tmp_dir = tempfile.gettempdir()
            # Pattern observed by user
            pattern = os.path.join(tmp_dir, "apify-playwright-*") 
            count = 0
            for path in glob.glob(pattern):
                # Safety: check if it looks like a temp dir and is a directory
                if os.path.isdir(path):
                    try:
                        shutil.rmtree(path, ignore_errors=True)
                        count += 1
                    except Exception:
                        pass

            if count > 0:
                self.logger.debug(f"Cleaned up {count} temporary Playwright directories")
        except Exception as e:
            self.logger.warning(f"Failed to clean up temp dirs: {e}")

    def reset_crawlee_global_state(self):
        """Reset Crawlee global state to prevent ServiceConflictError and cache accumulation"""
        self.logger.debug("Resetting Crawlee global state")
        try:
            from crawlee import service_locator
            # Reset the service locator's internal state
            service_locator._configuration = None
            service_locator._event_manager = None
            service_locator._storage_client = None
            # Clear the storage instance manager cache
            if hasattr(service_locator, 'storage_instance_manager'):
                 service_locator.storage_instance_manager.clear_cache()
        except Exception as e:
            self.logger.warning(f"Failed to reset Crawlee global state: {e}")

    def fetch_batch(self, batch_size=20):
        """Fetch batch of URLs from DB"""
        self.conn.rollback() # Ensure fresh transaction
        self.logger.debug(f"Fetching batch of {batch_size} URLs...")
        with get_cursor(self.conn) as cur:
            cur.execute("""
                SELECT queue_id, url, uni_listing_id, opco, retry_count, depth
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
        self.logger.debug(f"Saving result for {url} (queue_id: {queue_id})")
        conn = get_db_connection()
        try:
            with get_cursor(conn, dict_cursor=False) as cur:
                lang, lang_conf = None, 0.0
                if scrape_result.get('html'):
                    lang, lang_conf = detect_language(scrape_result['html'])

                cur.execute("""
                    INSERT INTO scr_scrape_results
                    (queue_id, url, html, status_code, headers, ip_address,
                     redirected_from, detected_language, language_confidence, error_message)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING result_id
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

    def reconcile_batch_sync(self, batch_ids):
        """Ensure no items are left in processing state after batch"""
        if not batch_ids:
            return
            
        self.logger.debug(f"Reconciling batch of {len(batch_ids)} items...")
        conn = get_db_connection()
        try:
            with get_cursor(conn, dict_cursor=False) as cur:
                # Placeholders for IN clause
                placeholders = ','.join(['%s'] * len(batch_ids))
                query = f"""
                    UPDATE scr_scrape_queue
                    SET status = 'failed'
                    WHERE queue_id IN ({placeholders})
                      AND status = 'processing'
                """
                cur.execute(query, tuple(batch_ids))
                count = cur.rowcount
                conn.commit()
                if count > 0:
                    self.logger.warning(f"Reconciled {count} stuck items in batch (set to failed)")
        except Exception as e:
            self.logger.error(f"Error reconciling batch: {e}")
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
            # Enforce a hard timeout on the page content retrieval
            # This protects against Playwright hanging internally
            self.logger.debug(f"Waiting for content from {request.url}")
            
            # Retry logic for "Execution context was destroyed" (client-side redirects)
            for attempt in range(3):
                try:
                    content = await page.content()
                    break # Success
                except Exception as e:
                    if "Execution context was destroyed" in str(e) and attempt < 2:
                        self.logger.warning(f"Execution context destroyed for {request.url}, retrying ({attempt+1}/3)...")
                        await asyncio.sleep(1) # Wait for navigation/redirect to settle
                        continue
                    raise e # Re-raise if not handled or max retries reached
            
            result['html'] = content
            
            # Check for redirect (client-side or server-side)
            # If the page URL is different from the request URL, we should treat it as a redirect
            # and potentially enqueue the new URL if it wasn't a standard 3xx redirect handled by Playwright
            final_url = page.url
            if final_url != request.url:
                 self.logger.info(f"Redirect detected: {request.url} -> {final_url}")
                 result['redirected_from'] = request.url
                 # We still save the content under the ORIGINAL queue_id, effectively treating it as
                 # "we asked for X, we got content for Y". This is usually fine.
                 # However, if we want to explicitly track Y as a new item, we'd need to add it to the queue.
                 # For now, just logging it and saving the content is sufficient for most cases.
            
            # Extract more info from the page/response
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
            
            self.logger.info(f"Finished processing {request.url}")

        except Exception as e:
            self.logger.warning(f"Error scraping {request.url}: {e}")
            result['error'] = str(e)

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.save_result_sync, queue_id, request.url, result)

            if retry_count >= MAX_RETRIES:
                 await loop.run_in_executor(None, self.update_queue_status_sync, queue_id, 'failed')
            else:
                 next_try = datetime.now() + timedelta(hours=1)
                 await loop.run_in_executor(None, self.update_queue_status_sync, queue_id, 'pending', retry_count + 1, next_try)
            
            self.logger.info(f"Finished processing (failed) {request.url}")

    async def failed_request_handler(self, context, error):
        """Handle failed requests"""
        request = context.request
        
        queue_id = request.user_data['queue_id']
        retry_count = request.user_data['retry_count']
        
        # Simple one-line warning
        self.logger.warning(f"Page unavailable: {request.url} ({error})")
        
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
        self.update_queue_status_sync(item['queue_id'], 'processing')

        request_list = [
            Request.from_url(
                item['url'],
                user_data={
                    "queue_id": item['queue_id'],
                    "retry_count": item['retry_count'],
                    "uni_listing_id": item['uni_listing_id'],
                    "opco": item.get('opco'),
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
                navigation_timeout=timedelta(seconds=SCRAPE_TIMEOUT),
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

        while True:
            # 1. Reset global state at the start of each iteration to prevent accumulation and ServiceConflictError
            self.reset_crawlee_global_state()

            # 2. Fetch batch
            # Used small batch size (20) to ensure regular browser restarts and avoid memory leaks/hangs
            batch = self.fetch_batch(20)
            if not batch:
                self.logger.info("Queue empty, waiting...")
                await asyncio.sleep(60)
                continue

            self.logger.info(f"Fetched {len(batch)} URLs")

            # Force total isolation for this batch by using a fresh configuration and unique storage directory
            batch_storage_dir = tempfile.mkdtemp(prefix="crawlee_batch_storage_")
            batch_config = Configuration()
            batch_config.storage_dir = batch_storage_dir

            request_list = []
            for item in batch:
                # Mark as processing immediately
                self.update_queue_status_sync(item['queue_id'], 'processing')
                request_list.append(
                    Request.from_url(
                        item['url'],
                        user_data={
                            "queue_id": item['queue_id'],
                            "retry_count": item['retry_count'],
                            "uni_listing_id": item['uni_listing_id'],
                            "opco": item.get('opco'),
                            "depth": item['depth']
                        }
                    )
                )

            # Configure Crawler with isolation
            crawler = PlaywrightCrawler(
                configuration=batch_config,
                request_handler=self.request_handler,
                storage_client=MemoryStorageClient(),
                max_requests_per_crawl=25,
                headless=PLAYWRIGHT_HEADLESS,
                browser_type='chromium',
                request_handler_timeout=timedelta(seconds=SCRAPE_TIMEOUT),
                navigation_timeout=timedelta(seconds=SCRAPE_TIMEOUT),
                browser_launch_options={
                    "args": ["--no-sandbox", "--disable-dev-shm-usage"],
                    "handle_sigint": False,
                },
            )
            crawler.failed_request_handler = self.failed_request_handler

            # Run crawler on this batch
            try:
                self.logger.info(f"Starting batch execution (isolation dir: {batch_storage_dir})...")
                await crawler.run(request_list)
            except Exception as e:
                self.logger.error(f"Batch execution failed with error: {e}")
            finally:
                # 3. Aggressive cleanup after EVERY batch
                self.cleanup_temp_dirs()
                try:
                    if os.path.exists(batch_storage_dir):
                        shutil.rmtree(batch_storage_dir, ignore_errors=True)
                except Exception:
                    pass

                # Reconcile batch status (fix stuck items)
                batch_ids = [item['queue_id'] for item in batch]
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self.reconcile_batch_sync, batch_ids)

if __name__ == '__main__':
    scraper = Scraper()
    asyncio.run(scraper.run())
