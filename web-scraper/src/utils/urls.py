from urllib.parse import urlparse, urljoin
import re

def normalize_url(url):
    """Normalizuje URL pro deduplikaci"""
    url = url.lower().strip()
    url = re.sub(r'/$', '', url)  # remove trailing slash
    url = re.sub(r'#.*$', '', url)  # remove fragment
    url = re.sub(r'\?.*$', '', url)  # remove query params (optional)
    return url

def extract_domain(url):
    """Extrahuje doménu z URL"""
    parsed = urlparse(url)
    return parsed.netloc.lower()

def same_domain(url1, url2):
    """Kontroluje zda jsou URL ze stejné domény"""
    return extract_domain(url1) == extract_domain(url2)

def is_valid_url(url):
    """Základní validace URL"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False
