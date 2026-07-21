#!/usr/bin/env python3
import os
import sys
import re
import shutil
import zipfile
from datetime import datetime

# Ensure src module can be imported
sys.path.append(os.getcwd())

from src.utils.db import get_db_connection, get_cursor
from src.utils.storage import save_raw_html
from src.utils.logging_config import setup_logging
from config.settings import LOG_DIR

def encode_url_key(url: str) -> str:
    """
    Encodes a URL or domain string into a clean normalized key for matching with zip filenames.
    """
    if not url:
        return ""
    clean = re.sub(r'^(https?://)', '', url, flags=re.I)
    clean = re.sub(r'[^a-zA-Z0-9]+', '-', clean).strip('-').lower()
    return clean

def decode_html_bytes(raw_bytes: bytes) -> str:
    """Best effort decoding of HTML content bytes."""
    for enc in ("utf-8", "latin-1"):
        try:
            return raw_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="ignore")

def parse_filename_info(filename: str):
    """
    Parses zip HTML filename e.g. 'http-alphacars-be-20231113103908.html'
    Returns (scheme, encoded_key, timestamp_dt)
    """
    base = os.path.basename(filename)
    m = re.match(r'^(http|https|ftp)?-?(.*?)-(\d{14})\.html$', base, re.I)
    if not m:
        # Fallback regex without scheme prefix
        m2 = re.match(r'^(.*?)-(\d{14})\.html$', base, re.I)
        if not m2:
            return "http", encode_url_key(base.replace('.html', '')), datetime.now()
        key_part, ts_part = m2.groups()
        scheme = "http"
    else:
        scheme_part, key_part, ts_part = m.groups()
        scheme = scheme_part.lower() if scheme_part else "http"

    try:
        ts_dt = datetime.strptime(ts_part, "%Y%m%d%H%M%S")
    except ValueError:
        ts_dt = datetime.now()

    return scheme, encode_url_key(key_part), ts_dt

def reconstruct_url_from_filename(filename: str) -> str:
    """
    Reconstructs fallback URL from filename if metadata not found in DB.
    e.g. 'http-alphacars-be-20231113103908.html' -> 'http://alphacars.be'
    """
    scheme, key, _ = parse_filename_info(filename)
    base = os.path.basename(filename)
    m = re.match(r'^(?:http|https)?-?(.*?)-\d{14}\.html$', base, re.I)
    raw_domain = m.group(1) if m else key
    
    # Replace single dashes before common TLDs or convert last dash to dot
    # e.g. alphacars-be -> alphacars.be
    if '-' in raw_domain:
        parts = raw_domain.rsplit('-', 1)
        domain = f"{parts[0]}.{parts[1]}"
    else:
        domain = raw_domain

    return f"{scheme}://{domain}"

def process_single_zip(zip_path: str, conn, logger):
    logger.info(f"Processing ZIP file: {zip_path}")
    zip_name = os.path.basename(zip_path)
    total_files = 0
    matched_meta = 0

    with zipfile.ZipFile(zip_path, 'r') as zf:
        members = [m for m in zf.namelist() if m.lower().endswith('.html') or m.lower().endswith('.htm')]
        total_files = len(members)

        for member in members:
            scheme, enc_key, scraped_at = parse_filename_info(member)

            # Lookup metadata in DB
            metadata = None
            with get_cursor(conn) as cur:
                cur.execute("""
                    SELECT sourcefile_url, system_url, status_code, redirect_as
                    FROM tmp_ondrej_metadata
                    WHERE encoded_sourcefile = %s OR encoded_system_url = %s
                    LIMIT 1
                """, (enc_key, enc_key))
                metadata = cur.fetchone()

            if metadata:
                matched_meta += 1
                url = metadata.get('system_url') or metadata.get('sourcefile_url') or reconstruct_url_from_filename(member)
                redirect_as = metadata.get('redirect_as')
                final_url = redirect_as if redirect_as else url
                status_code = metadata.get('status_code') or 200
            else:
                url = reconstruct_url_from_filename(member)
                final_url = url
                status_code = 200

            # Read HTML content
            raw_bytes = zf.read(member)
            html_str = decode_html_bytes(raw_bytes)

            with get_cursor(conn, dict_cursor=False) as cur:
                # 1. Insert or get queue_id
                cur.execute("""
                    INSERT INTO scr_scrape_queue (url, status, added_at)
                    VALUES (%s, 'completed', %s)
                    ON CONFLICT (url) DO UPDATE SET status = 'completed'
                    RETURNING queue_id
                """, (url, scraped_at))
                queue_id = cur.fetchone()[0]

                # 2. Insert scr_scrape_results record
                redirected_from = url if final_url != url else None
                cur.execute("""
                    INSERT INTO scr_scrape_results
                    (queue_id, url, html, html_path, html_size, status_code,
                     redirected_from, scraped_at, processing_status)
                    VALUES (%s, %s, NULL, NULL, 0, %s, %s, %s, 'new')
                    RETURNING result_id
                """, (queue_id, final_url, status_code, redirected_from, scraped_at))
                result_id = cur.fetchone()[0]

                # 3. Save raw HTML to disk/NFS
                html_path, html_size = save_raw_html(final_url, html_str, result_id=result_id)

                # 4. Update html_path and html_size
                cur.execute("""
                    UPDATE scr_scrape_results
                    SET html_path = %s, html_size = %s
                    WHERE result_id = %s
                """, (html_path, html_size, result_id))

            conn.commit()

    logger.info(f"Completed ZIP {zip_name}: {total_files} HTMLs processed ({matched_meta} matched TSV metadata).")

    # Move ZIP to done/ folder
    done_dir = os.path.join(os.path.dirname(zip_path), 'done')
    os.makedirs(done_dir, exist_ok=True)
    done_path = os.path.join(done_dir, zip_name)
    shutil.move(zip_path, done_path)
    logger.info(f"Moved {zip_name} -> {done_path}")

def import_zips(target_path: str):
    logger = setup_logging('import_zips', f"{LOG_DIR}/import_zips.log")
    if not os.path.exists(target_path):
        logger.error(f"Target path not found: {target_path}")
        sys.exit(1)

    conn = get_db_connection()
    try:
        if os.path.isfile(target_path) and target_path.endswith('.zip'):
            process_single_zip(target_path, conn, logger)
        elif os.path.isdir(target_path):
            zip_files = []
            for root, dirs, files in os.walk(target_path):
                if 'done' in root.split(os.sep):
                    continue
                for file in files:
                    if file.endswith('.zip'):
                        zip_files.append(os.path.join(root, file))

            logger.info(f"Found {len(zip_files)} ZIP files to import in {target_path}")
            for zfile in zip_files:
                process_single_zip(zfile, conn, logger)
        else:
            logger.error(f"Invalid target: {target_path} (must be a .zip file or directory with zips)")
    finally:
        conn.close()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python import_ondrej_zips.py <zip_file_or_dir>")
        sys.exit(1)

    import_zips(sys.argv[1])
