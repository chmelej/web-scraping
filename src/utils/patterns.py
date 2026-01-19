import re

PATTERNS = {
    'email': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',

    'phone': {
        'cs': r'\+?420\s?\d{3}\s?\d{3}\s?\d{3}',
        'sk': r'\+?421\s?\d{3}\s?\d{3}\s?\d{3}',
        'de': r'\+?49\s?\d{3,4}\s?\d{3,8}',
        'nl': r'\+?31\s?\d{2,3}\s?\d{6,7}',
        'fr': r'\+?33\s?\d{1}\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{2}',
        'en': r'\+?44\s?\d{4}\s?\d{6}',
    },

    'ico': {
        'cs': r'\b(IČO?:?:?\s*)?(\d{8})\b',
        'sk': r'\b(IČO?:?:?\s*)?(\d{8})\b',
    },

    'social_media': {
        'facebook': r'(?:https?://)?(?:www\.)?facebook\.com/[\w\-\.]+',
        'linkedin': r'(?:https?://)?(?:www\.)?linkedin\.com/(?:company|in)/[\w\-]+',
        'instagram': r'(?:https?://)?(?:www\.)?instagram\.com/[\w\-\.]+',
        'twitter': r'(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/[\w\-\.]+',
    }
}

def extract_emails(text):
    """Extract všechny emaily"""
    return list(set(re.findall(PATTERNS['email'], text, re.IGNORECASE)))

def extract_phones(text, language='cs'):
    """Extract telefony podle jazyka"""
    pattern = PATTERNS['phone'].get(language, PATTERNS['phone']['cs'])
    phones = re.findall(pattern, text)
    # Normalize: remove spaces
    return [re.sub(r'\s', '', p) for p in phones]

def extract_ico(text, language='cs'):
    """Extract IČO"""
    pattern = PATTERNS['ico'].get(language)
    if not pattern:
        return None

    matches = re.findall(pattern, text, re.IGNORECASE)
    if matches:
        # matches[0] is tuple ('IČO: ', '12345678') or just '12345678' depending on group
        # The regex has 2 groups. The number is in group 2.
        # findall returns list of tuples if multiple groups.
        for match in matches:
            if isinstance(match, tuple):
                return match[1]
            return match

    return None

def extract_social_media(text):
    """Extract social media links"""
    result = {}
    for platform, pattern in PATTERNS['social_media'].items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            result[platform] = matches[0]
    return result
