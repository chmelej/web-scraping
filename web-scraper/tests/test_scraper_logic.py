import unittest
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

from workers.scraper import Scraper

class TestScraperLogic(unittest.TestCase):
    @patch('workers.scraper.get_db_connection')
    @patch('workers.scraper.setup_logging')
    def test_fetch_batch(self, mock_log, mock_get_db):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.__enter__.return_value = mock_cur

        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        # Mock result for fetch_batch
        # fetchall should return a list of dicts (RealDictCursor)
        mock_cur.fetchall.return_value = [{'id': 1, 'url': 'http://example.com', 'uni_listing_id': 100, 'retry_count': 0, 'depth': 0}]

        scraper = Scraper()
        batch = scraper.fetch_batch(1)

        self.assertEqual(len(batch), 1)
        self.assertEqual(batch[0]['url'], 'http://example.com')
        self.assertEqual(batch[0]['uni_listing_id'], 100)

        # Verify SQL
        # Check if execute was called
        self.assertTrue(mock_cur.execute.called)
        sql = mock_cur.execute.call_args[0][0]
        self.assertIn("FROM scr_scrape_queue", sql)
        # uni_listing_id is now in the SELECT list, not necessarily in WHERE clause unless specific logic
        # But we check if it is selected
        self.assertIn("uni_listing_id", sql)

if __name__ == '__main__':
    unittest.main()
