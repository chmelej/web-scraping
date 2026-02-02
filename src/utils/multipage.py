import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from src.utils.urls import same_domain
from src.utils.country import COUNTRY_LANG_MAP

MULTIPAGE_PATTERNS = {
    'cs': {
        'contact': r'/(kontakt|kontakty|spojeni)',
        'about': r'/(o-nas|o-firme|profil)',
        'services': r'/(sluzby|nabidka|co-delame|reseni)',
        'products': r'/(produkty|vyrobky|sortiment)',
        'locations': r'/(pobocky|kde-nas-najdete|provozovny)'
    },
    'sk': {
        'contact': r'/(kontakt|kontakty)',
        'about': r'/(o-nas|profil)',
        'services': r'/(sluzby|ponuka|riesenia)',
        'products': r'/(produkty|vyrobky)',
        'locations': r'/(pobocky|kde-nas-najdete)'
    },
    'de': {
        'contact': r'/(kontakt|kontaktieren)',
        'about': r'/(uber-uns|unternehmen|profil)',
        'services': r'/(leistungen|dienstleistungen|angebot|losungen)',
        'products': r'/(produkte)',
        'locations': r'/(standorte|filialen)'
    },
    'en': {
        'contact': r'/(contact|contact-us|get-in-touch)',
        'about': r'/(about|about-us|company)',
        'services': r'/(services|what-we-do|solutions)',
        'products': r'/(products|our-products)',
        'locations': r'/(locations|branches|find-us)'
    },
    'nl': {
        'contact': r'/(contact|contacteer|contact-us|neem-contact-op)',
        'about': r'/(over-ons|bedrijf|wie-zijn-wij)',
        'services': r'/(diensten|aanbod|oplossingen)',
        'products': r'/(producten)',
        'locations': r'/(locaties|vestigingen)'
    },
    'fr': {
        'contact': r'/(contact|contactez)',
        'about': r'/(a-propos|entreprise|qui-sommes-nous)',
        'services': r'/(services|prestations|solutions)',
        'products': r'/(produits)',
        'locations': r'/(emplacements|agences)'
    }
}

def find_promising_links(html, base_url, language=None, country=None):
    """
    Najde nadějné odkazy na stejné doméně.
    Checks patterns for given language AND all languages associated with the country.
    Returns: list of (url, category) - sorted by relevance, limited to top 5.
    """
    soup = BeautifulSoup(html, 'lxml')
    
    # Collect languages to check
    langs_to_check = set()
    if language and language in MULTIPAGE_PATTERNS:
        langs_to_check.add(language)
        
    if country and country in COUNTRY_LANG_MAP:
        for lang in COUNTRY_LANG_MAP[country]:
            if lang in MULTIPAGE_PATTERNS:
                langs_to_check.add(lang)
                
    if not langs_to_check:
        langs_to_check.add('en') # Default

    candidates = []
    seen = set()

    for link in soup.find_all('a', href=True):
        url = urljoin(base_url, link['href'])

        # Musí být stejná doména
        if not same_domain(url, base_url):
            continue

        # Už přidáno?
        if url in seen:
            continue

        # Match pattern?
        for lang in langs_to_check:
            patterns = MULTIPAGE_PATTERNS[lang]
            matched = False
            for category, pattern in patterns.items():
                if re.search(pattern, url, re.IGNORECASE):
                    candidates.append((url, category))
                    seen.add(url)
                    matched = True
                    break
            if matched:
                break

    # Sort candidates
    # Criteria: 1. Path depth (fewer slashes is better/higher up), 2. Path length (shorter is simpler)
    def score_url(item):
        u = item[0]
        path = urlparse(u).path
        # Count non-empty segments
        segments = [s for s in path.split('/') if s]
        depth = len(segments)
        length = len(path)
        return (depth, length)

    candidates.sort(key=score_url)

    # Return top 5
    return candidates[:5]
