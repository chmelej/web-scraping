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
                SELECT date_trunc('day', scraped_at) as day, count(*) as count,
                       sum(case when status_code = 200 then 1 else 0 end) as success_count
                FROM scr_scrape_results
                WHERE scraped_at >= NOW() - INTERVAL '7 days'
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

            return {
                "total_urls": total_queue_count,
                "pending_queue": pending_count,
                "status_breakdown": queue_stats,
                "recent_velocity": daily_scrapes
            }
        except psycopg2.Error as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
