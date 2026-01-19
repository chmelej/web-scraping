from bs4 import BeautifulSoup
import re
import extract_from_html_zips as efhz

# Funkce pro extrakci emailu z HTML
def extract_emails_from_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    text = soup.get_text(separator=" ")
    # Najdi všechny emaily pomocí regexu
    emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text) 
    return ';'.join(emails)

efhz.out_dir = '/mnt/emc/Import/be/new/WebGraderSnappyExport/results-scan-emails'
efhz.crawl_zips_dir = '/mnt/emc/Import/be/new/WebGraderSnappyExport'
efhz.parser_funct = extract_emails_from_html

efhz.parallel_process_zip_files()
