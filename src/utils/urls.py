from urllib.parse import urlparse, urljoin
import re

def normalize_url(url):
    """Normalizuje URL pro deduplikaci"""
    if not url:
        return ""
    url = url.lower().strip()
    url = re.sub(r'/$', '', url)  # remove trailing slash
    url = re.sub(r'#.*$', '', url)  # remove fragment
    # url = re.sub(r'\?.*$', '', url)  # remove query params (optional - keep for now as some sites need them)
    return url

def extract_domain(url):
    """Extrahuje doménu z URL"""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except:
        return ""

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
