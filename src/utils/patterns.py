import re

PATTERNS = {
    'email': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',

    'phone': {
        'cz': r'\+?420\s?\d{3}\s?\d{3}\s?\d{3}',
        'sk': r'\+?421\s?\d{3}\s?\d{3}\s?\d{3}',
        'de': r'\+?49\s?\d{3,4}\s?\d{3,8}',
        'nl': r'\+?31\s?\d{2,3}\s?\d{6,7}',
        'fr': r'\+?33\s?\d{1}\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{2}',
        'gb': r'\+?44\s?\d{4}\s?\d{6}',
        # BE: Matches 0, +32, 0032 followed by 8 or 9 digits, with optional separators
        'be': r'(?:0032|\+32|(?<!0)0)[\s\-\./]?(?:\d[\s\-\./]*){8,9}',
    },

    'org_num': {
        'cz': r'\b(\d{8})\b', # IČO
        'sk': r'\b(\d{8})\b', # IČO
        'be': r'\b((?:BE)? ?0?\d{3}[\.\s]?\d{3}[\.\s]?\d{3})\b', # BE Enterprise number 0xxx.xxx.xxx
    },

    'social_media': {
        'facebook': r'(?:https?://)?(?:www\.)?facebook\.com/[\w\-\.]+',
        'twitter': r'(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/[\w\-\.]+',
        'instagram': r'(?:https?://)?(?:www\.)?instagram\.com/[\w\-\.]+',
        'linkedin': r'(?:https?://)?(?:www\.)?linkedin\.com/(?:company|in|school)/[\w\-\.]+',
        'youtube': r'(?:https?://)?(?:www\.)?youtube\.com/(?:channel|user|c|@)[\w\-\.]+',
        'google_business': r'(?:https?://)?(?:www\.)?(?:google\.com/maps.*cid=\d+|goo\.gl/maps/[\w\-\.]+|business\.google\.com/[\w\-\./]+|g\.page/[\w\-\./]+)',
    }
}

def extract_emails(text):
    """Extract všechny emaily"""
    return list(set(re.findall(PATTERNS['email'], text, re.IGNORECASE)))

def extract_phones(text, country='cz'):
    """Extract telefony podle zeme"""
    pattern = PATTERNS['phone'].get(country, PATTERNS['phone']['cz'])
    phones = re.findall(pattern, text)
    return [re.sub(r'[\s\-\./]', '', p) for p in phones]  # normalize removing spaces, dots, dashes, slashes

def validate_cz_ico(ico):
    """Validate CZ IČO (checksum)"""
    if not ico or len(ico) != 8 or not ico.isdigit():
        return False
    
    weights = [8, 7, 6, 5, 4, 3, 2]
    s = sum(int(ico[i]) * weights[i] for i in range(7))
    remainder = s % 11
    
    checksum = 0
    if remainder == 0:
        checksum = 1
    elif remainder == 1:
        checksum = 0
    else:
        checksum = 11 - remainder
        
    return int(ico[7]) == checksum

def validate_be_org_num(org_num):
    """
    Validate BE Enterprise Number (Modulo 97)
    Format: 0 or 1 followed by 9 digits.
    Logic:
    - Must be 10 digits (pad left with 0 if 9)
    - 1st digit must be 0 or 1
    - If 1st digit is 0, 2nd digit cannot be 0 or 1 (Range >= 0200.000.000)
    - Modulo 97 check
    """
    # Normalize: remove dots, spaces, BE prefix
    clean = re.sub(r'[^0-9]', '', org_num)
    
    if len(clean) == 9:
        clean = '0' + clean
        
    if len(clean) != 10:
        return False
        
    # Check range/format
    first_digit = int(clean[0])
    second_digit = int(clean[1])
    
    if first_digit not in [0, 1]:
        return False
        
    if first_digit == 0 and second_digit in [0, 1]:
        return False
        
    base = int(clean[:8])
    check = int(clean[8:])
    
    # 97 - (base % 97) == check
    remainder = base % 97
    calc_check = 97 - remainder
    
    return calc_check == check

def extract_org_num(text, country='cz'):
    """Extract Organization Number (IČO, etc.) with validation"""
    pattern = PATTERNS['org_num'].get(country)
    if not pattern:
        return None

    matches = re.findall(pattern, text)
    for match in matches:
        # Match can be tuple if groups are used, but here simple groups
        candidate = match if isinstance(match, str) else match[0]
        candidate = candidate.strip()
        
        # Validation
        if country == 'cz':
            if validate_cz_ico(candidate):
                return candidate
        elif country == 'be':
            if validate_be_org_num(candidate):
                return candidate
        else:
            # Default: accept first match
            return candidate
            
    return None

def extract_social_media(text):
    """Extract social media links from text (not robust for HREF)"""
    result = {}
    for platform, pattern in PATTERNS['social_media'].items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            result[platform] = matches[0]
    return result

def extract_social_media_from_soup(soup):
    """Extract social media links from 'a' tags hrefs"""
    result = {}
    # Iterate all links
    for a in soup.find_all('a', href=True):
        href = a['href']
        for platform, pattern in PATTERNS['social_media'].items():
            if platform not in result and re.search(pattern, href, re.IGNORECASE):
                result[platform] = href
    return result