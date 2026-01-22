from urllib.parse import urlparse, urljoin, parse_qsl, urlencode, urlunparse
import re

# List of tracking parameters to strip
TRACKING_PARAMS = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'fbclid', 'gclid', 'gclsrc', 'dclid', 'msclkid', 'zanpid',
    '_ga', '_gl', 'mc_eid', 'mc_cid', 'yclid', '_hsenc', '_hsmi'
}

def clean_url(url):
    """
    Cleans URL by removing known tracking parameters and fragments.
    Preserves functional query parameters (e.g. ?page=2, ?id=123).
    """
    if not url:
        return url
        
    try:
        url = url.strip()
        parsed = urlparse(url)
        
        # Filter query parameters
        query_params = parse_qsl(parsed.query, keep_blank_values=True)
        cleaned_params = [
            (k, v) for k, v in query_params 
            if k.lower() not in TRACKING_PARAMS
        ]
        
        # Rebuild URL
        # Sort params to ensure consistent ordering for deduplication
        cleaned_params.sort(key=lambda x: x[0])
        new_query = urlencode(cleaned_params)
        
        # Remove fragment, keep scheme and netloc lowercase
        cleaned = parsed._replace(
            scheme=parsed.scheme.lower(),
            netloc=parsed.netloc.lower(),
            query=new_query, 
            fragment=''
        )
        
        # Remove trailing slash from path if it's not root
        if cleaned.path != '/' and cleaned.path.endswith('/'):
            cleaned = cleaned._replace(path=cleaned.path.rstrip('/'))

        return urlunparse(cleaned)
    except Exception:
        return url

def normalize_url(url):
    """
    Legacy wrapper for backward compatibility or stricter normalization.
    Currently maps to clean_url.
    """
    return clean_url(url)

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