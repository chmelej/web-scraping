import pytest
from unittest.mock import MagicMock, patch
from src.utils.bloom import BloomFilterManager

@patch('src.utils.bloom.get_db_connection')
def test_bloom_manager(mock_get_conn):
    # Setup Mock DB
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_conn.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.__enter__.return_value = mock_cursor
    mock_cursor.__exit__.return_value = None

    bfm = BloomFilterManager()

    # Test Create
    bf = bfm.create_filter('test_filter')
    assert bf is not None
    # Check DB insert
    assert mock_cursor.execute.call_count == 1
    assert "INSERT INTO bloom_filters" in str(mock_cursor.execute.call_args)

    # Test Add
    mock_cursor.execute.reset_mock()
    # Mock load_filter to return our bf (so it doesn't try to load from DB)
    with patch.object(bfm, 'load_filter', return_value=bf):
        result = bfm.add('test_filter', 'item1')
        assert result is True
        assert "item1" in bf

        # Check DB update
        assert mock_cursor.execute.call_count >= 1
        calls = [str(call) for call in mock_cursor.execute.mock_calls]
        assert any("INSERT INTO bloom_filter_items" in c for c in calls)

        # Test Add Duplicate
        result = bfm.add('test_filter', 'item1')
        assert result is False

    # Test Check
    with patch.object(bfm, 'load_filter', return_value=bf):
        assert bfm.check('test_filter', 'item1') is True
        assert bfm.check('test_filter', 'item2') is False
