import time
import socket
import json
from playwright.sync_api import sync_playwright
from src.utils.db import get_db_connection, get_cursor
from src.utils.language import detect_language
from src.utils.urls import extract_domain
from src.utils.logging_config import setup_logging
from src.utils.multipage import find_promising_links
from config.settings import SCRAPE_DELAY, USER_AGENT, MAX_RETRIES, PLAYWRIGHT_HEADLESS, LOG_DIR

class Scraper:
    def __init__(self):
        self.conn = get_db_connection()
        self.last_domain_access = {}
        self.logger = setup_logging('scraper', f'{LOG_DIR}/scraper.log')
        self.browser = None

    def get_next_url(self):
        """Získá další URL z fronty"""
        with get_cursor(self.conn) as cur:
            cur.execute("""
                SELECT id, url, unit_listing_id, retry_count, depth
                FROM scrape_queue
                WHERE status = 'pending'
                  AND next_scrape_at <= NOW()
                  AND url NOT LIKE ANY(
                      SELECT '%' || domain || '%' FROM domain_blacklist
                  )
                ORDER BY priority DESC, added_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            """)
            return cur.fetchone()

    def respect_rate_limit(self, domain):
        """Enforce delay between requests na stejnou doménu"""
        if domain in self.last_domain_access:
            elapsed = time.time() - self.last_domain_access[domain]
            if elapsed < SCRAPE_DELAY:
                time.sleep(SCRAPE_DELAY - elapsed)

        self.last_domain_access[domain] = time.time()

    def scrape_url(self, url):
        """
        Stáhne HTML z URL
        Returns: dict s html, status_code, headers, ip, redirects
        """
        domain = extract_domain(url)
        self.respect_rate_limit(domain)

        result = {
            'html': None,
            'status_code': None,
            'headers': {},
            'ip_address': None,
            'redirected_from': None,
            'error': None
        }

        try:
            # Resolve IP
            try:
                result['ip_address'] = socket.gethostbyname(domain)
            except:
                pass # DNS fail handled by playwright or not critical

            # Use existing browser instance
            if not self.browser:
                 raise Exception("Browser not initialized")

            context = self.browser.new_context(user_agent=USER_AGENT)
            page = context.new_page()

            try:
                response = page.goto(url, wait_until='networkidle', timeout=30000)

                result['status_code'] = response.status
                result['headers'] = dict(response.headers)

                # Check redirects
                if response.url != url:
                    result['redirected_from'] = url

                if response.status == 200:
                    result['html'] = page.content()
            except Exception as e:
                result['error'] = str(e)
            finally:
                page.close()
                context.close()

        except Exception as e:
            result['error'] = str(e)

        return result

    def save_result(self, queue_id, url, scrape_result):
        """Uloží výsledek scrape"""
        with get_cursor(self.conn, dict_cursor=False) as cur:
            # Detekce jazyka
            lang, lang_conf = 'unknown', 0.0
            if scrape_result['html']:
                lang, lang_conf = detect_language(scrape_result['html'])

            cur.execute("""
                INSERT INTO scrape_results
                (queue_id, url, html, status_code, headers, ip_address,
                 redirected_from, detected_language, language_confidence, error_message)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                queue_id, url, scrape_result['html'], scrape_result['status_code'],
                json.dumps(scrape_result.get('headers')) if scrape_result.get('headers') else None,
                scrape_result.get('ip_address'),
                scrape_result.get('redirected_from'), lang, lang_conf,
                scrape_result.get('error')
            ))

            result_id = cur.fetchone()[0]
            self.conn.commit()
            return result_id

    def update_queue_status(self, queue_id, status, retry_count=None, next_scrape_at=None):
        """Update stav fronty"""
        with get_cursor(self.conn, dict_cursor=False) as cur:
            if retry_count is not None:
                cur.execute("""
                    UPDATE scrape_queue
                    SET status = %s, retry_count = %s, next_scrape_at = %s
                    WHERE id = %s
                """, (status, retry_count, next_scrape_at, queue_id))
            else:
                cur.execute("""
                    UPDATE scrape_queue SET status = %s WHERE id = %s
                """, (status, queue_id))

            self.conn.commit()

    def add_subpages_to_queue(self, parent_id, parent_url, html, language, unit_listing_id, depth):
        """Přidá sub-stránky do fronty"""
        max_depth = self.get_max_depth(parent_url)

        if depth >= max_depth:
            return

        promising = find_promising_links(html, parent_url, language)

        with get_cursor(self.conn, dict_cursor=False) as cur:
            for url, category in promising:
                cur.execute("""
                    INSERT INTO scrape_queue
                    (url, unit_listing_id, parent_scrape_id, depth, priority)
                    VALUES (%s, %s, %s, %s, 5)
                    ON CONFLICT (url, unit_listing_id) DO NOTHING
                """, (url, unit_listing_id, parent_id, depth + 1))

            self.conn.commit()

        if promising:
            self.logger.info(f"  -> Added {len(promising)} sub-pages to queue")

    def get_max_depth(self, url):
        """Získá max_depth pro doménu"""
        domain = extract_domain(url)

        with get_cursor(self.conn) as cur:
            cur.execute("""
                SELECT max_depth FROM domain_multipage_rules
                WHERE domain = %s AND enabled = TRUE
            """, (domain,))

            row = cur.fetchone()
            return row['max_depth'] if row else 2 # default

    def process_one(self):
        """Zpracuje jedno URL"""
        item = self.get_next_url()
        if not item:
            return False

        queue_id = item['id']
        url = item['url']
        retry_count = item['retry_count']
        unit_listing_id = item.get('unit_listing_id')
        depth = item.get('depth', 0)

        self.logger.info(f"Scraping [{depth}]: {url}")

        # Mark as processing
        self.update_queue_status(queue_id, 'processing')

        # Scrape
        result = self.scrape_url(url)

        # Save
        scrape_result_id = self.save_result(queue_id, url, result)

        # Update queue
        if result['status_code'] == 200 and result['html']:
            self.update_queue_status(queue_id, 'completed')

            # Detect language
            lang, _ = detect_language(result['html'])

            # Add sub-pages
            if unit_listing_id:
                self.add_subpages_to_queue(
                    scrape_result_id, url, result['html'],
                    lang, unit_listing_id, depth
                )

        elif retry_count >= MAX_RETRIES:
            self.update_queue_status(queue_id, 'failed')
        else:
            # Retry za hodinu
            import datetime
            next_try = datetime.datetime.now() + datetime.timedelta(hours=1)
            self.update_queue_status(queue_id, 'pending', retry_count + 1, next_try)

        return True

    def run(self, max_items=None):
        """Main loop"""
        processed = 0
        self.logger.info("Scraper worker started")

        with sync_playwright() as p:
            self.browser = p.chromium.launch(headless=PLAYWRIGHT_HEADLESS)
            self.logger.info("Browser launched")

            try:
                while True:
                    if max_items and processed >= max_items:
                        break

                    try:
                        if not self.process_one():
                            self.logger.info("Queue empty, waiting...")
                            time.sleep(60)
                            continue
                        processed += 1
                    except Exception as e:
                        self.logger.error(f"Error in main loop: {e}")
                        time.sleep(10)
            finally:
                if self.browser:
                    self.browser.close()
                    self.logger.info("Browser closed")

        self.conn.close()

if __name__ == '__main__':
    scraper = Scraper()
    scraper.run()
