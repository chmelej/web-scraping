import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from src.utils.urls import same_domain

MULTIPAGE_PATTERNS = {
    'cs': {
        'contact': r'/(kontakt|kontakty|spojeni)',
        'about': r'/(o-nas|o-firme|profil)',
        'services': r'/(sluzby|nabidka|co-delame)',
        'locations': r'/(pobocky|kde-nas-najdete|provozovny)'
    },
    'sk': {
        'contact': r'/(kontakt|kontakty)',
        'about': r'/(o-nas|profil)',
        'services': r'/(sluzby|ponuka)',
        'locations': r'/(pobocky|kde-nas-najdete)'
    },
    'de': {
        'contact': r'/(kontakt|kontaktieren)',
        'about': r'/(uber-uns|unternehmen|profil)',
        'services': r'/(leistungen|dienstleistungen|angebot)',
        'locations': r'/(standorte|filialen)'
    },
    'en': {
        'contact': r'/(contact|contact-us|get-in-touch)',
        'about': r'/(about|about-us|company)',
        'services': r'/(services|what-we-do|solutions)',
        'locations': r'/(locations|branches|find-us)'
    },
    'nl': {
        'contact': r'/(contact|contacteer)',
        'about': r'/(over-ons|bedrijf)',
        'services': r'/(diensten|aanbod)',
        'locations': r'/(locaties|vestigingen)'
    },
    'fr': {
        'contact': r'/(contact|contactez)',
        'about': r'/(a-propos|entreprise)',
        'services': r'/(services|prestations)',
        'locations': r'/(emplacements|agences)'
    }
}

def find_promising_links(html, base_url, language):
    """
    Najde nadějné odkazy na stejné doméně
    Returns: list of (url, category)
    """
    soup = BeautifulSoup(html, 'lxml')
    patterns = MULTIPAGE_PATTERNS.get(language, MULTIPAGE_PATTERNS['en'])

    promising = []
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
        for category, pattern in patterns.items():
            if re.search(pattern, url, re.IGNORECASE):
                promising.append((url, category))
                seen.add(url)
                break

    return promising
