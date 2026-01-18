import psycopg2
from scrapling.fetchers import Fetcher
from urllib.parse import urlparse, urljoin
import time
from myutils import load_properties


def get_waiting_urls(cursor):
    cursor.execute(
        "SELECT id, parent_id, url FROM webcrawler_scrapling_data WHERE meta_record_status = 'waiting_in_queue' LIMIT 100")
    return cursor.fetchall()


def update_status_and_body(cursor, id, body, status):
    cursor.execute(
        "UPDATE webcrawler_scrapling_data SET response_body=%s, meta_record_status=%s, meta_modified_when = now() WHERE id=%s",
        (body, status, id))


def insert_url_if_not_exists(cursor, url, parent_id):
    cursor.execute("SELECT count(*) FROM webcrawler_scrapling_data WHERE url=%s", (url,))
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO webcrawler_scrapling_data (url, parent_id, meta_record_status, meta_modified_when, meta_created_when) VALUES (%s, %s, %s, now(), now())",
            (url, parent_id, 'waiting_in_queue'))


def fetch_and_process(cursor, fetcher, rec_id, parent_id, url):
    """
    Fetch a URL with Scrapling Fetcher and store response content and status.
    When parent_id is None, enqueue same-domain links found on the page.
    """
    try:
        print(f"GET {url}")
        page = fetcher.get(url, follow_redirects=True, stealthy_headers=True)
        # Try to get HTML/text content from the page object
        body = page.body
        if body is None:
            body = page.text
        status_code = page.status
        update_status_and_body(cursor, rec_id, body, 'http_200_ok' if status_code == 200 else f"http_{status_code}")
        # Enqueue internal links only for root pages (parent_id is None)
        if status_code == 200 and parent_id is None:
            base_netloc = urlparse(url).netloc
            # Find anchor tags and normalize to absolute URLs
            a_cnt = 0
            for a in page.find_all('a'):
                a_cnt += 1
                if (a_cnt >= 10):
                    break
                try:
                    href = a['href']
                except:
                    href = None
                if href is not None:
                    link_url = urljoin(url, str(href))
                    if urlparse(link_url).netloc == base_netloc:
                        insert_url_if_not_exists(cursor, link_url, rec_id)

        time.sleep(5)  # Pauza mezi požadavky
    except Exception as e:
        # Store error (truncate to 100 chars for meta status)
        update_status_and_body(cursor, rec_id, '', str(e)[:100])
        print(f"ERROR: {e}")


def main():
    config = load_properties('config.properties')
    DB = {'dbname': config['dbname'], 'user': config['username'], 'password': config['password'],
          'host': config['hostname']}

    fetcher = Fetcher()
    prev_cnt = -1
    cnt = 0
    with psycopg2.connect(**DB) as conn:
        with conn.cursor() as cursor:
            while prev_cnt < cnt:
                prev_cnt = cnt
                for id, parent_id, url in get_waiting_urls(cursor):
                    cnt += 1
                    fetch_and_process(cursor, fetcher, id, parent_id, url)
                    conn.commit()


if __name__ == '__main__':
    main()
