from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
import psycopg2
from psycopg2.extras import DictCursor
from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Any
from urllib.parse import urlparse
from ..deps import get_db_connection, get_cursor
from ..utils.nfs import generate_nfs_path
from src.utils.urls import clean_url, unify_url
from src.utils.storage import read_raw_html, generate_html_file_path


router = APIRouter()

class QueueItemRequest(BaseModel):
    url: HttpUrl
    priority: int = 10
    uni_listing_id: Optional[int] = None

class QueueItemResponse(BaseModel):
    message: str
    id: Optional[int] = None
    url: str
    status: str

@router.post("/", response_model=QueueItemResponse)
def add_to_queue(item: QueueItemRequest, db: psycopg2.extensions.connection = Depends(get_db_connection)):
    """Add a single URL to the scraping queue."""
    raw_url = str(item.url)
    cleaned_url = clean_url(raw_url)
    norm_url = unify_url(raw_url)

    with db.cursor(cursor_factory=DictCursor) as cursor:
        try:
            # Check if URL exists by normalized_url or exact cleaned url
            cursor.execute("""
                SELECT queue_id, status FROM scr_scrape_queue
                WHERE (normalized_url = %s OR url = %s) AND (uni_listing_id = %s OR (uni_listing_id IS NULL AND %s IS NULL))
            """, (norm_url, cleaned_url, item.uni_listing_id, item.uni_listing_id))

            existing = cursor.fetchone()

            if existing:
                if existing['status'] in ('pending', 'processing'):
                    return QueueItemResponse(
                        message="URL already in queue",
                        id=existing['queue_id'],
                        url=cleaned_url,
                        status=existing['status']
                    )
                else:
                    # Update existing record
                    cursor.execute("""
                        UPDATE scr_scrape_queue
                        SET status = 'pending', priority = %s, retry_count = 0, next_scrape_at = NOW(), normalized_url = %s
                        WHERE queue_id = %s
                        RETURNING queue_id, status
                    """, (item.priority, norm_url, existing['queue_id']))
                    updated = cursor.fetchone()
                    db.commit()
                    return QueueItemResponse(
                        message="URL requeued successfully",
                        id=updated['queue_id'],
                        url=cleaned_url,
                        status=updated['status']
                    )

            # Insert new record
            cursor.execute("""
                INSERT INTO scr_scrape_queue (url, normalized_url, uni_listing_id, priority, status)
                VALUES (%s, %s, %s, %s, 'pending')
                RETURNING queue_id, status
            """, (cleaned_url, norm_url, item.uni_listing_id, item.priority))

            new_item = cursor.fetchone()
            db.commit()

            return QueueItemResponse(
                message="URL added to queue successfully",
                id=new_item['queue_id'],
                url=cleaned_url,
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

    with db.cursor(cursor_factory=DictCursor) as cursor:
        try:
            for line in urls:
                line_str = line.strip()
                if not line_str or not line_str.startswith('http'):
                    skipped_count += 1
                    continue

                cleaned_url = clean_url(line_str)
                norm_url = unify_url(line_str)

                # Check if exists
                cursor.execute("SELECT queue_id, status FROM scr_scrape_queue WHERE normalized_url = %s OR url = %s", (norm_url, cleaned_url))
                existing = cursor.fetchone()

                if existing:
                    if existing['status'] not in ('pending', 'processing'):
                        # Requeue
                        cursor.execute("""
                            UPDATE scr_scrape_queue
                            SET status = 'pending', priority = %s, retry_count = 0, next_scrape_at = NOW(), normalized_url = %s
                            WHERE queue_id = %s
                        """, (priority, norm_url, existing['queue_id']))
                        added_count += 1
                    else:
                        skipped_count += 1
                else:
                    # Insert
                    cursor.execute("""
                        INSERT INTO scr_scrape_queue (url, normalized_url, priority, status)
                        VALUES (%s, %s, %s, 'pending')
                    """, (cleaned_url, norm_url, priority))
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
    """Get information about a specific URL including its scrape status and metadata."""

    search_url = clean_url(url)
    norm_url = unify_url(url)
    parsed = urlparse(search_url)

    with db.cursor(cursor_factory=DictCursor) as cursor:
        # Get queue info
        cursor.execute("""
            SELECT * FROM scr_scrape_queue
            WHERE normalized_url = %s OR url = %s
            ORDER BY added_at DESC LIMIT 1
        """, (norm_url, search_url))
        queue_info = cursor.fetchone()

        # Get results info
        cursor.execute("""
            SELECT * FROM scr_scrape_results
            WHERE url = %s OR queue_id = %s
            ORDER BY scraped_at DESC
        """, (search_url, queue_info['queue_id'] if queue_info else None))
        results = cursor.fetchall()

        if not queue_info and not results:
            # Basic fallback for small websites (ignore query string)
            if parsed.query:
                base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                cursor.execute("SELECT * FROM scr_scrape_queue WHERE url = %s ORDER BY added_at DESC LIMIT 1", (base_url,))
                queue_info = cursor.fetchone()
                cursor.execute("SELECT * FROM scr_scrape_results WHERE url = %s ORDER BY scraped_at DESC", (base_url,))
                results = cursor.fetchall()

        if not queue_info and not results:
             raise HTTPException(status_code=404, detail="URL not found in queue or results")


        latest_result = results[0] if results else None
        first_result = results[-1] if results else None

        # Determine website type based on depth/count (placeholder logic)
        domain_pattern = f"%{parsed.netloc}%"
        cursor.execute("SELECT COUNT(DISTINCT url) FROM scr_scrape_queue WHERE url LIKE %s", (domain_pattern,))
        count_row = cursor.fetchone()
        domain_urls_count = count_row[0] if count_row else 0

        site_type = "single_page"
        if domain_urls_count > 100:
            site_type = "large"
        elif domain_urls_count > 10:
            site_type = "small"


        response_data = {
            "url": queue_info['url'] if queue_info else search_url,
            "normalized_url": queue_info['normalized_url'] if queue_info and queue_info.get('normalized_url') else norm_url,
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

        }

        # Generate NFS paths if we have a scrape date
        if latest_result and latest_result['scraped_at']:
             timestamp_str = latest_result['scraped_at'].strftime("%Y%m%dT%H%M%S")
             response_data["latestHtmlLink"] = generate_nfs_path(response_data["url"], timestamp_str, ext="html.gz")
             response_data["latestMarkdownLink"] = generate_nfs_path(response_data["url"], timestamp_str, ext="md.gz")
             response_data["latestScreenshotLink"] = generate_nfs_path(response_data["url"], timestamp_str, ext="webp")
        else:
             response_data["latestHtmlLink"] = None
             response_data["latestMarkdownLink"] = None
             response_data["latestScreenshotLink"] = None

        # Fetch parsed data if available
        if latest_result:
           cursor.execute("SELECT data FROM scr_parsed_data WHERE result_id = %s", (latest_result['result_id'],))

           parsed_data = cursor.fetchone()
           if parsed_data:
             response_data["extracted_data"] = parsed_data['data']

        # Add history list for the frontend table
        if results:
            response_data["history"] = []
            for row in results:
                response_data["history"].append({
                    "result_id": row["result_id"],
                    "scraped_at": row["scraped_at"].isoformat() if row.get("scraped_at") else None,
                    "status_code": row["status_code"],
                    "processing_status": row["processing_status"],
                    "error_message": row["error_message"]
                })
        else:
            response_data["history"] = []

        return response_data

@router.get("/html/{result_id}")
def view_raw_html(result_id: int, db: psycopg2.extensions.connection = Depends(get_db_connection)):
    """Fetch and view the raw uncompressed HTML for a given result_id."""
    with db.cursor(cursor_factory=DictCursor) as cursor:
        cursor.execute("SELECT url, html_path, html FROM scr_scrape_results WHERE result_id = %s", (result_id,))
        res = cursor.fetchone()

        if not res:
            raise HTTPException(status_code=404, detail="Scrape result not found")

        html_content = None
        if res.get('html_path'):
            html_content = read_raw_html(res['html_path'])

        if html_content is None:
            file_path = generate_html_file_path(res['url'], result_id)
            html_content = read_raw_html(file_path)

        if html_content is None and res.get('html'):
            html_content = res['html']

        if html_content is None:
            raise HTTPException(status_code=404, detail="Raw HTML file not found on disk or database")

        return HTMLResponse(content=html_content)
