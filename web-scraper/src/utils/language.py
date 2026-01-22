from langdetect import detect_langs
from bs4 import BeautifulSoup

def detect_language(html):
    """
    Detekuje jazyk z HTML
    Returns: (language_code, confidence)
    """
    # Zkus HTML lang attribute
    soup = BeautifulSoup(html, 'lxml')
    html_tag = soup.find('html')
    if html_tag and html_tag.get('lang'):
        lang = html_tag.get('lang')[:2].lower()
        return lang, 0.99

    # Extract text
    text = soup.get_text(separator=' ', strip=True)
    text = ' '.join(text.split())[:10000]

    if len(text) < 50:
        return None, 0.0

    try:
        results = detect_langs(text)
        return results[0].lang, results[0].prob
    except:
        return None, 0.0
