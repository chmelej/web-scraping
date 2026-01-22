from bs4 import BeautifulSoup
import json
import time
from src.utils.db import get_db_connection, get_cursor
from src.utils.patterns import (
    extract_emails, extract_phones, extract_ico, extract_social_media
)
from src.utils.logging_config import setup_logging
from src.llm.prompts import PromptManager
from src.llm.client import call_llm
from src.utils.bloom import BloomFilterManager

class Parser:
    def __init__(self):
        self.logger = setup_logging('parser', 'parser.log')
        try:
            self.conn = get_db_connection()
        except:
            self.conn = None
            self.logger.error("Parser failed to connect to DB")

        self.prompt_manager = PromptManager()
        self.bloom_manager = BloomFilterManager()

    def get_next_scrape_result(self):
        """Získá další scrape_result k parsování"""
        if not self.conn:
            return None

        try:
            with get_cursor(self.conn) as cur:
                # JOIN scrape_queue to get unit_listing_id
                # Locking only scrape_results row
                cur.execute("""
                    SELECT sr.id, sr.html, sr.detected_language, sr.url, sq.unit_listing_id
                    FROM scrape_results sr
                    JOIN scrape_queue sq ON sq.id = sr.queue_id
                    WHERE sr.processing_status = 'new'
                      AND sr.html IS NOT NULL
                    ORDER BY sr.scraped_at ASC
                    LIMIT 1
                    FOR UPDATE OF sr SKIP LOCKED
                """)
                return cur.fetchone()
        except Exception as e:
            self.logger.error(f"Error getting next result: {e}")
            return None

    def extract_structured_data(self, soup):
        """Extract JSON-LD, microdata, OpenGraph"""
        data = {}

        # JSON-LD
        json_ld = soup.find('script', type='application/ld+json')
        if json_ld:
            try:
                content = json_ld.string
                if content:
                    data['json_ld'] = json.loads(content)
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

        # Bloom filter updates (new emails/phones)
        for email in data['emails']:
            self.bloom_manager.add('emails', email)
        for phone in data['phones']:
            self.bloom_manager.add('phones', phone)
        if data['ico']:
            self.bloom_manager.add('ico', data['ico'])

        # Structured data
        structured = self.extract_structured_data(soup)
        if structured:
            data['structured'] = structured

        # Company name attempts
        if 'json_ld' in structured and isinstance(structured['json_ld'], dict):
             if structured['json_ld'].get('name'):
                 data['company_name'] = structured['json_ld']['name']
        elif 'opengraph' in structured and structured['opengraph'].get('site_name'):
            data['company_name'] = structured['opengraph']['site_name']
        elif soup.title:
            data['company_name'] = soup.title.string.strip()

        # LLM Extraction for Opening Hours (if regex failed or just always try for better structure)
        # Using LLM when keywords found but no structured data
        if 'opening_hours' not in data: # simplified check
             keywords = ['otevírací doba', 'opening hours', 'öffnungszeiten']
             if any(k in text.lower() for k in keywords):
                 try:
                     # Cut text to relevant part or use full text (truncated)
                     # For simplicity, taking first 2000 chars of text or logic to find relevant section
                     # Using full text truncated to 2000 chars
                     relevant_text = text[:3000]

                     config = self.prompt_manager.render('opening_hours', language, text=relevant_text)

                     response = call_llm(
                         model=config['model'],
                         prompt=config['prompt'],
                         system=config['system'],
                         max_tokens=config['max_tokens'],
                         temperature=config['temperature']
                     )

                     try:
                        oh_data = json.loads(response)
                        data['opening_hours'] = oh_data

                        self.prompt_manager.log_execution(
                            config.get('prompt_id'),
                            success=True,
                            tokens=len(response.split())
                        )
                     except:
                         self.logger.warning("LLM returned invalid JSON")
                         self.prompt_manager.log_execution(config.get('prompt_id'), success=False)

                 except Exception as e:
                     self.logger.warning(f"LLM extraction failed: {e}")

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

    def save_parsed_data(self, scrape_result_id, unit_listing_id, data, language):
        """Uloží parsed data"""
        if not self.conn:
            return None

        quality_score = self.calculate_quality_score(data, language)

        try:
            with get_cursor(self.conn, dict_cursor=False) as cur:
                cur.execute("""
                    INSERT INTO parsed_data
                    (scrape_result_id, unit_listing_id, content_language, data, quality_score, change_checked)
                    VALUES (%s, %s, %s, %s, %s, FALSE)
                    RETURNING id
                """, (
                    scrape_result_id, unit_listing_id, language,
                    json.dumps(data), quality_score
                ))

                parsed_id = cur.fetchone()[0]

                # Mark scrape_result as processed
                cur.execute("""
                    UPDATE scrape_results
                    SET processing_status = 'processed'
                    WHERE id = %s
                """, (scrape_result_id,))

                self.conn.commit()
                return parsed_id
        except Exception as e:
            self.logger.error(f"Error saving parsed data: {e}")
            self.conn.rollback()
            return None

    def process_one(self):
        """Zpracuje jeden scrape result"""
        item = self.get_next_scrape_result()
        if not item:
            return False

        scrape_id = item['id']
        html = item['html']
        language = item['detected_language']
        url = item['url']
        unit_listing_id = item['unit_listing_id']

        self.logger.info(f"Parsing: {url} ({language})")

        # Parse
        data = self.parse_html(html, language, url)

        # Save
        self.save_parsed_data(scrape_id, unit_listing_id, data, language)

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

        if self.conn:
            self.conn.close()

if __name__ == '__main__':
    try:
        parser = Parser()
        parser.run()
    except KeyboardInterrupt:
        print("Stopping parser...")
