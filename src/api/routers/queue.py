from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
import psycopg2
from psycopg2.extras import DictCursor
from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Any
from urllib.parse import urlparse
from ..deps import get_db_connection, get_cursor
from src.utils.storage import read_raw_html, generate_html_file_path
from src.utils.urls import normalize_url

router = APIRouter()

class QueueItemRequest(BaseModel):
    url: HttpUrl
    priority: int = 10
    uni_listing_id: Optional[str] = None

class QueueItemResponse(BaseModel):
    message: str
    id: Optional[int] = None
    url: str
    status: str

@router.post("/", response_model=QueueItemResponse)
def add_to_queue(item: QueueItemRequest, db: psycopg2.extensions.connection = Depends(get_db_connection)):
    """Add a single URL to the scraping queue."""
    url_str = str(item.url)
    norm_url = normalize_url(url_str)

    with db.cursor(cursor_factory=DictCursor) as cursor:
        try:
            # Check if URL exists by normalized_url (fallback to url if column doesn't exist yet, but requirement says it does)
            try:
                cursor.execute("""
                    SELECT queue_id, status FROM scr_scrape_queue
                    WHERE (normalized_url = %s OR url = %s) AND (uni_listing_id = %s OR (uni_listing_id IS NULL AND %s IS NULL))
                """, (norm_url, url_str, item.uni_listing_id, item.uni_listing_id))
            except psycopg2.errors.UndefinedColumn:
                db.rollback()
                # Fallback if normalized_url doesn't exist yet in the actual DB
                cursor.execute("""
                    SELECT queue_id, status FROM scr_scrape_queue
                    WHERE url = %s AND (uni_listing_id = %s OR (uni_listing_id IS NULL AND %s IS NULL))
                """, (url_str, item.uni_listing_id, item.uni_listing_id))

            existing = cursor.fetchone()

            if existing:
                if existing['status'] in ('pending', 'processing'):
                    return QueueItemResponse(
                        message="URL already in queue",
                        id=existing['queue_id'],
                        url=url_str,
                        status=existing['status']
                    )
                else:
                    # Update existing record
                    try:
                        cursor.execute("""
                            UPDATE scr_scrape_queue
                            SET status = 'pending', priority = %s, retry_count = 0, next_scrape_at = NOW(), normalized_url = %s
                            WHERE queue_id = %s
                            RETURNING queue_id, status
                        """, (item.priority, norm_url, existing['queue_id']))
                    except psycopg2.errors.UndefinedColumn:
                        db.rollback()
                        cursor.execute("""
                            UPDATE scr_scrape_queue
                            SET status = 'pending', priority = %s, retry_count = 0, next_scrape_at = NOW()
                            WHERE queue_id = %s
                            RETURNING queue_id, status
                        """, (item.priority, existing['queue_id']))

                    updated = cursor.fetchone()
                    db.commit()
                    return QueueItemResponse(
                        message="URL requeued successfully",
                        id=updated['queue_id'],
                        url=url_str,
                        status=updated['status']
                    )

            # Insert new record
            try:
                cursor.execute("""
                    INSERT INTO scr_scrape_queue (url, normalized_url, uni_listing_id, priority, status)
                    VALUES (%s, %s, %s, %s, 'pending')
                    RETURNING queue_id, status
                """, (url_str, norm_url, item.uni_listing_id, item.priority))
            except psycopg2.errors.UndefinedColumn:
                db.rollback()
                cursor.execute("""
                    INSERT INTO scr_scrape_queue (url, uni_listing_id, priority, status)
                    VALUES (%s, %s, %s, 'pending')
                    RETURNING queue_id, status
                """, (url_str, item.uni_listing_id, item.priority))

            new_item = cursor.fetchone()
            db.commit()

            return QueueItemResponse(
                message="URL added to queue successfully",
                id=new_item['queue_id'],
                url=url_str,
                status=new_item['status']
            )

        except psycopg2.Error as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/bulk")
