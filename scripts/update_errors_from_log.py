import re
import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from src.utils.db import get_db_connection, get_cursor

def parse_and_update(log_file_path):
    print(f"Reading log file: {log_file_path}")
    
    # Patterns from the Perl script
    # (Regex, Error Code, URL Group Index)
    patterns = [
        (re.compile(r"Request to (http\S+)\s+failed and reached maximum retries"), "max_retries", 1),
        (re.compile(r"request to (http\S+)\s+due to: Page.goto: net::ERR_CERT_COMMON_NAME_INVALID"), "ERR_CERT_COMMON_NAME_INVALID", 1),
        (re.compile(r"request to (http\S+)\s+due to: Page.goto: net::ERR_SSL_VERSION_OR_CIPHER_MISMATCH"), "ERR_SSL_VERSION_OR_CIPHER_MISMATCH", 1),
        (re.compile(r"request to (http\S+)\s+due to: Page.goto: net::ERR_NAME_NOT_RESOLVED"), "ERR_NAME_NOT_RESOLVED", 1),
        (re.compile(r"request to (http\S+)\s+due to: Page.goto: net::ERR_SSL_PROTOCOL_ERROR"), "ERR_SSL_PROTOCOL_ERROR", 1),
        (re.compile(r"request to (http\S+)\s+due to: Page.goto: net::ERR_CONNECTION_RESET"), "ERR_CONNECTION_RESET", 1),
        (re.compile(r"request to (http\S+)\s+due to: Page.goto: net::ERR_CERT_DATE_INVALID"), "ERR_CERT_DATE_INVALID", 1),
        # Perl: /Timeout \d+ms exceeded...Call log:..  - navigating to "(\S+)"/
        # Using .* to match '...' and '..' more loosely
        (re.compile(r'Timeout \d+ms exceeded.*Call log:.* - navigating to "(\S+)"'), "TimeoutExceeded", 1),
    ]
    
    updates = {} # URL -> Error mapping

    with open(log_file_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            for pattern, error_code, url_group in patterns:
                match = pattern.search(line)
                if match:
                    url = match.group(url_group).strip()
                    # Perl logic: $url =~ s|/$||; (commented out in Perl, but maybe useful? Keeping raw for now as per Perl script active code)
                    updates[url] = error_code
                    break # Stop checking other patterns for this line

    print(f"Found {len(updates)} unique URLs with errors.")
    
    if not updates:
        return

    conn = get_db_connection()
    try:
        with get_cursor(conn) as cur:
            count = 0
            for url, error in updates.items():
                cur.execute("""
                    UPDATE scr_scrape_queue 
                    SET last_error = %s 
                    WHERE url = %s
                """, (error, url))
                
                # If exact match fails, try prefix match (from original script logic, seemingly useful)
                if cur.rowcount == 0:
                     cur.execute("""
                        UPDATE scr_scrape_queue 
                        SET last_error = %s 
                        WHERE url LIKE %s || '%%'
                    """, (error, url))
                
                count += cur.rowcount
            
            conn.commit()
            print(f"Updated {count} rows in database.")
    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/update_errors_from_log.py <path_to_log_file>")
        sys.exit(1)
    
    log_file = sys.argv[1]
    parse_and_update(log_file)
