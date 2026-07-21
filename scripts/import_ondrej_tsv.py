#!/usr/bin/env python3
import os
import sys
import csv
import json
import re
from datetime import datetime

# Ensure src module can be imported
sys.path.append(os.getcwd())

from src.utils.db import get_db_connection, get_cursor
from src.utils.logging_config import setup_logging
from config.settings import LOG_DIR

def encode_url_key(url: str) -> str:
    """
    Encodes a URL or domain string into a clean normalized key for matching with zip filenames.
    Example: 'https://www.example-domain.be/path' -> 'example-domain-be-path'
    """
    if not url:
        return ""
    # Strip scheme http:// or https://
    clean = re.sub(r'^(https?://)', '', url, flags=re.I)
    # Replace non-alphanumeric chars with hyphen
    clean = re.sub(r'[^a-zA-Z0-9]+', '-', clean).strip('-').lower()
    return clean

def parse_int(val, default=None):
    if not val:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default

def parse_iso_datetime(val_str):
    if not val_str:
        return None
    try:
        clean_str = val_str.replace('Z', '+00:00')
        return datetime.fromisoformat(clean_str)
    except Exception:
        return None

def import_tsv(tsv_filepath: str, batch_size=1000):
    logger = setup_logging('import_tsv', f"{LOG_DIR}/import_tsv.log")
    if not os.path.exists(tsv_filepath):
        logger.error(f"File not found: {tsv_filepath}")
        sys.exit(1)

    logger.info(f"Starting import of TSV metadata from: {tsv_filepath}")

    conn = get_db_connection()
    total_imported = 0

    try:
        with open(tsv_filepath, 'r', encoding='utf-8-sig', errors='ignore') as f:
            reader = csv.DictReader(f, delimiter='\t')
            batch = []

            for row in reader:
                sf_url = row.get('Sourcefile Url', '').strip()
                sys_url = row.get('System Url', '').strip()

                enc_sf = encode_url_key(sf_url)
                enc_sys = encode_url_key(sys_url)
                version_dt = parse_iso_datetime(row.get('Version'))
                state = row.get('State')
                status_code = parse_int(row.get('Redirection Checker  Status Code'))
                redirect_as = row.get('Redirection Checker  Redirect As')

                batch.append((
                    sf_url,
                    enc_sf,
                    sys_url,
                    enc_sys,
                    version_dt,
                    state,
                    status_code,
                    redirect_as,
                    json.dumps(row)
                ))

                if len(batch) >= batch_size:
                    with get_cursor(conn, dict_cursor=False) as cur:
                        cur.executemany("""
                            INSERT INTO tmp_ondrej_metadata
                            (sourcefile_url, encoded_sourcefile, system_url, encoded_system_url,
                             version, state, status_code, redirect_as, raw_data)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, batch)
                    conn.commit()
                    total_imported += len(batch)
                    logger.info(f"Imported {total_imported} metadata rows...")
                    batch.clear()

            if batch:
                with get_cursor(conn, dict_cursor=False) as cur:
                    cur.executemany("""
                        INSERT INTO tmp_ondrej_metadata
                        (sourcefile_url, encoded_sourcefile, system_url, encoded_system_url,
                         version, state, status_code, redirect_as, raw_data)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, batch)
                conn.commit()
                total_imported += len(batch)
                batch.clear()

        logger.info(f"Finished TSV import! Total rows inserted: {total_imported}")

    except Exception as e:
        logger.error(f"Error importing TSV: {e}", exc_info=True)
    finally:
        conn.close()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python import_ondrej_tsv.py <tsv_filepath>")
        sys.exit(1)

    tsv_file = sys.argv[1]
    import_tsv(tsv_file)
