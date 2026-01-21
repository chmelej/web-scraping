from datetime import datetime, timedelta
from src.utils.db import get_db_connection, get_cursor
from src.utils.logging_config import setup_logging
from config.settings import LOG_DIR, REQUEUE_INTERVAL_DAYS
import time

class RequeueWorker:
    def __init__(self):
        self.conn = get_db_connection()
        self.logger = setup_logging('requeue', f'{LOG_DIR}/requeue.log')

    def requeue_old_listings(self, days_old=90):
        """
        Najde listings starší než X dní a přidá je zpět do fronty
        """
        with get_cursor(self.conn, dict_cursor=False) as cur:
            # Get listings to requeue
            cur.execute("""
                SELECT DISTINCT pd.uni_listing_id, sr.url
                FROM scr_parsed_data pd
                JOIN scr_scrape_results sr ON sr.id = pd.scrape_result_id
                WHERE pd.quality_score > 50
                  AND pd.extracted_at < NOW() - INTERVAL '%s days'
                  AND sr.url NOT IN (
                      SELECT url FROM scr_domain_blacklist
                      WHERE auto_added = TRUE
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM scr_scrape_queue sq
                      WHERE sq.url = sr.url
                        AND sq.status IN ('pending', 'processing')
                  )
            """, (days_old,))

            results = cur.fetchall()

            # Re-add to queue
            count = 0
            for uni_listing_id, url in results:
                next_scrape = datetime.now() + timedelta(days=days_old)

                cur.execute("""
                    INSERT INTO scr_scrape_queue
                    (url, uni_listing_id, next_scrape_at, priority)
                    VALUES (%s, %s, %s, 1)
                    ON CONFLICT (url, uni_listing_id) DO UPDATE
                    SET next_scrape_at = EXCLUDED.next_scrape_at,
                        status = 'pending'
                """, (url, uni_listing_id, next_scrape))

                count += 1

            self.conn.commit()
            if count > 0:
                self.logger.info(f"Re-queued {count} listings")
            return count

    def run_daily(self):
        """Denní běh"""
        self.logger.info(f"Running requeue worker at {datetime.now()}")
        try:
            days = int(REQUEUE_INTERVAL_DAYS)
            self.requeue_old_listings(days_old=days)
        except Exception as e:
            self.logger.error(f"Error in requeue worker: {e}")

if __name__ == '__main__':
    worker = RequeueWorker()
    worker.logger.info("Requeue worker started")

    while True:
        worker.run_daily()
        # Sleep 24 hodin
        time.sleep(86400)
