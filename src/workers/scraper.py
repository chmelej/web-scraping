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
import http.client
from datetime import datetime, timedelta
from crawlee import Request
from crawlee.crawlers import PlaywrightCrawler
from crawlee import Request
from crawlee.storage_clients import MemoryStorageClient
from crawlee.configuration import Configuration
from src.utils.db import get_db_connection, get_cursor
from src.utils.language import detect_language
from src.utils.urls import extract_domain, normalize_url
from src.utils.logging_config import setup_logging
from src.utils.multipage import find_promising_links
from src.utils.storage import save_raw_html
from config.settings import SCRAPE_DELAY, USER_AGENT, MAX_RETRIES, PLAYWRIGHT_HEADLESS, LOG_DIR, SCRAPE_TIMEOUT, REQUEUE_INTERVAL_DAYS, SCRAPER_MAX_RUNTIME_SECONDS

class Scraper:
    def __init__(self):
        self.conn = get_db_connection()
        self.logger = setup_logging('scraper', f'{LOG_DIR}/scraper.log')
        self._current_crawler = None
        # Suppress verbose Crawlee errors (stack traces for 404s/DNS)
        # logging.getLogger('crawlee.crawlers._playwright._playwright_crawler').setLevel(logging.CRITICAL)

    def create_request_for_item(self, item):
        """Build a Crawlee Request for a queue item, proactively upgrading http:// to https://"""
        raw_url = item['url']
        target_url = raw_url
        is_https_upgrade = False

        if raw_url.startswith("http://"):
            target_url = "https://" + raw_url[7:]
            is_https_upgrade = True

        return Request.from_url(
            target_url,
            user_data={
                "queue_id": item['queue_id'],
                "retry_count": item['retry_count'],
                "uni_listing_id": item['uni_listing_id'],
                "opco": item.get('opco'),
                "depth": item['depth'],
                "priority": item.get('priority', 0),
                "original_url": raw_url,
                "is_https_upgrade_attempt": is_https_upgrade
            }
        )

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
        conn = get_db_connection()
        try:
            with get_cursor(conn, dict_cursor=False) as cur:
                if retry_count is not None and next_scrape_at is not None:
                    cur.execute("""
                        UPDATE scr_scrape_queue
                        SET status = %s, retry_count = %s, next_scrape_at = %s,
                            last_scrape_at = CASE WHEN %s IN ('completed', 'failed') THEN NOW() ELSE last_scrape_at END
                        WHERE queue_id = %s
                    """, (status, retry_count, next_scrape_at, status, queue_id))
                else:
                    cur.execute("""
                        UPDATE scr_scrape_queue
                        SET status = %s,
                            last_scrape_at = CASE WHEN %s IN ('completed', 'failed') THEN NOW() ELSE last_scrape_at END
                        WHERE queue_id = %s
                    """, (status, status, queue_id))
                conn.commit()
        finally:
            conn.close()

    def handle_redirect_sync(self, queue_id, original_url, final_url, uni_listing_id, opco, depth, priority=0):
        """Mark original URL as 'redirected' and insert final_url as a new queue item"""
        conn = get_db_connection()
        try:
            with get_cursor(conn, dict_cursor=False) as cur:
                # 1. Mark original item as 'redirected'
                cur.execute("""
                    UPDATE scr_scrape_queue
                    SET status = 'redirected'
                    WHERE queue_id = %s
                """, (queue_id,))

                # 2. Insert final_url into queue as new item (or return existing if present)
                norm_final_url = normalize_url(final_url)
                cur.execute("""
                    INSERT INTO scr_scrape_queue
                    (url, normalized_url, uni_listing_id, opco, depth, priority, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'pending')
                    ON CONFLICT (url) DO UPDATE
                    SET uni_listing_id = COALESCE(scr_scrape_queue.uni_listing_id, EXCLUDED.uni_listing_id),
                        opco = COALESCE(scr_scrape_queue.opco, EXCLUDED.opco),
                        normalized_url = COALESCE(scr_scrape_queue.normalized_url, EXCLUDED.normalized_url)
                    RETURNING queue_id
                """, (final_url, norm_final_url, uni_listing_id, opco, depth, priority))
                new_queue_id = cur.fetchone()[0]
                conn.commit()
                self.logger.info(f"Redirect handled: {original_url} (queue_id {queue_id} -> redirected) -> {final_url} (queue_id {new_queue_id})")
                return new_queue_id
        except Exception as e:
            self.logger.error(f"Error handling redirect {original_url} -> {final_url}: {e}")
            conn.rollback()
            return queue_id
        finally:
            conn.close()

    def add_domain_to_blacklist_sync(self, domain, reason="no_dns"):
        conn = get_db_connection()
        try:
            with get_cursor(conn, dict_cursor=False) as cur:
                cur.execute("""
                    INSERT INTO scr_domain_blacklist (domain, reason, fail_count, first_failed_at, last_failed_at, auto_added)
                    VALUES (%s, %s, 1, NOW(), NOW(), TRUE)
                    ON CONFLICT (domain) DO UPDATE
                    SET fail_count = scr_domain_blacklist.fail_count + 1,
                        last_failed_at = NOW()
                """, (domain, reason))
                conn.commit()
                self.logger.info(f"Blacklisted domain {domain} (reason: {reason})")
        except Exception as e:
            self.logger.warning(f"Failed to blacklist domain {domain}: {e}")
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
                    (queue_id, url, html, html_path, html_size, status_code, headers, ip_address,
                     redirected_from, detected_language, language_confidence, error_message)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING result_id
                """, (
                    queue_id, url, None, None, 0, scrape_result.get('status_code'),
                    json.dumps(scrape_result.get('headers')) if scrape_result.get('headers') else None,
                    scrape_result.get('ip_address'),
                    scrape_result.get('redirected_from'), lang, lang_conf,
                    scrape_result.get('error')
                ))
                result_id = cur.fetchone()[0]

                if scrape_result.get('html'):
                    html_path, html_size = save_raw_html(url, scrape_result['html'], result_id=result_id)
                    cur.execute("""
                        UPDATE scr_scrape_results
                        SET html_path = %s, html_size = %s
                        WHERE result_id = %s
                    """, (html_path, html_size, result_id))

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
                     norm_url = normalize_url(url)
                     cur.execute("""
                        INSERT INTO scr_scrape_queue
                        (url, normalized_url, uni_listing_id, parent_scrape_id, depth, priority)
                        VALUES (%s, %s, %s, %s, %s, 5)
                        ON CONFLICT (url) DO UPDATE
                        SET normalized_url = COALESCE(scr_scrape_queue.normalized_url, EXCLUDED.normalized_url)
                     """, (url, norm_url, uni_listing_id, parent_id, depth + 1))
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
            
            # Check for redirect (client-side or server-side) or HTTPS upgrade
            final_url = page.url
            original_url = request.user_data.get('original_url', request.url)
            is_https_upgrade = request.user_data.get('is_https_upgrade_attempt', False)

            target_url = request.url
            target_queue_id = queue_id

            if is_https_upgrade or (final_url and final_url != original_url):
                 effective_final_url = final_url if final_url else request.url
                 self.logger.info(f"Redirect / HTTPS upgrade: {original_url} -> {effective_final_url}")
                 result['redirected_from'] = original_url
                 target_url = effective_final_url
                 opco = request.user_data.get('opco')
                 priority = request.user_data.get('priority', 0)
                 loop = asyncio.get_running_loop()
                 target_queue_id = await loop.run_in_executor(
                     None, self.handle_redirect_sync, queue_id, original_url, effective_final_url, uni_listing_id, opco, depth, priority
                 )
            
            # Extract more info from the page/response
            if hasattr(context, 'response') and context.response:
                result['status_code'] = context.response.status
                result['headers'] = context.response.headers
                server_addr = await context.response.server_addr()
                if server_addr:
                    result['ip_address'] = server_addr.get('ipAddress')

            if not result['status_code']:
                result['status_code'] = 200

            if result['status_code'] != 200 and not result.get('error'):
                reason = http.client.responses.get(result['status_code'], 'HTTP Error')
                result['error'] = f"status code: {result['status_code']} ({reason})"

            self.logger.debug(f"Got content for {target_url}, saving result...")

            # Save result with final target_url and target_queue_id
            loop = asyncio.get_running_loop()
            result_id = await loop.run_in_executor(None, self.save_result_sync, target_queue_id, target_url, result)

            # Update status for target_queue_id
            next_scrape = datetime.now() + timedelta(days=REQUEUE_INTERVAL_DAYS)
            await loop.run_in_executor(None, self.update_queue_status_sync, target_queue_id, 'completed', None, next_scrape)

            # Subpages
            if uni_listing_id:
                self.logger.debug(f"Checking for subpages on {target_url}")
                lang, _ = detect_language(content)
                await loop.run_in_executor(None, self.add_subpages_sync, result_id, target_url, content, lang, uni_listing_id, depth)
            
            self.logger.info(f"Finished processing {target_url}")

        except Exception as e:
            self.logger.warning(f"Error scraping {request.url}: {e}")
            raise e

    async def failed_request_handler(self, context, error):
        """Handle failed requests"""
        request = context.request
        
        queue_id = request.user_data['queue_id']
        retry_count = request.user_data['retry_count']
        err_str = str(error)
        
        # Simple one-line warning
        self.logger.warning(f"Page unavailable: {request.url} ({err_str})")

        # Fallback to HTTP if proactive HTTPS upgrade failed
        is_https_upgrade = request.user_data.get('is_https_upgrade_attempt', False)
        original_url = request.user_data.get('original_url', request.url)

        if is_https_upgrade and original_url != request.url:
            self.logger.info(f"HTTPS upgrade attempt failed for {request.url} ({err_str}), falling back to HTTP: {original_url}")
            fallback_request = Request.from_url(
                original_url,
                user_data={
                    "queue_id": queue_id,
                    "retry_count": retry_count,
                    "uni_listing_id": request.user_data.get('uni_listing_id'),
                    "opco": request.user_data.get('opco'),
                    "depth": request.user_data.get('depth', 0),
                    "priority": request.user_data.get('priority', 0),
                    "original_url": original_url,
                    "is_https_upgrade_attempt": False
                }
            )
            if self._current_crawler:
                await self._current_crawler.add_requests([fallback_request])
                return
        
        result = {
            'html': None,
            'status_code': 0,
            'headers': {},
            'ip_address': None,
            'redirected_from': None,
            'error': err_str
        }

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.save_result_sync, queue_id, request.url, result)

        is_hard_failure = ("ERR_NAME_NOT_RESOLVED" in err_str or 
                           "could not translate host name" in err_str or 
                           "status code: 404" in err_str or 
                           "status code: 410" in err_str)

        if is_hard_failure:
            if "ERR_NAME_NOT_RESOLVED" in err_str or "could not translate host name" in err_str:
                from urllib.parse import urlparse
                domain = urlparse(request.url).netloc
                if domain:
                    await loop.run_in_executor(None, self.add_domain_to_blacklist_sync, domain, "no_dns")
            await loop.run_in_executor(None, self.update_queue_status_sync, queue_id, 'failed')
        elif retry_count >= MAX_RETRIES:
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

        request_list = [self.create_request_for_item(item)]

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
            self._current_crawler = crawler
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
        start_time = time.time()

        while True:
            # Check elapsed time
            elapsed = time.time() - start_time
            if elapsed >= SCRAPER_MAX_RUNTIME_SECONDS:
                self.logger.info(f"Max runtime reached ({elapsed:.0f}s >= {SCRAPER_MAX_RUNTIME_SECONDS}s). Exiting cleanly.")
                break

            # 1. Reset global state at the start of each iteration to prevent accumulation and ServiceConflictError
            self.reset_crawlee_global_state()

            # 2. Fetch batch
            # Used small batch size (20) to ensure regular browser restarts and avoid memory leaks/hangs
            batch = self.fetch_batch(20)
            if not batch:
                self.logger.info("Queue empty, exiting.")
                sys.exit(10)

            self.logger.info(f"Fetched {len(batch)} URLs")

            # Force total isolation for this batch by using a fresh configuration and unique storage directory
            batch_storage_dir = tempfile.mkdtemp(prefix="crawlee_batch_storage_")
            batch_config = Configuration()
            batch_config.storage_dir = batch_storage_dir

            request_list = []
            for item in batch:
                # Mark as processing immediately
                self.update_queue_status_sync(item['queue_id'], 'processing')
                request_list.append(self.create_request_for_item(item))

            # Configure Crawler with isolation
            crawler = PlaywrightCrawler(
                configuration=batch_config,
                request_handler=self.request_handler,
                storage_client=MemoryStorageClient(),
                max_requests_per_crawl=25,
                max_request_retries=1,
                headless=PLAYWRIGHT_HEADLESS,
                request_handler_timeout=timedelta(seconds=SCRAPE_TIMEOUT),
                navigation_timeout=timedelta(seconds=SCRAPE_TIMEOUT),
                browser_launch_options={"args": ["--no-sandbox"]},
            )
            crawler.failed_request_handler = self.failed_request_handler
            self._current_crawler = crawler

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
