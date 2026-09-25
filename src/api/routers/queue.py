from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
import psycopg2
from psycopg2.extras import DictCursor
from pydantic import BaseModel, HttpUrl
from urllib.parse import urlparse
from ..deps import get_db_connection, get_cursor
from ..utils.nfs import generate_nfs_path
from src.utils.urls import clean_url, unify_url
from src.utils.storage import read_raw_html, generate_html_file_path, save_raw_html


router = APIRouter()

class QueueItemRequest(BaseModel):
    url: HttpUrl
    priority: int = 10
    uni_listing_id: int | None = None

class QueueItemResponse(BaseModel):
    message: str
    id: int | None = None
    url: str
    status: str

class ManualUpdateRequest(BaseModel):
    url: HttpUrl
    html: str
    queue_id: int | None = None

@router.post("/", response_model=QueueItemResponse)
def add_to_queue(item: QueueItemRequest, db: psycopg2.extensions.connection = Depends(get_db_connection)):
    """Add a single URL to the scraping queue."""
    raw_url = str(item.url)
    cleaned_url = clean_url(raw_url)
    url_hash_str = unify_url(raw_url)

    with db.cursor(cursor_factory=DictCursor) as cursor:
        try:
            # Check if URL exists by url_hash or exact cleaned url
            cursor.execute("""
                SELECT queue_id, status FROM scr_scrape_queue
                WHERE (url_hash = %s OR url = %s) AND (uni_listing_id = %s OR (uni_listing_id IS NULL AND %s IS NULL))
            """, (url_hash_str, cleaned_url, item.uni_listing_id, item.uni_listing_id))

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
                        SET status = 'pending', priority = %s, retry_count = 0, next_scrape_at = NOW(), url_hash = %s, url = %s
                        WHERE queue_id = %s
                        RETURNING queue_id, status
                    """, (item.priority, url_hash_str, cleaned_url, existing['queue_id']))
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
                INSERT INTO scr_scrape_queue (url, url_hash, uni_listing_id, priority, status)
                VALUES (%s, %s, %s, %s, 'pending')
                RETURNING queue_id, status
            """, (cleaned_url, url_hash_str, item.uni_listing_id, item.priority))

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

