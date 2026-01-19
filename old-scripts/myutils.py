import unicodedata


def load_properties(path):
    config = {}
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
    return config

def unaccent(text):
    # Normalizuj do NFKD formy (rozdělí písmena a diakritiku)
    nfkd_form = unicodedata.normalize('NFKD', text)
    # Vezmi jen znaky, které nejsou diakritické značky (kategorie 'Mn')
    ascii_text = ''.join([c for c in nfkd_form if not unicodedata.combining(c)])
    # Převod na ASCII (volitelný krok navíc pro jistotu)
    return ascii_text.encode('ascii', 'ignore').decode('ascii')

