import pytest
from unittest.mock import MagicMock, patch
from src.workers.parser import Parser

@pytest.fixture
def mock_db_parser():
    with patch('src.workers.parser.get_db_connection') as mock_conn:
        mock_conn.return_value = MagicMock()
        parser = Parser()
        return parser

def test_parse_simple_page(mock_db_parser):
    html = """
    <html>
    <head><title>Test Firma s.r.o.</title></head>
    <body>
        <p>Email: info@test.cz</p>
        <p>Tel: +420 123 456 789</p>
        <p>IČO: 12345678</p>
    </body>
    </html>
    """

    data = mock_db_parser.parse_html(html, 'cs', 'https://test.cz')

    assert 'info@test.cz' in data['emails']
    assert len(data['phones']) > 0
    assert data['ico'] == '12345678'
    assert data['company_name'] == 'Test Firma s.r.o.'
