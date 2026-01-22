import json
import time
from src.utils.db import get_db_connection, get_cursor
from src.utils.logging_config import setup_logging

class ChangeDetector:
    def __init__(self):
        self.logger = setup_logging('change_detector', 'change_detector.log')
        try:
            self.conn = get_db_connection()
        except:
            self.conn = None
            self.logger.error("ChangeDetector failed to connect to DB")

    def get_previous_data(self, unit_listing_id, current_extracted_at):
        """Získá předchozí parsovaná data pro listing"""
        if not self.conn:
            return None

        with get_cursor(self.conn) as cur:
            cur.execute("""
                SELECT data
                FROM parsed_data
                WHERE unit_listing_id = %s
                  AND extracted_at < %s
                ORDER BY extracted_at DESC
                LIMIT 1
            """, (unit_listing_id, current_extracted_at))

            row = cur.fetchone()
            return row['data'] if row else None

    def detect_changes(self, old_data, new_data):
        """
        Porovná 2 JSON objekty a vrátí změny
        Returns: list of (field_name, old_value, new_value)
        """
        if not old_data:
            return [] # First scrape, no changes

        changes = []

        # Fields to track
        tracked_fields = [
            'company_name', 'emails', 'phones', 'ico',
            'address', 'opening_hours', 'social_media'
        ]

        for field in tracked_fields:
            old_val = old_data.get(field)
            new_val = new_data.get(field)

            # Normalize lists for comparison
            if isinstance(old_val, list):
                old_val = sorted(old_val)
            if isinstance(new_val, list):
                new_val = sorted(new_val)

            if old_val != new_val:
                changes.append((
                    field,
                    json.dumps(old_val) if old_val else None,
                    json.dumps(new_val) if new_val else None
                ))

        return changes

    def save_changes(self, unit_listing_id, changes):
        """Uloží změny do change_history"""
        if not changes or not self.conn:
            return

        try:
            with get_cursor(self.conn, dict_cursor=False) as cur:
                for field, old_val, new_val in changes:
                    cur.execute("""
                        INSERT INTO change_history
                        (unit_listing_id, field_name, old_value, new_value)
                        VALUES (%s, %s, %s, %s)
                    """, (unit_listing_id, field, old_val, new_val))
                # Commit handled by caller
        except Exception as e:
            self.logger.error(f"Error saving changes: {e}")
            raise e

    def process_one(self):
        """Zpracuje jeden unchecked parsed_data row"""
        if not self.conn:
            return False

        try:
            with get_cursor(self.conn, dict_cursor=True) as cur: # Keep dict cursor for fetching
                # 1. Select one unchecked row
                cur.execute("""
                    SELECT id, unit_listing_id, data, extracted_at
                    FROM parsed_data
                    WHERE change_checked = FALSE
                      AND unit_listing_id IS NOT NULL
                    ORDER BY extracted_at ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                """)

                target = cur.fetchone()
                if not target:
                    return False

                row_id = target['id']
                unit_listing_id = target['unit_listing_id']
                new_data = target['data']
                extracted_at = target['extracted_at']

                self.logger.info(f"Checking changes for listing {unit_listing_id} (row {row_id})")

                # 2. Get previous data
                old_data = self.get_previous_data(unit_listing_id, extracted_at)

                # 3. Detect changes
                changes = self.detect_changes(old_data, new_data)

                if changes:
                    self.logger.info(f"  -> Found {len(changes)} changes")
                    self.save_changes(unit_listing_id, changes)

                # 4. Mark as checked
                cur.execute("""
                    UPDATE parsed_data
                    SET change_checked = TRUE
                    WHERE id = %s
                """, (row_id,))

                self.conn.commit()
                return True

        except Exception as e:
            self.logger.error(f"Error in process_one: {e}")
            if self.conn:
                self.conn.rollback()
            return False

    def run(self):
        """Main loop"""
        self.logger.info("ChangeDetector started")

        while True:
            if not self.process_one():
                self.logger.info("No changes to detect, waiting...")
                time.sleep(300) # 5 minut
                continue

if __name__ == '__main__':
    try:
        detector = ChangeDetector()
        detector.run()
    except KeyboardInterrupt:
        print("Stopping detector...")
