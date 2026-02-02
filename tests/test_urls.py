import pytest
from src.utils.urls import normalize_url, extract_domain, same_domain, is_valid_url

def test_normalize_url():
    assert normalize_url('https://Example.com/') == 'https://example.com'
    assert normalize_url('http://test.com#anchor') == 'http://test.com'
    assert normalize_url('http://test.com?q=1') == 'http://test.com'

def test_extract_domain():
    assert extract_domain('https://www.example.com/path') == 'www.example.com'
    assert extract_domain('http://sub.domain.co.uk') == 'sub.domain.co.uk'

def test_same_domain():
    assert same_domain('https://test.com/a', 'https://test.com/b') == True
    assert same_domain('https://test.com', 'https://other.com') == False

def test_is_valid_url():
    assert is_valid_url('https://google.com') == True
    assert is_valid_url('not-a-url') == False