@router.post("/manual")
def manual_update_url(item: ManualUpdateRequest, db: psycopg2.extensions.connection = Depends(get_db_connection)):
    """Manually upload HTML for a URL, mimicking the scraper but bypassing fetching."""
    raw_url = str(item.url)
    cleaned_url = clean_url(raw_url)
    norm_url = unify_url(raw_url)
    html_content = item.html

    with db.cursor(cursor_factory=DictCursor) as cursor:
        try:
            # 1. Ensure it's in the queue or update its status to 'manual'
            queue_id = item.queue_id

            if not queue_id:
                # Try finding it
                cursor.execute("""
                    SELECT queue_id FROM scr_scrape_queue
                    WHERE url_hash = %s OR url = %s
                """, (norm_url, cleaned_url))
                row = cursor.fetchone()
                if row:
                    queue_id = row['queue_id']

            if queue_id:
                cursor.execute("""
                    UPDATE scr_scrape_queue
                    SET status = 'manual', retry_count = 0, next_scrape_at = NOW(), url_hash = %s, url = %s
                    WHERE queue_id = %s
                """, (norm_url, cleaned_url, queue_id))
            else:
                # Insert it manually if not found at all
                cursor.execute("""
                    INSERT INTO scr_scrape_queue (url, url_hash, status)
                    VALUES (%s, %s, 'manual')
                    RETURNING queue_id
                """, (cleaned_url, norm_url))
                queue_id = cursor.fetchone()['queue_id']

            # 2. Insert into scr_scrape_results (status_code 200, processing_status 'new')
            cursor.execute("""
                INSERT INTO scr_scrape_results
                (queue_id, url, status_code, processing_status)
                VALUES (%s, %s, %s, %s)
                RETURNING result_id
            """, (queue_id, cleaned_url, 200, 'new'))
            result_id = cursor.fetchone()['result_id']

            # 3. Save raw HTML to NFS
            html_path, html_size = save_raw_html(cleaned_url, html_content, result_id=result_id)

            # 4. Update the result with html path and size
            if html_path:
                cursor.execute("""
                    UPDATE scr_scrape_results
                    SET html_path = %s, html_size = %s
                    WHERE result_id = %s
                """, (html_path, html_size, result_id))

            db.commit()

            return {
                "message": "Manual update successful",
                "queue_id": queue_id,
                "result_id": result_id
            }

        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Error processing manual update: {str(e)}")


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
                cursor.execute("SELECT queue_id, status FROM scr_scrape_queue WHERE url_hash = %s OR url = %s", (norm_url, cleaned_url))
                existing = cursor.fetchone()

                if existing:
                    if existing['status'] not in ('pending', 'processing'):
                        # Requeue
                        cursor.execute("""
                            UPDATE scr_scrape_queue
                            SET status = 'pending', priority = %s, retry_count = 0, next_scrape_at = NOW(), url_hash = %s, url = %s
                            WHERE queue_id = %s
                        """, (priority, norm_url, cleaned_url, existing['queue_id']))
                        added_count += 1
                    else:
                        skipped_count += 1
                else:
                    # Insert
                    cursor.execute("""
                        INSERT INTO scr_scrape_queue (url, url_hash, priority, status)
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
        # Get queue info - prefer exact URL match, then completed/pending status, then newest added
        cursor.execute("""
            SELECT * FROM scr_scrape_queue
            WHERE url_hash = %s OR url = %s
            ORDER BY 
                CASE WHEN url = %s THEN 0 ELSE 1 END,
                CASE WHEN status = 'completed' THEN 0 WHEN status = 'pending' THEN 1 ELSE 2 END,
                added_at DESC 
            LIMIT 1
        """, (norm_url, search_url, search_url))
        queue_info = cursor.fetchone()

        qid = queue_info['queue_id'] if queue_info else None

        # Get results info for all queue items with matching url_hash / search_url or redirect chain
        cursor.execute("""
            SELECT * FROM scr_scrape_results
            WHERE queue_id IN (
                SELECT queue_id FROM scr_scrape_queue
                WHERE url_hash = %s 
                   OR url = %s
                   OR (following_queue_id = %s AND %s IS NOT NULL)
                   OR (queue_id = %s AND %s IS NOT NULL)
            )
            OR url = %s OR url = %s
            ORDER BY scraped_at DESC
        """, (
            norm_url, search_url,
            qid, qid,
            qid, qid,
            search_url, f"{search_url}/"
        ))
        results = cursor.fetchall()

        if not queue_info and not results:
            # Basic fallback for small websites (ignore query string)
            if parsed.query:
                base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                base_norm = unify_url(base_url)
                cursor.execute("""
                    SELECT * FROM scr_scrape_queue 
                    WHERE url_hash = %s OR url = %s 
                    ORDER BY 
                        CASE WHEN url = %s THEN 0 ELSE 1 END,
                        added_at DESC 
                    LIMIT 1
                """, (base_norm, base_url, base_url))
                queue_info = cursor.fetchone()
                base_qid = queue_info['queue_id'] if queue_info else None
                cursor.execute("""
                    SELECT * FROM scr_scrape_results 
                    WHERE queue_id IN (
                        SELECT queue_id FROM scr_scrape_queue 
                        WHERE url_hash = %s 
                           OR url = %s
                           OR (following_queue_id = %s AND %s IS NOT NULL)
                           OR (queue_id = %s AND %s IS NOT NULL)
                    )
                    OR url = %s OR url = %s
                    ORDER BY scraped_at DESC
                """, (
                    base_norm, base_url,
                    base_qid, base_qid,
                    base_qid, base_qid,
                    base_url, f"{base_url}/"
                ))
                results = cursor.fetchall()

        if not queue_info and not results:
             raise HTTPException(status_code=404, detail="URL not found in queue or results")

        latest_result = results[0] if results else None
        first_result = results[-1] if results else None

        # Determine website type based on unique url_hash count for this domain
        domain = norm_url.split('/')[0] if norm_url else (parsed.netloc or "")
        cursor.execute("""
            SELECT COUNT(DISTINCT url_hash) FROM scr_scrape_queue 
            WHERE url_hash = %s OR url_hash LIKE %s
        """, (domain, f"{domain}/%"))
        count_row = cursor.fetchone()
        domain_urls_count = count_row[0] if count_row else 0

        site_type = "single_page"
        if domain_urls_count > 100:
            site_type = "large"
        elif domain_urls_count > 10:
            site_type = "small"


        response_data = {
            "queue_id": queue_info['queue_id'] if queue_info else None,
            "url": queue_info['url'] if queue_info else search_url,
            "url_hash": queue_info['url_hash'] if queue_info and queue_info.get('url_hash') else norm_url,
            "normalized_url": queue_info['url_hash'] if queue_info and queue_info.get('url_hash') else norm_url,
            "status": queue_info['status'] if queue_info else "unknown",
            "following_queue_id": queue_info['following_queue_id'] if queue_info and queue_info.get('following_queue_id') else None,
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
                    "queue_id": row.get("queue_id"),
                    "url": row.get("url"),
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
