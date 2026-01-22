from bs4 import BeautifulSoup
import re
import extract_from_html_zips as efhz
import unicodedata
from profusion import Bloom
from myutils import unaccent

# Funkce pro extrakci emailu z HTML
def extract_address_from_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    text = soup.get_text(separator=" ")

    # Split using re.split
    words = re.split(r'[;,\s]+', text)
    
    bfilter_streets = Bloom(path="be_address_streets.bloom.dat")
    bfilter_muni = Bloom(path="be_address_municipalities.bloom.dat")
    bfilter_posts = Bloom(path="be_address_post_codes.bloom.dat")
    # extra hodnoty jsem postupne doplnil abych narovnal chovani bloom filteru ktery je nespravne vyhodnoti
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
        # analyza termu    
        term = unaccent(w.upper())    
            
        if len(term) > 0:        
            if term in extra_accept_terms:
                filtered_words.append(term)
                filtered_tags.append('EXTRA')                
                found = found + 1            
            elif term in extra_skip_terms:
                # skip 
                found = found + 0
            elif term in extra_split_terms:
                # spatny slovo reset!
                filtered_words = []
                filtered_tags = []
                found = 0
                accept_err = 0
                num_counter = 0
            elif term in bfilter_posts:
                filtered_words.append(term)
                filtered_tags.append('POST_CODE')                    
                found = found + 1
                num_counter = num_counter + 1
            elif term in bfilter_muni:
                filtered_words.append(term)
                filtered_tags.append('MUNICIPALITY')                
                found = found + 1
                num_counter = 0
            elif term in bfilter_streets:
                filtered_words.append(term)
                filtered_tags.append('STREET')                
                found = found + 1
                num_counter = 0
            elif re.search("^[0-9.()/-]{9,20}", term):
                # asi jsem narazil na telefon! reset
                filtered_words = []
                filtered_tags = []
                found = 0
                accept_err = 0
                num_counter = 0
            elif re.search("^[0-9]+[/-]?[0-9]*[a-zA-Z]?$", term):
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
            # 4 cisla za sebou to uz adresa nebude! reset
            filtered_words = []
            filtered_tags = []
            found = 0
            accept_err = 0
            num_counter = 0
            
        #print(f"{term}:{filtered_words};{filtered_tags};{found}")    
        if found >= 4:            
            if 'POST_CODE' in filtered_tags and 'MUNICIPALITY' in filtered_tags and 'NUMBER' in filtered_tags:    
                # tohle by mohla byt adresa
                address = ' '.join(filtered_words)
                addresses.append(address)
                #print(f"ADDRESS!!! {address}")
                # reset
                filtered_words = []
                filtered_tags = []
                found = 0
                accept_err = 0
                num_counter = 0
            elif found >= 10:
                filtered_words = filtered_words[3:]
                filtered_tags = filtered_tags[3:]
                found = found - 3

    # unique values only
    return ';;;'.join(list(set(addresses)))

####
efhz.crawl_zips_dir = '/mnt/emc/Import/be/new/WebGraderSnappyExport'
efhz.out_dir = '/mnt/emc/Import/be/new/WebGraderSnappyExport/results-scan-be-addresses'
efhz.parser_funct = extract_address_from_html

efhz.parallel_process_zip_files()

