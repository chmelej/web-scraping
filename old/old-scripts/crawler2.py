from scrapling.fetchers import Fetcher
from urllib.parse import urlparse, urljoin

def fetch_and_process(fetcher, url):
    """
    Fetch a URL with Scrapling Fetcher and store response content and status.
    When parent_id is None, enqueue same-domain links found on the page.
    """
    print(f"GET {url}")
    page = fetcher.get(url, follow_redirects=True, stealthy_headers=True)
    # Try to get HTML/text content from the page object
    #body = page.body
    #if body is None:
    #    body = page.text
    #    print("page.body is None, using page.text instead")
    status_code = page.status
    # Enqueue internal links only for root pages (parent_id is None)
    if status_code == 200:
        base_netloc = urlparse(url).netloc
        # Find anchor tags and normalize to absolute URLs
        for a in page.find_all('a'):
            try:
                href = a['href']
            except:
                href = None
            if href is not None:
                link_url = urljoin(url, str(href))
                if urlparse(link_url).netloc == base_netloc:
                    print(f"new internal link {link_url}")


def main():
    fetcher = Fetcher()
    fetch_and_process(fetcher, 'https://www.facebook.com/')


if __name__ == '__main__':
    main()
