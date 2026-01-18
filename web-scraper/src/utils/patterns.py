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
        'cs': r'\b(IČO?:?\s*)?(\d{8})\b',
        'sk': r'\b(IČO?:?\s*)?(\d{8})\b',
    },

    'social_media': {
        'facebook': r'(?:https?://)?(?:www\.)?facebook\.com/[\w\-\.]+',
        'linkedin': r'(?:https?://)?(?:www\.)?linkedin\.com/(?:company|in)/[\w\-]+',
        'instagram': r'(?:https?://)?(?:www\.)?instagram\.com/[\w\-\.]+',
    }
}

def extract_emails(text):
    """Extract všechny emaily"""
    return list(set(re.findall(PATTERNS['email'], text, re.IGNORECASE)))

def extract_phones(text, language='cs'):
    """Extract telefony podle jazyka"""
    pattern = PATTERNS['phone'].get(language, PATTERNS['phone']['cs'])
    phones = re.findall(pattern, text)
    return [re.sub(r'\s', '', p) for p in phones]  # normalize

def extract_ico(text, language='cs'):
    """Extract IČO"""
    pattern = PATTERNS['ico'].get(language)
    if not pattern:
        return None

    matches = re.findall(pattern, text)
    if matches:
        # Vrať samotné číslo (bez "IČO:" prefixu)
        # matches[0] might be tuple ('IČO: ', '12345678')
        if isinstance(matches[0], tuple):
            return matches[0][-1]
        return matches[0]
    return None

def extract_social_media(text):
    """Extract social media links"""
    result = {}
    for platform, pattern in PATTERNS['social_media'].items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            result[platform] = matches[0]
    return result
