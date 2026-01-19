from bs4 import BeautifulSoup
import json
import time
import re
from src.utils.db import get_db_connection, get_cursor
from src.utils.patterns import (
    extract_emails, extract_phones, extract_org_num, extract_social_media_from_soup
)
from src.utils.address import extract_addresses_from_text
from src.utils.logging_config import setup_logging
from src.utils.country import detect_country
from src.utils.multipage import find_promising_links
from config.settings import LOG_DIR

class Parser:
    def __init__(self):
        self.conn = get_db_connection()
        self.logger = setup_logging('parser', f'{LOG_DIR}/parser.log')

    def get_next_scrape_result(self):
        """Získá další scrape_result k parsování"""
        with get_cursor(self.conn) as cur:
            cur.execute("""
                SELECT r.id, r.html, r.detected_language, r.url, r.queue_id, q.depth
                FROM scr_scrape_results r
                LEFT JOIN scr_scrape_queue q ON r.queue_id = q.id
                WHERE r.processing_status = 'new'
                  AND r.html IS NOT NULL
                ORDER BY r.scraped_at ASC
                LIMIT 1
                FOR UPDATE OF r SKIP LOCKED
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
        # Don't remove nav/footer as they often contain contact info
        for elem in soup(['script', 'style']):
            elem.decompose()

        return soup.get_text(separator=' ', strip=True)

    def parse_html(self, html, language, url):
        """
        Parse HTML a extrahuje data
        Returns: dict s extracted data
        """
        soup = BeautifulSoup(html, 'lxml')
        
        # Social media extraction from soup (links)
        social_media = extract_social_media_from_soup(soup)
        
        text = self.extract_text_content(soup)
        
        # Detect country context
        country = detect_country(url, language)

        phones = extract_phones(text, country)
        org_num = extract_org_num(text, country)

        # Conflict resolution: Org Num wins over Phone
        if org_num and phones:
            clean_org = re.sub(r'[^0-9]', '', org_num)
            # Remove phone if it matches normalized org_num
            # Phones are already normalized by extract_phones (spaces removed)
            phones = [p for p in phones if re.sub(r'[^0-9]', '', p) != clean_org]

        data = {
            'url': url,
            'language': language,
            'country': country,
            'emails': extract_emails(text),
            'phones': phones,
            'org_num': org_num,
            'addresses': extract_addresses_from_text(text, language),
            'social_media': social_media,
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
        elif soup.title and soup.title.string:
            data['company_name'] = soup.title.string.strip()

        return data

    def calculate_quality_score(self, data, language):
        """Spočítá quality score"""
        score = 0

        if data.get('emails'): score += 20
        if data.get('phones'): score += 20
        if data.get('company_name'): score += 15
        if data.get('org_num'): score += 15
        if data.get('social_media'): score += 10
        if data.get('addresses'): score += 10 # Added score for addresses

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

    def add_subpages_to_queue(self, uni_listing_id, parent_scrape_id, depth, promising_links):
        """Add promising links to queue"""
        if not promising_links:
            return

        with get_cursor(self.conn, dict_cursor=False) as cur:
            for url, category in promising_links:
                cur.execute("""
                    INSERT INTO scr_scrape_queue
                    (url, uni_listing_id, parent_scrape_id, depth, priority)
                    VALUES (%s, %s, %s, %s, 5)
                    ON CONFLICT (url) DO NOTHING
                """, (url, uni_listing_id, parent_scrape_id, depth + 1))
            self.conn.commit()
        
        self.logger.info(f"  -> Added {len(promising_links)} sub-pages to queue")

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
        depth = item.get('depth') or 0 # Default to 0 if null

        self.logger.info(f"Parsing: {url} ({language})")

        try:
            # Parse
            data = self.parse_html(html, language, url)
            country = data.get('country')

            # Get uni_listing_id
            uni_listing_id = self.get_uni_listing_id(queue_id)

            # Save
            self.save_parsed_data(scrape_id, uni_listing_id, data, language)
            
            # Find and add subpages
            # Check max depth first? Assume max depth is handled by scraper usually, 
            # but if we add here, we should probably check.
            # For now, let's just add if depth < 2 (hardcoded limit for now, or fetch from DB rules)
            if depth < 2:
                promising = find_promising_links(html, url, language, country)
                if promising:
                    # Need parent_scrape_id -> scrape_id (this result is the parent of the new subpage)
                    # Actually scrape_queue.parent_scrape_id refers to scrape_results.id of parent?
                    # Schema says: parent_scrape_id INTEGER. Probably yes.
                    self.add_subpages_to_queue(uni_listing_id, scrape_id, depth, promising)

        except Exception as e:
            self.logger.error(f"Error parsing {url}: {e}", exc_info=True)
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
                self.logger.info("Nothing to parse, exiting.")
                break

            processed += 1

        self.conn.close()

if __name__ == '__main__':
    parser = Parser()
    parser.run()
