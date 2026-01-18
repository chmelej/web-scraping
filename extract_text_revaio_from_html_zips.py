from bs4 import BeautifulSoup
import re
import extract_from_html_zips as efhz

# Funkce pro extrakci odkazu na revaio z HTML
def extract_revaio_links_from_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    text = soup.get_text(separator=" ")
    # Najdi všechny emaily pomocí regexu
    emails = re.findall(r'(?i)revaio', text) 
    return ';'.join(emails)
    
efhz.out_dir = '/mnt/emc/Import/be/new/WebGraderSnappyExport/results-scan-revaio'
efhz.crawl_zips_dir = '/mnt/emc/Import/be/new/WebGraderSnappyExport'
efhz.parser_funct = extract_revaio_links_from_html

efhz.parallel_process_zip_files()
