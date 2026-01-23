import pytest
from unittest.mock import MagicMock, patch
from src.llm.prompts import PromptManager

@patch('src.llm.prompts.get_db_connection')
def test_prompt_manager(mock_get_conn):
    # Setup Mock DB
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_conn.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.__enter__.return_value = mock_cursor
    mock_cursor.__exit__.return_value = None

    pm = PromptManager()

    # Test get_prompt (found)
    mock_row = {
        'prompt_template': 'Hello {name}',
        'system_prompt': 'System',
        'model': 'gpt-4',
        'max_tokens': 100,
        'temperature': 0.7,
        'id': 1
    }
    mock_cursor.fetchone.return_value = mock_row

    config = pm.get_prompt('test_case', 'cs')
    assert config['model'] == 'gpt-4'

    # Test render
    rendered = pm.render('test_case', 'cs', name='World')
    assert rendered['prompt'] == 'Hello World'
    assert rendered['system'] == 'System'

    # Test log_execution
    pm.log_execution(1, True, 50)
    assert "INSERT INTO prompt_stats" in str(mock_cursor.execute.call_args)
