import pytest
from src.utils.multipage import find_promising_links

def test_default_language_english():
    html = """
    <html>
        <body>
            <a href="/contact-us">Contact</a>
            <a href="/about">About Us</a>
            <a href="/random">Random</a>
        </body>
    </html>
    """
    base_url = "https://example.com"
    result = find_promising_links(html, base_url)

    # Verify it finds english promising links by default
    assert len(result) == 2
    # The links are sorted. /about length is 6, /contact-us length is 11.
    # So /about might be first.
    urls = [item[0] for item in result]
    assert "https://example.com/about" in urls
    assert "https://example.com/contact-us" in urls
    categories = [item[1] for item in result]
    assert "about" in categories
    assert "contact" in categories

def test_specific_language():
    html = """
    <html>
        <body>
            <a href="/kontakt">Kontakt</a>
            <a href="/o-nas">O nas</a>
            <a href="/contact-us">Contact Us</a>
        </body>
    </html>
    """
    base_url = "https://example.cz"
    result = find_promising_links(html, base_url, language='cs')

    urls = [item[0] for item in result]
    assert "https://example.cz/kontakt" in urls
    assert "https://example.cz/o-nas" in urls
    assert "https://example.cz/contact-us" not in urls # because en is not used

def test_country_fallback_logic():
    html = """
    <html>
        <body>
            <a href="/kontakt">Kontakt (SK/CS)</a>
            <a href="/o-nas">O nas (CS)</a>
        </body>
    </html>
    """
    base_url = "https://example.sk"
    # Country sk maps to ['sk', 'cs', 'hu']
    result = find_promising_links(html, base_url, country='sk')

    urls = [item[0] for item in result]
    assert "https://example.sk/kontakt" in urls
    assert "https://example.sk/o-nas" in urls

def test_external_domains_ignored():
    html = """
    <html>
        <body>
            <a href="/contact">Contact</a>
            <a href="https://external.com/contact">External Contact</a>
        </body>
    </html>
    """
    base_url = "https://example.com"
    result = find_promising_links(html, base_url)

    urls = [item[0] for item in result]
    assert "https://example.com/contact" in urls
    assert "https://external.com/contact" not in urls

def test_duplicate_links():
    html = """
    <html>
        <body>
            <a href="/contact">Contact</a>
            <a href="/contact">Contact Us Again</a>
            <a href="https://example.com/contact">Full URL Contact</a>
        </body>
    </html>
    """
    base_url = "https://example.com"
    result = find_promising_links(html, base_url)

    assert len(result) == 1
    assert result[0][0] == "https://example.com/contact"

def test_sorting_logic():
    html = """
    <html>
        <body>
            <a href="/company/info/contact">Deep Contact</a>
            <a href="/contact-us">Longer Contact</a>
            <a href="/contact">Short Contact</a>
        </body>
    </html>
    """
    base_url = "https://example.com"
    result = find_promising_links(html, base_url)

    assert len(result) == 3
    urls = [item[0] for item in result]
    # depth 1, length 8
    assert urls[0] == "https://example.com/contact"
    # depth 1, length 11
    assert urls[1] == "https://example.com/contact-us"
    # depth 3, length 21
    assert urls[2] == "https://example.com/company/info/contact"

def test_max_returned_items():
    html = """
    <html>
        <body>
            <a href="/contact">1</a>
            <a href="/about">2</a>
            <a href="/services">3</a>
            <a href="/products">4</a>
            <a href="/locations">5</a>
            <a href="/what-we-do">6</a>
        </body>
    </html>
    """
    base_url = "https://example.com"
    result = find_promising_links(html, base_url)

    assert len(result) == 5

def test_edge_cases():
    # malformed html and links without href
    html = """
    <html>
        <body>
            <a>No href</a>
            <a href="">Empty href</a>
            <a href="/contact">Good link</a>
            <div href="/about">Not a link</div>
        </body>
    </html>
    """
    base_url = "https://example.com"
    result = find_promising_links(html, base_url)

    assert len(result) == 1
    assert result[0][0] == "https://example.com/contact"
