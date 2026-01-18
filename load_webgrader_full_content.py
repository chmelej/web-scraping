# load_webgrader_full_content.py
import os
import zipfile
from typing import Tuple, List

import pandas as pd
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text
from myutils import load_properties
import re

# Root directory containing ZIP files with HTML content
crawl_zips_dir = '/mnt/emc/Import/be/new/WebGraderSnappyExport'

# Batch size for DB insert to control memory usage
BATCH_SIZE = 5000

# Precompiled regex to strip surrogate code points (U+D800–U+DFFF)
_SURROGATE_RE = re.compile(r'[\ud800-\udfff]')


def sanitize_string(s: str) -> str:
    """Remove characters that PostgreSQL/psycopg2 can't encode (surrogates, NULs)."""
    if s is None:
        return s
    # Remove NUL characters first
    s = s.replace("\x00", "")
    # Remove surrogate code points
    s = _SURROGATE_RE.sub("", s)
    return s


def decode_best_effort(raw_bytes: bytes) -> str:
    """Decode bytes to string trying UTF-8 first, with graceful fallback."""
    for enc in ("utf-8", "latin-1"):
        try:
            s = raw_bytes.decode(enc)
            # Replace NUL characters which are not allowed by PostgreSQL text types
            return sanitize_string(s)
        except UnicodeDecodeError:
            continue
    # As a last resort, ignore errors
    return sanitize_string(raw_bytes.decode("utf-8", errors="ignore"))


def extract_html_and_text(html_content: str) -> Tuple[str, str]:
    """Return original HTML and extracted plain text."""
    soup = BeautifulSoup(html_content, "html.parser")
    text_content = soup.get_text(separator=" ", strip=True)
    return html_content, text_content


def iter_zip_html_records(zip_path: str) -> List[dict]:
    """Yield records from a single ZIP with HTML files."""
    records = []
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for member in zf.namelist():
            lower = member.lower()
            if not (lower.endswith('.html') or lower.endswith('.htm')):
                continue
            try:
                with zf.open(member) as f:
                    raw = f.read()
                html = decode_best_effort(raw)
                html_content, text_content = extract_html_and_text(html)
                records.append({
                    "html_file_name": member,
                    "html_content": html_content,
                    "text_content": text_content,
                })
            except Exception:
                # Skip problematic entries but keep processing others
                continue
    return records


def main():
    # Configure DB connection
    config = load_properties('config.properties')
    engine = create_engine(
        f"postgresql+psycopg2://{config['username']}:{config['password']}@{config['hostname']}:5432/{config['dbname']}"
    )

    # Prepare destination table
    with engine.begin() as conn:
        conn.execute(text("truncate table webgrader_full_content"))

    total_inserted = 0
    batch: List[dict] = []

    print("Scan for ZIPs.")
    for subdir, dirs, files in os.walk(crawl_zips_dir):
        for file in files:
            if not file.endswith(".zip"):
                continue
            zip_path = os.path.join(subdir, file)
            print(f"Processing ZIP: {zip_path}")

            # Collect records from this ZIP
            records = iter_zip_html_records(zip_path)
            if not records:
                continue

            # Batch and insert
            for rec in records:
                batch.append(rec)
                if len(batch) >= BATCH_SIZE:
                    df = pd.DataFrame(batch)
                    df.to_sql("webgrader_full_content", engine, if_exists="append", index=False, method="multi")
                    total_inserted += len(batch)
                    print(f"Inserted {total_inserted} rows so far...")
                    batch.clear()

    # Flush remaining records
    if batch:
        df = pd.DataFrame(batch)
        df.to_sql("webgrader_full_content", engine, if_exists="append", index=False, method="multi")
        total_inserted += len(batch)
        batch.clear()

    print(f"Done. Total inserted rows: {total_inserted}")


if __name__ == "__main__":
    main()