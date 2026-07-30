import hashlib
from urllib.parse import urlparse

def generate_nfs_path(url: str, timestamp_str: str, prefix: str = "/data/scraping-data", ext: str = "html.gz") -> str:
    """
    Generates a deterministic NFS file path based on URL and timestamp.
    Format: [prefix]/[domain_hash[0:2]]/[domain_hash[2:4]]/[domain]_[path_hash]_[timestamp].[ext]
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        # If there's no domain (e.g. invalid URL), fallback to entire URL as string
        if not domain:
            domain = "unknown"

        path_query = parsed.path
        if parsed.query:
            path_query += "?" + parsed.query

        domain_hash = hashlib.md5(domain.encode('utf-8')).hexdigest()
        path_hash = hashlib.md5(path_query.encode('utf-8')).hexdigest()

        dir1 = domain_hash[0:2]
        dir2 = domain_hash[2:4]

        # Clean up domain string to prevent invalid chars in filename (e.g. port numbers)
        safe_domain = domain.replace(':', '_')

        filename = f"{safe_domain}_{path_hash}_{timestamp_str}.{ext}"

        # Join parts, ensuring no double slashes
        path_parts = [prefix.rstrip('/'), dir1, dir2, filename]
        return "/".join(path_parts)
    except Exception:
        # Fallback if something goes wrong
        return f"{prefix.rstrip('/')}/error/path_generation_failed.{ext}"
