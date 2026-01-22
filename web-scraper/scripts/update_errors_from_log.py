import re
import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from src.utils.db import get_db_connection, get_cursor

def parse_and_update(log_file_path):
    print(f"Reading log file: {log_file_path}")
    
    # Regex for WARN retry lines
    warn_pattern = re.compile(r"Retrying request to (https?://\S+) due to: (.*)")
    # Regex for ERROR failure lines (indicates start of error detail on next lines)
    error_pattern = re.compile(r"ERROR\s+Request to (https?://\S+) failed")
    
    updates = {} # URL -> Error mapping
    last_error_url = None # State for capturing multi-line errors after ERROR log

    with open(log_file_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            # 1. Check for ERROR block start
            error_match = error_pattern.search(line)
            if error_match:
                last_error_url = error_match.group(1).strip()
                # Initialize buffer/counter to look for the real error in next few lines
                lookahead_lines = 0
                continue
            
            # 2. If inside ERROR block, look for exception details
            if last_error_url:
                lookahead_lines += 1
                # If we hit a new log line or looked too far, stop
                if lookahead_lines > 10 or (line.startswith('[') and ('INFO' in line or 'WARN' in line or 'ERROR' in line)):
                    last_error_url = None
                else:
                    # Look for high-quality error markers
                    is_real_error = any(x in line for x in ["Error:", "Exception:", "TimeoutError", "net::ERR_"])
                    is_garbage = 'File "' in line or "File '" in line or "^^^^" in line
                    
                    if is_real_error and not is_garbage:
                        updates[last_error_url] = line
                        last_error_url = None # Found it, reset
                        continue
            
            # 3. Check for WARN retry lines (fallback)
            warn_match = warn_pattern.search(line)
            if warn_match:
                url = warn_match.group(1).strip()
                raw_error = warn_match.group(2).strip()
                
                # Filter out python tracebacks and garbage patterns
                if 'File "' in raw_error or "File '" in raw_error or "^^^^" in raw_error or raw_error.startswith(". ,"):
                    continue
                    
                updates[url] = raw_error

    print(f"Found {len(updates)} unique URLs with errors.")
    
    # helper to clean error string
    def clean_error(error_str):
        error_str = error_str.strip()
        
        # Standardize known high-priority errors immediately
        if "ERR_NAME_NOT_RESOLVED" in error_str: return "ERR_NAME_NOT_RESOLVED"
        if "ERR_CONNECTION_RESET" in error_str: return "ERR_CONNECTION_RESET"
        if "ERR_CERT_AUTHORITY_INVALID" in error_str: return "ERR_CERT_AUTHORITY_INVALID"
        if "ERR_CERT_COMMON_NAME_INVALID" in error_str: return "ERR_CERT_COMMON_NAME_INVALID"
        if "ERR_CONNECTION_REFUSED" in error_str: return "ERR_CONNECTION_REFUSED"
        if "ERR_TIMED_OUT" in error_str: return "ERR_TIMED_OUT"
        if "ERR_EMPTY_RESPONSE" in error_str: return "ERR_EMPTY_RESPONSE"
        if "ERR_SSL_PROTOCOL_ERROR" in error_str: return "ERR_SSL_PROTOCOL_ERROR"
        
        # Strip prefixes repeatedly
        prefixes = [
            "playwright._impl._errors.Error: ",
            "crawlee.errors.HttpClientStatusCodeError: ",
            "crawlee.errors.HttpStatusCodeError: ",
            "crawlee.errors.SessionError: ",
            "Page.goto: ",
            "Page.query_selector: ",
            "Error status code returned (status code: ",
            "Client error status code returned (status code: ",
            ". , "
        ]
        
        while True:
            changed = False
            for p in prefixes:
                if error_str.startswith(p):
                    error_str = error_str[len(p):].strip()
                    changed = True
            if not changed:
                break
        
        # Split repeat URL
        if " at http" in error_str:
            error_str = error_str.split(" at http")[0]
        
        error_str = error_str.strip().rstrip(')').rstrip('(').rstrip('.').strip()
        
        # Timeout handling
        if "Timeout" in error_str and "exceeded" in error_str:
            tm = re.search(r"Timeout \d+ms exceeded", error_str)
            if tm: return tm.group(0)
            return "Timeout exceeded"
        
        # Status codes
        if "status code: " in error_str:
            sc_match = re.search(r"status code: (\d+)", error_str)
            if sc_match: return f"HTTP {sc_match.group(1)}"
        
        return error_str

    if not updates:
        return

    conn = get_db_connection()
    try:
        with get_cursor(conn) as cur:
            count = 0
            for url, raw_error in updates.items():
                error = clean_error(raw_error)
                
                # Skip empty
                if not error: continue

                # Truncate to fit in varchar(200)
                if len(error) > 200:
                    error = error[:197] + "..."

                cur.execute("""
                    UPDATE scr_scrape_queue 
                    SET last_error = %s 
                    WHERE url = %s
                """, (error, url))
                
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
