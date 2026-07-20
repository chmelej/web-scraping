import glob
import os
import re
import sys
from collections import Counter

# Add src to path if needed
sys.path.append(os.getcwd())

# Define error classification rules (order matters: specific -> general)
ERROR_RULES = [
    ("DNS_NOT_RESOLVED", [
        re.compile(r"ERR_NAME_NOT_RESOLVED", re.I),
        re.compile(r"ERR_NAME_RESOLUTION_FAILED", re.I),
        re.compile(r"could not translate host name", re.I),
    ]),
    ("CONNECTION_REFUSED_OR_RESET", [
        re.compile(r"ERR_CONNECTION_REFUSED", re.I),
        re.compile(r"ERR_CONNECTION_RESET", re.I),
        re.compile(r"ERR_CONNECTION_CLOSED", re.I),
        re.compile(r"ERR_CONNECTION_TIMED_OUT", re.I),
        re.compile(r"ERR_CONNECTION_FAILED", re.I),
        re.compile(r"ERR_ADDRESS_UNREACHABLE", re.I),
        re.compile(r"ERR_EMPTY_RESPONSE", re.I),
        re.compile(r"ERR_HTTP2_PROTOCOL_ERROR", re.I),
        re.compile(r"ERR_ABORTED", re.I),
        re.compile(r"ERR_INVALID_REDIRECT", re.I),
    ]),
    ("SSL_CERT_ERROR", [
        re.compile(r"ERR_CERT_", re.I),
        re.compile(r"ERR_SSL_", re.I),
        re.compile(r"CERT_HAS_EXPIRED", re.I),
        re.compile(r"DEPTH_ZERO_SELF_SIGNED_CERT", re.I),
    ]),
    ("HTTP_403_BLOCKED", [
        re.compile(r"status code:? 403", re.I),
        re.compile(r"status code:? 401", re.I),
        re.compile(r"status code:? 429", re.I),
        re.compile(r"SessionError.*403", re.I),
        re.compile(r"SessionError.*401", re.I),
        re.compile(r"SessionError.*429", re.I),
        re.compile(r"ERR_TOO_MANY_REDIRECTS", re.I),
    ]),
    ("HTTP_404_NOT_FOUND", [
        re.compile(r"status code:? 404", re.I),
        re.compile(r"status code:? 410", re.I),
    ]),
    ("HTTP_OTHER_CLIENT_ERROR", [
        re.compile(r"status code:? 400", re.I),
        re.compile(r"status code:? 402", re.I),
        re.compile(r"status code:? 409", re.I),
        re.compile(r"status code:? 444", re.I),
    ]),
    ("FILE_DOWNLOAD_TRIGGERED", [
        re.compile(r"Download is starting", re.I),
    ]),
    ("BROWSER_TARGET_CLOSED", [
        re.compile(r"TargetClosedError", re.I),
        re.compile(r"Target page, context or browser has been closed", re.I),
    ]),
    ("DB_CONNECTION_ERROR", [
        re.compile(r"psycopg2\.connect", re.I),
        re.compile(r"get_db_connection", re.I),
    ]),
    ("HTTP_5XX_SERVER_ERROR", [
        re.compile(r"status code:? 5[0-9]{2}", re.I),
        re.compile(r"status code:? 520", re.I),
    ]),
    ("NAVIGATION_TIMEOUT", [
        re.compile(r"Timeout \d+ms exceeded", re.I),
        re.compile(r"Request handler timed out", re.I),
        re.compile(r"navigation_timeout", re.I),
    ]),
    ("EXECUTION_CONTEXT_DESTROYED", [
        re.compile(r"Execution context was destroyed", re.I),
    ]),
    ("BATCH_RECONCILED", [
        re.compile(r"Reconciled \d+ stuck items", re.I),
    ]),
    ("CRAWLEE_MAX_RETRIES_REACHED", [
        re.compile(r"failed and reached maximum retries", re.I),
    ]),
]

