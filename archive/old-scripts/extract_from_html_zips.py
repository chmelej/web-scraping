from multiprocessing import Pool, cpu_count
from pathlib import Path
import csv
import os
import zipfile

out_dir = '/home/dev-jupyter/notebooks/data/results-scan-emails'
crawl_zips_dir = '/home/dev-jupyter/notebooks/data/zip-sample'
parser_funct = print


def extract_data_from_zip(parser_funct, zip_file, file_name):
    """
    Extrahuje text z HTML souboru v ZIP archivu.
    """        
    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
        with zip_ref.open(file_name) as file:
            try:
                content = file.read().decode('utf-8')                  # Čte obsah souboru
                content = parser_funct(content)          # bezpecne provede transformaci
            except:
                content = ""
            return file_name, content
    

def process_htmls_in_zip_file(zip_file):
    """
    Zpracovává jeden ZIP soubor: extrahuje text z HTML souborů.
    """
    print(f"process_htmls_in_zip_file {zip_file}\n")
    extracted_texts = []
    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
        html_files = [file for file in zip_ref.namelist() if file.endswith('.html')]        
        for file_name in html_files:            
            file_name, content = extract_data_from_zip(parser_funct, zip_file, file_name)
            if (content):
                extracted_texts.append((file_name, content))  # Ukládá název a vysledek parsovani
                
    
    out_file_name = Path(zip_file).stem             
    with open(f"{out_dir}/{out_file_name}_output.csv", "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerows(extracted_texts)                
    return extracted_texts


def parallel_process_zip_files():
    """
    Paralelně zpracovává seznam ZIP souborů.
    """
    print("Scan for ZIPs.")
    zip_files = [] # sem si nactu nazvy ZIP souboru 
    for subdir, dirs, files in os.walk(crawl_zips_dir):
        for file in files:
            if file.endswith(".zip"):  # Kontrola, zda je to zip soubor
                zip_files.append(f"{subdir}/{file}")
                
    print("Process zip data.")
    # Vytvoření procesního poolu
    with Pool(cpu_count()) as pool:
        results = pool.map(process_htmls_in_zip_file, zip_files)    
    return results



