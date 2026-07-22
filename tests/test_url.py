import pytest
from src.api.utils.url import unify_url, get_url_hash

def test_unify_url_protocols():
    assert unify_url("http://example.com") == "example.com"
    assert unify_url("https://example.com") == "example.com"

def test_unify_url_www():
    assert unify_url("https://www.example.com") == "example.com"
    assert unify_url("http://WWW.Example.Com") == "example.com"

def test_unify_url_trailing_slashes():
    assert unify_url("https://example.com/") == "example.com"
    assert unify_url("https://example.com/foo/") == "example.com/foo"
    assert unify_url("https://example.com/foo//bar///") == "example.com/foo/bar"

def test_unify_url_encoding():
    assert unify_url("https://example.com/foo%20bar") == "example.com/foo bar"
    assert unify_url("https://example.com/foo+bar") == "example.com/foo+bar"

def test_unify_url_anchors():
    assert unify_url("https://example.com/page#section1") == "example.com/page"
    assert unify_url("https://example.com/#") == "example.com"

def test_unify_url_query_params():
    # Sorting
    assert unify_url("https://example.com/?b=2&a=1") == "example.com?a=1&b=2"
    # Tracking params removal
    assert unify_url("https://example.com/?utm_source=google&q=test") == "example.com?q=test"
    assert unify_url("https://example.com/?fbclid=123&sessionid=abc") == "example.com"
    # Complex case
    complex_url = "HTTPS://WWW.EXAMPLE.COM/Page%20Name/?UTM_CAMPAIGN=spring&b=2&a=1#top"
    assert unify_url(complex_url) == "example.com/page name?a=1&b=2"

def test_url_hash():
    hash1 = get_url_hash("http://www.example.com/foo?b=1&a=2#anchor")
    hash2 = get_url_hash("https://example.com/foo/?a=2&b=1&utm_source=abc")
    assert hash1 == hash2
    assert len(hash1) == 32 # MD5 length
