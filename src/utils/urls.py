from urllib.parse import urlparse, urljoin, parse_qsl, urlencode, urlunparse, unquote
import hashlib
import re

# List of tracking parameters to strip
TRACKING_PARAMS = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'fbclid', 'gclid', 'gclsrc', 'dclid', 'msclkid', 'zanpid', 'igshid',
    'sessionid', 'phpsessid', 'sid', 'ncid', '_ga', '_gl', 'mc_eid', 'mc_cid',
    'yclid', '_hsenc', '_hsmi', 'y_source', 'affiliate', 'clickid', 't_id',
    'ref', 'referrer', 'subid'
}

def clean_url(url: str) -> str:
    """
    Cleans URL by removing known tracking parameters and fragments.
    Preserves protocol (http/https) and valid structure for fetching.
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
        
        cleaned_params.sort(key=lambda x: x[0])
        new_query = urlencode(cleaned_params)
        
        cleaned = parsed._replace(
            scheme=parsed.scheme.lower() if parsed.scheme else 'http',
            netloc=parsed.netloc.lower(),
            query=new_query, 
            fragment=''
        )
        
        if cleaned.path.endswith('/'):
            cleaned = cleaned._replace(path=cleaned.path.rstrip('/'))

        return urlunparse(cleaned)
    except Exception:
        return url

def unify_url(url: str) -> str:
    """
    Aggressively unifies a URL into a canonical string key for deduplication.
    Strips protocols (http/https), www. prefix, trailing slashes, fragments,
    and tracking parameters, and standardizes query param order and case.
    e.g. 'https://www.example.com/foo/?b=2&a=1' -> 'example.com/foo?a=1&b=2'
    """
    if not url:
        return ''
    
    url = url.strip()
    url_lower = url.lower()
    if not url_lower.startswith('http://') and not url_lower.startswith('https://'):
        url = 'http://' + url

    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()

        if netloc.startswith('www.'):
            netloc = netloc[4:]

        if netloc.endswith(':80'):
            netloc = netloc[:-3]
        elif netloc.endswith(':443'):
            netloc = netloc[:-4]

        path = unquote(parsed.path)
        path = re.sub(r'/+', '/', path)

        if path.endswith('/') and len(path) > 1:
            path = path[:-1]
        if path == '/':
            path = ''
        path = path.lower()

        query_params = parse_qsl(parsed.query, keep_blank_values=True)
        filtered_params = [
            (k.lower(), v.lower()) for k, v in query_params
            if k.lower() not in TRACKING_PARAMS
        ]
        filtered_params.sort()
        unified_query = urlencode(filtered_params)

        unified_url = netloc + path
        if unified_query:
            unified_url += '?' + unified_query
        return unified_url
    except Exception:
        return url.lower()

def normalize_url(url: str) -> str:
    """
    Cleans URL preserving valid scheme (http/https). Alias for clean_url.
    """
    return clean_url(url)

def get_url_hash(url: str) -> str:
    """
    Returns an MD5 hash of the unified URL key.
    """
    unified = unify_url(url)
    return hashlib.md5(unified.encode('utf-8')).hexdigest()

def extract_domain(url: str) -> str:
    """Extrahuje doménu z URL"""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except Exception:
        return ""

def same_domain(url1: str, url2: str) -> bool:
    """Kontroluje zda jsou URL ze stejné domény"""
    return extract_domain(url1) == extract_domain(url2)

def is_valid_url(url: str) -> bool:
    """Základní validace URL"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False