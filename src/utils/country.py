from src.utils.urls import extract_domain
import tldextract

COUNTRY_LANG_MAP = {
    'cz': ['cs'],
    'sk': ['sk', 'cs', 'hu'],
    'be': ['nl', 'fr', 'de', 'en'],
    'nl': ['nl', 'en'],
    'fr': ['fr'],
    'ro': ['ro'],
    'gb': ['en'],
    'de': ['de'],
}

LANG_TO_COUNTRY_DEFAULT = {
    'cs': 'cz',
    'sk': 'sk',
    'ro': 'ro',
    'nl': 'nl', # default if no TLD info
    'fr': 'fr',
    'de': 'de',
    'en': 'gb',
}

def detect_country(url, language):
    """
    Detect country based on URL TLD and language.
    Returns: iso2 country code (e.g., 'cz', 'be')
    """
    # 1. Check TLD
    extracted = tldextract.extract(url)
    suffix = extracted.suffix.lower()
    
    # Handle composite TLDs if necessary, but tldextract handles co.uk etc.
    # suffix 'be' -> 'be'
    if suffix in COUNTRY_LANG_MAP:
        return suffix
    
    # 2. Fallback to language
    if language in LANG_TO_COUNTRY_DEFAULT:
        return LANG_TO_COUNTRY_DEFAULT[language]
    
    # 3. Default
    return 'unknown'
