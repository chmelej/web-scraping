import pytest
from unittest.mock import MagicMock, patch
from src.workers.scraper import Scraper

@patch('src.workers.scraper.get_db_connection')
def test_scraper_process_one_mock(mock_get_conn):
    # Setup Mock DB
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_conn.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    # Mock context manager for cursor
    mock_cursor.__enter__.return_value = mock_cursor
    mock_cursor.__exit__.return_value = None

    # Setup Scraper
    scraper = Scraper()

    # Mock Queue Item (what fetchone returns)
    queue_item = {
        'id': 123,
        'url': 'https://example.com',
        'retry_count': 0,
        'unit_listing_id': 1,
        'depth': 0
    }

    # First fetchone returns item, second (for save_result returning id) returns [456]
    mock_cursor.fetchone.side_effect = [queue_item, [456], None]

    # Mock Scrape Result
    scrape_result = {
        'html': '<html><html lang="en"><body>Test Content</body></html>',
        'status_code': 200,
        'headers': {'Content-Type': 'text/html'},
        'ip_address': '127.0.0.1',
        'redirected_from': None,
        'error': None
    }

    # Patch scrape_url to avoid network calls
    with patch.object(scraper, 'scrape_url', return_value=scrape_result) as mock_scrape:

        # Run process_one
        result = scraper.process_one()

        # Assertions
        assert result is True
        mock_scrape.assert_called_once_with('https://example.com')

        # Verify DB calls
        # 1. Select from queue
        assert mock_cursor.execute.call_count >= 1
        # Check if UPDATE scrape_queue (processing) was called
        # Check if INSERT INTO scrape_results was called
        # Check if UPDATE scrape_queue (completed) was called

        calls = [str(call) for call in mock_cursor.execute.mock_calls]
        assert any("SELECT id, url" in c for c in calls)
        assert any("UPDATE scrape_queue" in c for c in calls)
        assert any("INSERT INTO scrape_results" in c for c in calls)
