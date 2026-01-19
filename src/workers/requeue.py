from datetime import datetime, timedelta
import time
from src.utils.db import get_db_connection, get_cursor
from src.utils.logging_config import setup_logging
import os

class RequeueWorker:
    def __init__(self):
        self.logger = setup_logging('requeue', 'requeue.log')
        try:
            self.conn = get_db_connection()
        except:
            self.conn = None
            self.logger.error("RequeueWorker failed to connect to DB")

    def requeue_old_listings(self, days_old=90):
        """
        Najde listings starší než X dní a přidá je zpět do fronty
        """
        if not self.conn:
            return 0

        try:
            with get_cursor(self.conn, dict_cursor=False) as cur:
                # Get listings to requeue
                # Join with scrape_results to get URL
                cur.execute("""
                    SELECT DISTINCT pd.unit_listing_id, sr.url
                    FROM parsed_data pd
                    JOIN scrape_results sr ON sr.id = pd.scrape_result_id
                    WHERE pd.quality_score > 50
                      AND pd.extracted_at < NOW() - INTERVAL '%s days'
                      AND sr.url NOT IN (
                          SELECT domain FROM domain_blacklist
                          WHERE auto_added = TRUE
                      )
                      AND NOT EXISTS (
                          SELECT 1 FROM scrape_queue sq
                          WHERE sq.url = sr.url
                            AND sq.status IN ('pending', 'processing')
                      )
                """, (days_old,))

                results = cur.fetchall()

                # Re-add to queue
                count = 0
                for unit_listing_id, url in results:
                    next_scrape = datetime.now() + timedelta(days=days_old)

                    cur.execute("""
                        INSERT INTO scrape_queue
                        (url, unit_listing_id, next_scrape_at, priority)
                        VALUES (%s, %s, %s, 1)
                        ON CONFLICT (url, unit_listing_id) DO UPDATE
                        SET next_scrape_at = EXCLUDED.next_scrape_at,
                            status = 'pending'
                    """, (url, unit_listing_id, next_scrape))

                    count += 1

                self.conn.commit()
                self.logger.info(f"Re-queued {count} listings")
                return count
        except Exception as e:
            self.logger.error(f"Error requeuing: {e}")
            self.conn.rollback()
            return 0

    def run_daily(self):
        """Denní běh"""
        self.logger.info(f"Running requeue worker at {datetime.now()}")
        days = int(os.getenv('REQUEUE_INTERVAL_DAYS', 90))
        self.requeue_old_listings(days_old=days)

if __name__ == '__main__':
    worker = RequeueWorker()

    while True:
        worker.run_daily()
        # Sleep 24 hodin
        time.sleep(86400)
