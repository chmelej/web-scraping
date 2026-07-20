import pandas as pd
import os
from sqlalchemy import create_engine, text
from myutils import load_properties

extract_address_csv_directory = '/mnt/emc/Import/be/new/WebGraderSnappyExport/results-scan-be-addresses'

config = load_properties('config.properties')
engine = create_engine(f"postgresql+psycopg2://{config['username']}:{config['password']}@{config['hostname']}:5432/{config['dbname']}")

def load_cvs_into_webgrader_extract_address(file_name):
    print(file_name)
    # Načtení CSV bez hlavičky
    columns = ["html_file_name", "address_in_line"]
    df = pd.read_csv(file_name, sep=',',header=None, names=columns)
    # Rozděl sloupec phones podle středníku a vytvoř seznamy
    df["address_in_line"] = df["address_in_line"].str.split(";;;")
    # Rozkopíruj řádky pro každé telefonní číslo
    df = df.explode("address_in_line")
    # (Volitelné) oříznout mezery nebo očistit
    df["address_in_line"] = df["address_in_line"].str.strip()
    # kazdy radek je unikatni
    df = df.drop_duplicates()
    df.to_sql("webgrader_extract_address", engine, if_exists="append", index=False)

with engine.begin() as conn:
    conn.execute(text("truncate table webgrader_extract_address"))
    conn.commit()

print("Scan for CSVs.")
for subdir, dirs, files in os.walk(extract_address_csv_directory):
        for file in files:
            if file.endswith(".csv"):  # Kontrola, zda je to zip soubor
                load_cvs_into_webgrader_extract_address(f"{subdir}/{file}") 

