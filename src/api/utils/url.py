import urllib.parse
import hashlib
import re

TRACKING_PARAMS = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'gclid', 'fbclid', 'msclkid', 'dclid', 'zanpid', 'igshid',
    'sessionid', 'phpsessid', 'sid', 'ncid'
}

def unify_url(url: str) -> str:
    """
    Normalizes a URL to a unified string representation.
    Removes protocols, www., trailing slashes, fragments, tracking parameters,
    and standardizes encodings and case.
    """
    url_lower = url.lower()
    if not url_lower.startswith('http://') and not url_lower.startswith('https://'):
        url = 'http://' + url

    parsed = urllib.parse.urlparse(url)

    # 2. Lowercase domain
    netloc = parsed.netloc.lower()

    # 3. Remove 'www.' prefix
    if netloc.startswith('www.'):
        netloc = netloc[4:]

    # 4. Remove default ports if present
    if netloc.endswith(':80'):
        netloc = netloc[:-3]
    elif netloc.endswith(':443'):
        netloc = netloc[:-4]

    # 5. Unquote path and query (convert %20 to space, etc.)
    path = urllib.parse.unquote(parsed.path)

    # 6. Remove multiple consecutive slashes
    path = re.sub(r'/+', '/', path)

    # 7. Remove trailing slash completely (or preserve root slash depending on test requirements, let's preserve root if it's just '/')
    if path.endswith('/') and len(path) > 1:
        path = path[:-1]

    # If path is empty, maybe default to '/' or remove completely.
    # Let's see what the tests expect: "example.com/" vs "example.com".
    # Since tests have "example.com/", we should ensure root path is "/"
    if not path:
        path = '/'
    # If we want to remove trailing slash even for root, tests should reflect "example.com".
    # Wait, the user specifically said: "lomítko na konci páth je zbytečné". Let's remove it completely even if it's the root path.
    if path == '/':
        path = ''

    path = path.lower()

    # 8. Handle query parameters
    query_params = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)

    filtered_params = []
    for k, v in query_params:
        k_lower = k.lower()
        if k_lower not in TRACKING_PARAMS:
            filtered_params.append((k_lower, v.lower()))

    # 10. Sort query parameters alphabetically
    filtered_params.sort()

    # 11. Reconstruct query string
    unified_query = urllib.parse.urlencode(filtered_params)

    # 13. Construct unified string
    unified_url = netloc + path
    if unified_query:
        unified_url += '?' + unified_query

    return unified_url

def get_url_hash(url: str) -> str:
    """
    Returns a shortened MD5 hash of the unified URL.
    """
    unified = unify_url(url)
    return hashlib.md5(unified.encode('utf-8')).hexdigest()
