from fastapi import APIRouter, Depends, HTTPException
import psycopg2
from psycopg2.extras import DictCursor
from typing import Dict, Any
from ..deps import get_db_connection

router = APIRouter()

@router.get("")
def get_dashboard(db: psycopg2.extensions.connection = Depends(get_db_connection)) -> Dict[str, Any]:
    """Get overview statistics for the dashboard."""
    with db.cursor(cursor_factory=DictCursor) as cursor:
        try:
            # Stats from queue_stats view or direct table
            cursor.execute("""
                SELECT status, count(*) as count
                FROM scr_scrape_queue
                GROUP BY status
            """)
            queue_stats_raw = cursor.fetchall()

            queue_stats = {}
            total_queue_count = 0
            pending_count = 0

            for row in queue_stats_raw:
                status = row['status']
                count = row['count']
                queue_stats[status] = count
                total_queue_count += count
                if status == 'pending':
                    pending_count += count

            # Daily scrapes from daily_scrapes view or direct table (last 7 days)
            cursor.execute("""
                WITH max_date AS (
                    SELECT COALESCE(MAX(scraped_at), NOW()) as max_scraped_at
                    FROM scr_scrape_results
                )
                SELECT date_trunc('day', scraped_at) as day, count(*) as count,
                       sum(case when status_code = 200 then 1 else 0 end) as success_count
                FROM scr_scrape_results, max_date
                WHERE scraped_at >= max_date.max_scraped_at - INTERVAL '7 days'
                GROUP BY 1
                ORDER BY 1 DESC
            """)
            daily_scrapes_raw = cursor.fetchall()

            daily_scrapes = []
            for row in daily_scrapes_raw:
                if row['day']:
                    daily_scrapes.append({
                        "date": row['day'].strftime("%Y-%m-%d"),
                        "total": row['count'],
                        "success": int(row['success_count']) if row['success_count'] else 0
                    })

            # Latest 10 unique domains scraped
            cursor.execute("""
                SELECT * FROM (
                    SELECT *, row_number() OVER (PARTITION BY domain ORDER BY scraped_at desc) rn  FROM (
                        SELECT scraped_at, queue_id, url, (string_to_array(url, '/'))[3] as domain FROM scr_scrape_results order by scraped_at desc limit 100
                    ) as sub1
                ) as sub2 where rn=1
                ORDER BY scraped_at DESC
                LIMIT 10
            """)
            recent_domains_raw = cursor.fetchall()

            recent_domains = []
            for row in recent_domains_raw:
                recent_domains.append({
                    "scraped_at": row["scraped_at"].isoformat() if row["scraped_at"] else None,
                    "queue_id": row["queue_id"],
                    "url": row["url"],
                    "domain": row["domain"]
                })

            return {
                "total_urls": total_queue_count,
                "pending_queue": pending_count,
                "status_breakdown": queue_stats,
                "recent_velocity": daily_scrapes,
                "recent_domains": recent_domains
            }
        except psycopg2.Error as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