async def bulk_add_to_queue(file: UploadFile = File(...), db: psycopg2.extensions.connection = Depends(get_db_connection)):
    """Bulk add URLs to the queue from a text file (one URL per line). Priority is 5."""
    if not file.filename.endswith(('.txt', '.csv')):
         raise HTTPException(status_code=400, detail="Only .txt or .csv files are supported")

    content = await file.read()
    urls = content.decode('utf-8').splitlines()

    added_count = 0
    skipped_count = 0
    priority = 5

    # Check if normalized_url exists in schema
    has_normalized = False
    with db.cursor(cursor_factory=DictCursor) as cursor:
        try:
            cursor.execute("SELECT normalized_url FROM scr_scrape_queue LIMIT 0")
            has_normalized = True
        except psycopg2.errors.UndefinedColumn:
            db.rollback()
            has_normalized = False

        try:
            for line in urls:
                url_str = line.strip()
                if not url_str or not url_str.startswith('http'):
                    skipped_count += 1
                    continue

                norm_url = normalize_url(url_str)

                # Check if exists
                if has_normalized:
                    cursor.execute("SELECT queue_id, status FROM scr_scrape_queue WHERE normalized_url = %s OR url = %s", (norm_url, url_str))
                else:
                    cursor.execute("SELECT queue_id, status FROM scr_scrape_queue WHERE url = %s", (url_str,))

                existing = cursor.fetchone()

                if existing:
                    if existing['status'] not in ('pending', 'processing'):
                        # Requeue
                        if has_normalized:
                            cursor.execute("""
                                UPDATE scr_scrape_queue
                                SET status = 'pending', priority = %s, retry_count = 0, next_scrape_at = NOW(), normalized_url = %s
                                WHERE queue_id = %s
                            """, (priority, norm_url, existing['queue_id']))
                        else:
                            cursor.execute("""
                                UPDATE scr_scrape_queue
                                SET status = 'pending', priority = %s, retry_count = 0, next_scrape_at = NOW()
                                WHERE queue_id = %s
                            """, (priority, existing['queue_id']))
                        added_count += 1
                    else:
                        skipped_count += 1
                else:
                    # Insert
                    if has_normalized:
                        cursor.execute("""
                            INSERT INTO scr_scrape_queue (url, normalized_url, priority, status)
                            VALUES (%s, %s, %s, 'pending')
                        """, (url_str, norm_url, priority))
                    else:
                        cursor.execute("""
                            INSERT INTO scr_scrape_queue (url, priority, status)
                            VALUES (%s, %s, 'pending')
                        """, (url_str, priority))
                    added_count += 1

            db.commit()
            return {
                "message": "Bulk upload processed",
                "added_count": added_count,
                "skipped_or_invalid_count": skipped_count
            }

        except psycopg2.Error as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/info")
