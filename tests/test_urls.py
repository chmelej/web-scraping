from src.utils.urls import normalize_url, extract_domain, same_domain

def test_normalize_url():
    assert normalize_url('https://Example.com/') == 'https://example.com'
    assert normalize_url('http://test.com#anchor') == 'http://test.com'

def test_extract_domain():
    assert extract_domain('https://www.example.com/path') == 'www.example.com'

def test_same_domain():
    assert same_domain('https://test.com/a', 'https://test.com/b') == True
    assert same_domain('https://test.com', 'https://other.com') == False
