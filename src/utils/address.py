import re
import unicodedata
from bs4 import BeautifulSoup
from profusion import Bloom
import os

# Paths to bloom filters
# Assuming they are in the project root or a known location
BLOOM_DIR = os.getenv('BLOOM_DIR', '.')

def unaccent(text):
    """Odstraní diakritiku"""
    nfkd_form = unicodedata.normalize('NFKD', text)
    ascii_text = ''.join([c for c in nfkd_form if not unicodedata.combining(c)])
    return ascii_text.encode('ascii', 'ignore').decode('ascii')

class AddressExtractor:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AddressExtractor, cls).__new__(cls)
            cls._instance._load_filters()
        return cls._instance

    def _load_filters(self):
        try:
            self.bfilter_streets = Bloom(path=os.path.join(BLOOM_DIR, "be_address_streets.bloom.dat"))
            self.bfilter_muni = Bloom(path=os.path.join(BLOOM_DIR, "be_address_municipalities.bloom.dat"))
            self.bfilter_posts = Bloom(path=os.path.join(BLOOM_DIR, "be_address_post_codes.bloom.dat"))
            self.loaded = True
        except Exception as e:
            print(f"Warning: Could not load address bloom filters: {e}")
            self.loaded = False

    def extract_addresses(self, text):
        if not self.loaded:
            return []

        # Split using re.split
        words = re.split(r'[;,\s]+', text)
        
        extra_skip_terms = ['BELGIUM', 'BELGIE','-', ',','DU','DE','BUSINESS','CENTER']
        extra_accept_terms = ['ROUTE','RUE','AVENUE']
        extra_split_terms = ['ADRESSE']
        
        addresses = []
        filtered_words = []
        filtered_tags = []
        found = 0
        accept_err = 0
        num_counter = 0
        
        for w in words:                        
            term = unaccent(w.upper())    
                
            if len(term) > 0:        
                if term in extra_accept_terms:
                    filtered_words.append(term)
                    filtered_tags.append('EXTRA')                
                    found = found + 1            
                elif term in extra_skip_terms:
                    # skip 
                    pass
                elif term in extra_split_terms:
                    # reset
                    filtered_words = []
                    filtered_tags = []
                    found = 0
                    accept_err = 0
                    num_counter = 0
                elif term in self.bfilter_posts:
                    filtered_words.append(term)
                    filtered_tags.append('POST_CODE')                    
                    found = found + 1
                    num_counter = num_counter + 1
                elif term in self.bfilter_muni:
                    filtered_words.append(term)
                    filtered_tags.append('MUNICIPALITY')                
                    found = found + 1
                    num_counter = 0
                elif term in self.bfilter_streets:
                    filtered_words.append(term)
                    filtered_tags.append('STREET')                
                    found = found + 1
                    num_counter = 0
                elif re.search(r"^[0-9.()/-]{9,20}", term):
                    # asi telefon! reset
                    filtered_words = []
                    filtered_tags = []
                    found = 0
                    accept_err = 0
                    num_counter = 0
                elif re.search(r"^[0-9]+[/-]?[0-9]*[a-zA-Z]?$", term):
                    filtered_words.append(term)
                    filtered_tags.append('NUMBER')                
                    found = found + 1        
                    num_counter = num_counter + 1
                else:
                    if accept_err == 0:
                        accept_err = 1
                    else:
                        # reset
                        filtered_words = []
                        filtered_tags = []
                        found = 0
                        accept_err = 0
                        num_counter = 0

            if num_counter > 3:
                # 4 cisla za sebou - reset
                filtered_words = []
                filtered_tags = []
                found = 0
                accept_err = 0
                num_counter = 0
                
            if found >= 4:            
                if 'POST_CODE' in filtered_tags and 'MUNICIPALITY' in filtered_tags and 'NUMBER' in filtered_tags:    
                    address = ' '.join(filtered_words)
                    addresses.append(address)
                    
                    filtered_words = []
                    filtered_tags = []
                    found = 0
                    accept_err = 0
                    num_counter = 0
                elif found >= 10:
                    filtered_words = filtered_words[3:]
                    filtered_tags = filtered_tags[3:]
                    found = found - 3

        return list(set(addresses))

def extract_addresses_from_text(text, language='be'):
    """Extract addresses from text using bloom filters"""
    # Allow Belgian languages and unknown/None
    belgian_langs = ['be', 'fr', 'nl', 'de', 'unknown', None]
    if language not in belgian_langs and language is not None:
        return []
    
    extractor = AddressExtractor()
    return extractor.extract_addresses(text)
