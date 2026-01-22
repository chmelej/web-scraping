import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

from utils.bloom import BloomFilterManager

class TestBloomFilter(unittest.TestCase):
    @patch('utils.bloom.get_db_connection')
    def test_add_item(self, mock_get_db):
        # Setup mock DB
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        # Ensure context manager works
        mock_cur.__enter__.return_value = mock_cur

        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        # Mock fetchone to return None (filter doesn't exist)
        mock_cur.fetchone.return_value = None

        bfm = BloomFilterManager()

        # Test add
        bfm.add('test_filter', 'item1')

        # Verify SQL calls
        calls = mock_cur.execute.call_args_list

        # Check insert item call
        # We look for "INSERT INTO scr_bloom_filter_items"
        insert_calls = [c for c in calls if "INSERT INTO scr_bloom_filter_items" in c[0][0]]
        self.assertTrue(len(insert_calls) > 0, "Should insert item into scr_bloom_filter_items")

        # Check update count call
        update_calls = [c for c in calls if "UPDATE scr_bloom_filters" in c[0][0] and "item_count" in c[0][0]]
        self.assertTrue(len(update_calls) > 0, "Should update item_count")

if __name__ == '__main__':
    unittest.main()