def get_url_info(url: str, db: psycopg2.extensions.connection = Depends(get_db_connection)):
    """Get information about a specific URL including its scrape status and history."""
    search_url = url
    norm_url = normalize_url(search_url)

    # Check if normalized_url exists in schema
    has_normalized = False
    with db.cursor(cursor_factory=DictCursor) as cursor:
        try:
            cursor.execute("SELECT normalized_url FROM scr_scrape_queue LIMIT 0")
            has_normalized = True
        except psycopg2.errors.UndefinedColumn:
            db.rollback()
            has_normalized = False

        # Get queue info
        if has_normalized:
            cursor.execute("""
                SELECT * FROM scr_scrape_queue
                WHERE normalized_url = %s OR url = %s
                ORDER BY added_at DESC LIMIT 1
            """, (norm_url, search_url))
        else:
            cursor.execute("""
                SELECT * FROM scr_scrape_queue
                WHERE url = %s
                ORDER BY added_at DESC LIMIT 1
            """, (search_url,))

        queue_info = cursor.fetchone()

        # Get results info - fetch all history based on queue_id if exists, otherwise by URL
        results = []
        if queue_info:
            cursor.execute("""
                SELECT * FROM scr_scrape_results
                WHERE queue_id = %s
                ORDER BY scraped_at DESC
            """, (queue_info['queue_id'],))
            results = cursor.fetchall()
        else:
            cursor.execute("""
                SELECT * FROM scr_scrape_results
                WHERE url = %s
                ORDER BY scraped_at DESC
            """, (search_url,))
            results = cursor.fetchall()

        if not queue_info and not results:
             raise HTTPException(status_code=404, detail="URL not found in queue or results")

        latest_result = results[0] if results else None
        first_result = results[-1] if results else None

        parsed = urlparse(queue_info['url'] if queue_info else search_url)
        domain_pattern = f"%{parsed.netloc}%"
        cursor.execute("SELECT COUNT(DISTINCT url) FROM scr_scrape_queue WHERE url LIKE %s", (domain_pattern,))
        count_row = cursor.fetchone()
        domain_urls_count = count_row[0] if count_row else 0

        site_type = "single_page"
        if domain_urls_count > 100:
            site_type = "large"
        elif domain_urls_count > 10:
            site_type = "small"

        # Format history rows for the UI
        history = []
        for r in results:
             history.append({
                  "result_id": r['result_id'],
                  "scraped_at": r['scraped_at'],
                  "status_code": r['status_code'],
                  "processing_status": r['processing_status'],
                  "error_message": r['error_message'],
             })

        response_data = {
            "url": queue_info['url'] if queue_info else search_url,
            "normalized_url": queue_info.get('normalized_url') if queue_info and 'normalized_url' in queue_info else norm_url,
            "status": queue_info['status'] if queue_info else "unknown",
            "in_queue": bool(queue_info and queue_info['status'] == 'pending'),
            "added_at": queue_info['added_at'] if queue_info else None,
            "next_scrape_at": queue_info['next_scrape_at'] if queue_info else None,
            "retry_count": queue_info['retry_count'] if queue_info else 0,

            "site_type": site_type,
            "first_scraped_at": first_result['scraped_at'] if first_result else None,
            "latest_scraped_at": latest_result['scraped_at'] if latest_result else None,

            "latest_status_code": latest_result['status_code'] if latest_result else None,
            "latest_error": latest_result['error_message'] if latest_result else None,

            "history": history
        }

        # Fetch parsed data for the latest result if available
        if latest_result:
             cursor.execute("SELECT data FROM scr_parsed_data WHERE result_id = %s", (latest_result['result_id'],))
             parsed_data = cursor.fetchone()
             if parsed_data:
                 response_data["extracted_data"] = parsed_data['data']

        return response_data

@router.get("/html/{result_id}")
def view_raw_html(result_id: int, db: psycopg2.extensions.connection = Depends(get_db_connection)):
    """Fetch and view the raw uncompressed HTML for a given result_id."""
    with db.cursor(cursor_factory=DictCursor) as cursor:
        cursor.execute("SELECT url FROM scr_scrape_results WHERE result_id = %s", (result_id,))
        res = cursor.fetchone()

        if not res:
            raise HTTPException(status_code=404, detail="Scrape result not found")

        url = res['url']
        # read_raw_html accepts either a file path or a dictionary.
        # But wait, read_raw_html signature is read_raw_html(item_or_path).
        # If we pass a dict, it expects 'html_path' or 'html'.
        # Let's just generate the path and pass it.
        file_path = generate_html_file_path(url, result_id)

        html_content = read_raw_html(file_path)

        if html_content is None:
            # Fallback: check if it's stored in the DB (for old rows before migration to disk)
            cursor.execute("SELECT html FROM scr_scrape_results WHERE result_id = %s", (result_id,))
            res2 = cursor.fetchone()
            if res2 and res2.get('html'):
                html_content = res2['html']
            else:
                raise HTTPException(status_code=404, detail="Raw HTML file not found on disk or database")

        return HTMLResponse(content=html_content)
