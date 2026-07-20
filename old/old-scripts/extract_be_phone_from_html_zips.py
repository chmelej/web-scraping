from bs4 import BeautifulSoup
import re
import extract_from_html_zips as efhz

# Funkce pro extrakci Belgickych tel. cisel z HTML
def extract_belgian_phone_numbers(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    text = soup.get_text(separator=" ")

    # Regulární výraz pro belgická čísla (pevná i mobilní)
    phone_pattern = re.compile(r'''
        (?:
            0032|\+32|(?<!0)0    # Mezinárodní nebo národní prefix            
        )
        [\s\-\.]?              # Oddělovače
        (?:
            [1-9][\s\-\.]?[0-9]             # Města (např. 02, 03, 09, atd.)
            |
            4[5-9][0-9]            # Mobilní prefixy (např. 0470–0499)
        )
        (?:[\s\-\.]*\d){6,8}       # Zbytek čísel, s možnými oddělovači
    ''', re.VERBOSE)

    matches = phone_pattern.findall(text)
    # Pro kontrolu: odstraníme mezery a spojíme čísla do jednotného tvaru
    cleaned = [normalize_belgian_number(num) for num in matches]
    return ';'.join(cleaned)

def normalize_belgian_number(number):
    # Odstranit mezery, pomlčky, tečky
    clean = re.sub(r'[\s\-.]', '', number)

    # Normalizace prefixu
    if clean.startswith('+32'):
        clean = '0032' + clean[3:]
    elif clean.startswith('0032'):
        pass  # už OK
    elif clean.startswith('0'):
        clean = '0032' + clean[1:]
    else:
        return None  # neplatné číslo pro BE

    return clean

efhz.crawl_zips_dir = '/mnt/emc/Import/be/new/WebGraderSnappyExport'
efhz.out_dir = '/mnt/emc/Import/be/new/WebGraderSnappyExport/results-scan-be-phones'
efhz.parser_funct = extract_belgian_phone_numbers

efhz.parallel_process_zip_files()

