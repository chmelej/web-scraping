import os
import gzip
import hashlib
import base64
import re
from urllib.parse import urlparse
from config.settings import RAW_HTML_DIR, ENABLE_RAW_HTML_STORAGE

def get_url_hash(url: str) -> str:
    """
    Generates a URL-safe Base64 hash from the URL.
    """
    digest = hashlib.sha256(url.encode('utf-8')).digest()
    # URL-safe Base64 without trailing '=' padding
    b64 = base64.urlsafe_b64encode(digest).decode('ascii').rstrip('=')
    # Replace any non-alphanumeric chars if needed for safe subdirs
    clean_b64 = re.sub(r'[^a-zA-Z0-9]', 'x', b64)
    return clean_b64

def generate_html_file_path(url: str, result_id: int | str, base_dir: str = None) -> str:
    """
    Generates a file path for raw HTML storage based on URL, Base64 hash, and result_id version.
    Format: [base_dir]/[subdir1]/[subdir2]/[domain]_[url_hash]_[version].html.gz
    where:
      <subdir1> = url_hash[0:2]
      <subdir2> = url_hash[2:4]
      <verze>   = result_id
    """
    if base_dir is None:
        base_dir = RAW_HTML_DIR

    try:
        parsed = urlparse(url)
        domain = parsed.netloc or "unknown"
        safe_domain = domain.replace(':', '_').replace('/', '_')

        url_hash = get_url_hash(url)
        subdir1 = url_hash[0:2]
        subdir2 = url_hash[2:4]

        filename = f"{safe_domain}_{url_hash}_{result_id}.html.gz"
        return os.path.join(base_dir, subdir1, subdir2, filename)
    except Exception:
        fallback_hash = hashlib.md5(url.encode('utf-8')).hexdigest()[:10]
        return os.path.join(base_dir, "error", f"file_{fallback_hash}_{result_id}.html.gz")

def save_raw_html(url: str, html_content: str, result_id: int | str, base_dir: str = None) -> tuple:
    """
    Compresses and saves raw HTML content to disk/NFS under base_dir.
    Returns (relative_file_path, uncompressed_size_in_bytes).
    """
    if not ENABLE_RAW_HTML_STORAGE or not html_content:
        return None, 0

    encoded_bytes = html_content.encode('utf-8')
    uncompressed_size = len(encoded_bytes)

    rel_path = generate_html_file_path(url, result_id, base_dir)
    full_path = os.path.abspath(rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    with gzip.open(full_path, 'wb') as f:
        f.write(encoded_bytes)

    return rel_path, uncompressed_size

def read_raw_html(item_or_path) -> str | None:
    """
    Reads and decompresses raw HTML from file path or falls back to 'html' field in item dict/row.
    """
    file_path = None
    if isinstance(item_or_path, str):
        file_path = item_or_path
    elif isinstance(item_or_path, dict):
        file_path = item_or_path.get('html_path')
        if not file_path:
            return item_or_path.get('html')
    elif hasattr(item_or_path, '__getitem__'):
        try:
            file_path = item_or_path['html_path']
        except (KeyError, IndexError):
            pass
        if not file_path:
            try:
                return item_or_path['html']
            except (KeyError, IndexError):
                return None

    if file_path:
        full_path = os.path.abspath(file_path)
        if os.path.exists(full_path):
            with gzip.open(full_path, 'rt', encoding='utf-8', errors='ignore') as f:
                return f.read()

    return None
