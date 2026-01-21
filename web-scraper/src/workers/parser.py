from bs4 import BeautifulSoup
import json
import time
from src.utils.db import get_db_connection, get_cursor
from src.utils.patterns import (
    extract_emails, extract_phones, extract_ico, extract_social_media
)
from src.utils.logging_config import setup_logging
from config.settings import LOG_DIR

class Parser:
    def __init__(self):
        self.conn = get_db_connection()
        self.logger = setup_logging('parser', f'{LOG_DIR}/parser.log')

    def get_next_scrape_result(self):
        """Získá další scrape_result k parsování"""
        with get_cursor(self.conn) as cur:
            cur.execute("""
                SELECT id, html, detected_language, url, queue_id
                FROM scr_scrape_results
                WHERE processing_status = 'new'
                  AND html IS NOT NULL
                ORDER BY scraped_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            """)
            return cur.fetchone()

    def extract_structured_data(self, soup):
        """Extract JSON-LD, microdata, OpenGraph"""
        data = {}

        # JSON-LD
        json_ld = soup.find('script', type='application/ld+json')
        if json_ld and json_ld.string:
            try:
                data['json_ld'] = json.loads(json_ld.string)
            except:
                pass

        # OpenGraph
        og_tags = soup.find_all('meta', property=lambda x: x and x.startswith('og:'))
        if og_tags:
            data['opengraph'] = {
                tag.get('property')[3:]: tag.get('content')
                for tag in og_tags
            }

        return data

    def extract_text_content(self, soup):
        """Extract plain text z HTML"""
        # Remove script, style
        for elem in soup(['script', 'style', 'nav', 'footer']):
            elem.decompose()

        return soup.get_text(separator=' ', strip=True)

    def parse_html(self, html, language, url):
        """
        Parse HTML a extrahuje data
        Returns: dict s extracted data
        """
        soup = BeautifulSoup(html, 'lxml')
        text = self.extract_text_content(soup)

        data = {
            'url': url,
            'language': language,
            'emails': extract_emails(text),
            'phones': extract_phones(text, language),
            'ico': extract_ico(text, language),
            'social_media': extract_social_media(text),
        }

        # Structured data
        structured = self.extract_structured_data(soup)
        if structured:
            data['structured'] = structured

        # Company name attempts
        # 1. JSON-LD
        if 'json_ld' in structured and isinstance(structured['json_ld'], dict):
             if structured['json_ld'].get('name'):
                data['company_name'] = structured['json_ld']['name']
        # 2. OpenGraph
        elif 'opengraph' in structured and structured['opengraph'].get('site_name'):
            data['company_name'] = structured['opengraph']['site_name']
        # 3. Title tag
        elif soup.title:
            data['company_name'] = soup.title.string.strip()

        return data

    def calculate_quality_score(self, data, language):
        """Spočítá quality score"""
        score = 0

        if data.get('emails'): score += 20
        if data.get('phones'): score += 20
        if data.get('company_name'): score += 15
        if data.get('ico'): score += 15
        if data.get('social_media'): score += 10

        # Bonus za structured data
        if data.get('structured'): score += 10

        return min(score, 100)

    def save_parsed_data(self, scrape_result_id, uni_listing_id, data, language):
        """Uloží parsed data"""
        quality_score = self.calculate_quality_score(data, language)

        with get_cursor(self.conn, dict_cursor=False) as cur:
            cur.execute("""
                INSERT INTO scr_parsed_data
                (scrape_result_id, uni_listing_id, content_language, data, quality_score)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (
                scrape_result_id, uni_listing_id, language,
                json.dumps(data), quality_score
            ))

            parsed_id = cur.fetchone()[0]

            # Mark scrape_result as processed
            cur.execute("""
                UPDATE scr_scrape_results
                SET processing_status = 'processed'
                WHERE id = %s
            """, (scrape_result_id,))

            self.conn.commit()
            return parsed_id

    def get_uni_listing_id(self, queue_id):
        # Helper to get uni_listing_id from queue
        with get_cursor(self.conn) as cur:
             cur.execute("SELECT uni_listing_id FROM scr_scrape_queue WHERE id = %s", (queue_id,))
             res = cur.fetchone()
             return res['uni_listing_id'] if res else None

    def process_one(self):
        """Zpracuje jeden scrape result"""
        item = self.get_next_scrape_result()
        if not item:
            return False

        scrape_id = item['id']
        html = item['html']
        language = item['detected_language']
        url = item['url']
        queue_id = item['queue_id']

        self.logger.info(f"Parsing: {url} ({language})")

        try:
            # Parse
            data = self.parse_html(html, language, url)

            # Get uni_listing_id
            uni_listing_id = self.get_uni_listing_id(queue_id)

            # Save
            self.save_parsed_data(scrape_id, uni_listing_id, data, language)
        except Exception as e:
            self.logger.error(f"Error parsing {url}: {e}")
            # Mark as failed or skip?
            with get_cursor(self.conn, dict_cursor=False) as cur:
                 cur.execute("UPDATE scr_scrape_results SET processing_status = 'failed', error_message = %s WHERE id = %s", (str(e), scrape_id))
                 self.conn.commit()

        return True

    def run(self, max_items=None):
        """Main loop"""
        processed = 0
        self.logger.info("Parser worker started")

        while True:
            if max_items and processed >= max_items:
                break

            if not self.process_one():
                self.logger.info("Nothing to parse, waiting...")
                time.sleep(30)
                continue

            processed += 1

        self.conn.close()

if __name__ == '__main__':
    parser = Parser()
    parser.run()