# Noise patterns to ignore (statistics tables, routine info logs, tracebacks of known errors)
NOISE_PATTERNS = [
    re.compile(r"^\s*│"),
    re.compile(r"^\s*┌"),
    re.compile(r"^\s*└"),
    re.compile(r"^\s*├"),
    re.compile(r"^\s*\^"),
    re.compile(r"INFO  Crawled"),
    re.compile(r"INFO  current_concurrency"),
    re.compile(r"INFO  Starting Crawlee Scraper"),
    re.compile(r"INFO  Fetched \d+ URLs"),
    re.compile(r"INFO  Starting batch execution"),
    re.compile(r"INFO - Processing"),
    re.compile(r"INFO - Finished processing"),
    re.compile(r"INFO - Redirect detected"),
    re.compile(r"INFO - Fetched \d+ URLs"),
    re.compile(r"INFO  Processing http"),
    re.compile(r"INFO  Finished processing http"),
    re.compile(r"INFO  Redirect detected"),
    re.compile(r"INFO  Final request statistics"),
    re.compile(r"INFO  Current request statistics"),
    re.compile(r"INFO  Error analysis"),
    re.compile(r"INFO  Waiting for remaining tasks"),
    re.compile(r"\[scraper\] INFO"),
    re.compile(r"self\._raise_for_error_status_code"),
    re.compile(r"raise rewrite_error"),
    re.compile(r"raise HttpClientStatusCodeError"),
    re.compile(r"raise SessionError"),
    re.compile(r"File \".*site-packages/playwright"),
    re.compile(r"File \".*site-packages/crawlee"),
    re.compile(r"File \".*src/workers/scraper\.py"),
    re.compile(r"File \"/usr/lib/python"),
    re.compile(r"async with self\._shared_navigation_timeouts"),
    re.compile(r"await self\._active_timeout"),
    re.compile(r"return await _wait"),
    re.compile(r"asyncio\.exceptions\.CancelledError"),
    re.compile(r"The above exception was the direct cause"),
    re.compile(r"TimeoutError$"),
    re.compile(r"Traceback \(most recent call last\):"),
    re.compile(r"result = await middleware_instance"),
    re.compile(r"self\.output_context = await"),
    re.compile(r"Call log:"),
    re.compile(r"- navigating to"),
    re.compile(r"return await self\._connection"),
    re.compile(r"response = await context\.page\.goto"),
    re.compile(r"await self\._impl_obj\.goto"),
    re.compile(r"return await self\._main_frame\.goto"),
    re.compile(r"await self\._channel\.send"),
    re.compile(r"\[asyncio\] ERROR Future exception was never retrieved"),
    re.compile(r"return await cb\(\)"),
    re.compile(r"done, _ = await asyncio\.wait"),
    re.compile(r"await waiter"),
    re.compile(r"raise TimeoutError from exc_val"),
    re.compile(r"await self\._run_request_handler"),
    re.compile(r"await self\._context_pipeline"),
    re.compile(r"self\._raise_for_session_blocked_status_code"),
    re.compile(r"raise HttpStatusCodeError"),
    re.compile(r"return await user_defined_handler"),
    re.compile(r"result_id = await loop\.run_in_executor"),
    re.compile(r"selector for selector in RETRY_CSS_SELECTORS"),
    re.compile(r"await self\._impl_obj\.query_selector"),
    re.compile(r"return await self\._main_frame\.query_selector"),
    re.compile(r"INFO - Starting batch execution"),
    re.compile(r"INFO - Starting Crawlee Scraper"),
    re.compile(r"INFO - Max runtime reached"),
    re.compile(r"File \"<frozen runpy>\""),
    re.compile(r"asyncio\.run\(scraper\.run\(\)\)"),
    re.compile(r"return runner\.run\(main\)"),
    re.compile(r"return self\._loop\.run_until_complete"),
    re.compile(r"return future\.result\(\)"),
    re.compile(r"result = self\.fn"),
    re.compile(r"Page\.content: Unable to retrieve content"),
    re.compile(r"reconcile_batch_sync"),
    re.compile(r"pyee/asyncio\.py"),
    re.compile(r"self\._context\.run"),
    re.compile(r"self\.emit"),
]

def classify_line(line):
    for category, rx_list in ERROR_RULES:
        if any(rx.search(line) for rx in rx_list):
            return category
    return None

def is_noise(line):
    return any(rx.search(line) for rx in NOISE_PATTERNS)

def process_log_files(file_paths):
    category_counts = Counter()
    unknown_lines = Counter()

    for path in file_paths:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue

                if is_noise(line_str):
                    continue

                cat = classify_line(line_str)
                if cat:
                    category_counts[cat] += 1
                else:
                    # Generalize unknown line for deduplication
                    gen = re.sub(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}', '<TIMESTAMP>', line_str)
                    gen = re.sub(r'https?://[^\s>]+', '<URL>', gen)
                    gen = re.sub(r'/tmp/[^\s>]+', '<TMP_PATH>', gen)
                    unknown_lines[gen] += 1

    return category_counts, unknown_lines

def main():
    log_dir = sys.argv[1] if len(sys.argv) > 1 else "logs/x1"
    files = sorted(glob.glob(os.path.join(log_dir, "*.log")))

    if not files:
        print(f"No log files found in {log_dir}")
        return

    print(f"Analyzing {len(files)} log files from {log_dir}...")
    category_counts, unknown_lines = process_log_files(files)

    print("\n" + "=" * 60)
    print("CLASSIFIED ERROR CATEGORIES SUMMARY")
    print("=" * 60)
    total_known = sum(category_counts.values())
    for cat, count in category_counts.most_common():
        pct = (count / total_known * 100) if total_known > 0 else 0
        print(f"{cat:<35} : {count:>8} ({pct:5.1f}%)")

    print(f"\nTotal Recognized Log Errors: {total_known}")
    print(f"Total Unique Unknown Log Patterns: {len(unknown_lines)}")

    if unknown_lines:
        print("\n" + "=" * 60)
        print("UNKNOWN / UNCLASSIFIED LOG PATTERNS (Candidates for LLM / Rules)")
        print("=" * 60)
        for gen_line, count in unknown_lines.most_common(20):
            print(f"{count:>5}x | {gen_line}")

if __name__ == '__main__':
    main()
