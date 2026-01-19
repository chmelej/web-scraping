import pandas as pd
from sqlalchemy import create_engine
from myutils import load_properties

config = load_properties('config.properties')

df = pd.read_csv("/mnt/emc/Import/be/new/WebGraderSnappyExport/FileIndex-20231123-BE-BT199.tsv", sep='\t')

engine = create_engine(f"postgresql+psycopg2://{config['username']}:{config['password']}@{config['hostname']}:5432/{config['dbname']}")

df = df.rename(columns={
    "DateCheckedUtc": "checked_date_utc",
    "ZipDir": "zip_dir",
    "CheckState": "check_state",
    "FinalUrl": "final_url",
    "HtmlFileName": "html_file_name"
})

df.to_sql("webgrader_file_index", engine, if_exists="append", index=False)
#print(df)

