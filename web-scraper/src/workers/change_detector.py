import json
import time
from src.utils.db import get_db_connection, get_cursor
from src.utils.logging_config import setup_logging
from config.settings import LOG_DIR, WEBHOOK_URL
import os
import requests
from datetime import datetime

class ChangeDetector:
    def __init__(self):
        self.conn = get_db_connection()
        self.logger = setup_logging('change_detector', f'{LOG_DIR}/change_detector.log')

    def get_latest_data(self, uni_listing_id):
        """Získá 2 nejnovější parsovaná data pro listing"""
        with get_cursor(self.conn) as cur:
            cur.execute("""
                SELECT id, data, extracted_at
                FROM scr_parsed_data
                WHERE uni_listing_id = %s
                ORDER BY extracted_at DESC
                LIMIT 2
            """)
            return cur.fetchall()

    def detect_changes(self, old_data, new_data):
        """
        Porovná 2 JSON objekty a vrátí změny
        Returns: list of (field_name, old_value, new_value)
        """
        changes = []

        # Fields to track
        tracked_fields = [
            'company_name', 'emails', 'phones', 'org_num',
            'addresses', 'opening_hours', 'social_media'
        ]

        for field in tracked_fields:
            old_val = old_data.get(field)
            new_val = new_data.get(field)

            # Normalize lists for comparison
            if isinstance(old_val, list):
                old_val = sorted([str(x) for x in old_val])
            if isinstance(new_val, list):
                new_val = sorted([str(x) for x in new_val])

            if old_val != new_val:
                changes.append((
                    field,
                    json.dumps(old_val) if old_val else None,
                    json.dumps(new_val) if new_val else None
                ))

        return changes

    def save_changes(self, uni_listing_id, changes):
        """Uloží změny do change_history"""
        if not changes:
            return

        with get_cursor(self.conn, dict_cursor=False) as cur:
            for field, old_val, new_val in changes:
                cur.execute("""
                    INSERT INTO scr_change_history
                    (uni_listing_id, field_name, old_value, new_value)
                    VALUES (%s, %s, %s, %s)
                """, (uni_listing_id, field, old_val, new_val))

            self.conn.commit()

    def notify_change(self, uni_listing_id, changes):
        """Pošli webhook notification při změně"""
        if not WEBHOOK_URL:
            return

        payload = {
            'uni_listing_id': uni_listing_id,
            'changes': [
                {
                    'field': field,
                    'old_value': old_val,
                    'new_value': new_val
                }
                for field, old_val, new_val in changes
            ],
            'timestamp': datetime.now().isoformat()
        }

        try:
            requests.post(WEBHOOK_URL, json=payload, timeout=10)
        except Exception as e:
            self.logger.error(f"Webhook failed: {e}")

    def process_one(self):
        """Zpracuje jeden listing"""
        # Get listings s více než 1 parsovaným výsledkem
        with get_cursor(self.conn) as cur:
            cur.execute("""
                SELECT uni_listing_id, COUNT(*) as cnt
                FROM scr_parsed_data
                WHERE uni_listing_id IS NOT NULL
                GROUP BY uni_listing_id
                HAVING COUNT(*) >= 2
                ORDER BY MAX(extracted_at) DESC
                LIMIT 1
            """)

            row = cur.fetchone()
            if not row:
                return False

            uni_listing_id = row['uni_listing_id']

        # Get latest 2 data
        results = self.get_latest_data(uni_listing_id)
        if len(results) < 2:
            return False

        new_data = results[0]['data']
        old_data = results[1]['data']

        self.logger.info(f"Checking changes for listing {uni_listing_id}")

        # Detect changes
        changes = self.detect_changes(old_data, new_data)

        if changes:
            self.logger.info(f"  -> Found {len(changes)} changes")
            self.save_changes(uni_listing_id, changes)
            self.notify_change(uni_listing_id, changes)

        return True

    def run(self):
        """Main loop"""
        self.logger.info("Change detector started")

        while True:
            try:
                if not self.process_one():
                    self.logger.info("No changes to detect, waiting...")
                    time.sleep(300) # 5 minut
                    continue
            except Exception as e:
                self.logger.error(f"Error in change detector: {e}")
                time.sleep(60)

if __name__ == '__main__':
    detector = ChangeDetector()
    detector.run()
