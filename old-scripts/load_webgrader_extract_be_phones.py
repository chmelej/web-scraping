import pandas as pd
import os
from sqlalchemy import create_engine, text
from myutils import load_properties

extract_phone_csv_directory = '/mnt/emc/Import/be/new/WebGraderSnappyExport/results-scan-be-phones'

config = load_properties('config.properties')
engine = create_engine(f"postgresql+psycopg2://{config['username']}:{config['password']}@{config['hostname']}:5432/{config['dbname']}")

def load_cvs_into_webgrader_extract_phone(file_name):
    print(file_name)
    # Načtení CSV bez hlavičky
    columns = ["html_file_name", "contact_value"]
    df = pd.read_csv(file_name, sep=',',header=None, names=columns)
    # Rozděl sloupec phones podle středníku a vytvoř seznamy
    df["contact_value"] = df["contact_value"].str.split(";")
    # Rozkopíruj řádky pro každé telefonní číslo
    df = df.explode("contact_value")
    # (Volitelné) oříznout mezery nebo očistit
    df["contact_value"] = df["contact_value"].str.strip()
    # kazdy radek je unikatni
    df = df.drop_duplicates()
    df.to_sql("webgrader_extract_phone", engine, if_exists="append", index=False)

with engine.begin() as conn:
    conn.execute(text("truncate table webgrader_extract_phone"))
    conn.commit()

print("Scan for CSVs.")
for subdir, dirs, files in os.walk(extract_phone_csv_directory):
        for file in files:
            if file.endswith(".csv"):  # Kontrola, zda je to zip soubor
                load_cvs_into_webgrader_extract_phone(f"{subdir}/{file}") 

