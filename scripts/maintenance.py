import click
import sys
import os

# Add src to path
sys.path.append(os.getcwd())

from src.utils.db import get_db_connection

@click.group()
def cli():
    """Maintenance tasks"""
    pass

@cli.command()
def deduplicate_http():
    """
    Removes HTTP URLs from queue if HTTPS version has been successfully scraped (200 OK).
    Also removes HTTP from queue if HTTPS is already in queue (pending/processing).
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    click.echo("Starting HTTP deduplication...")

    # 1. Remove HTTP from queue if HTTPS is already in queue (any status)
    # This prevents double scraping
    cur.execute("""
        DELETE FROM scr_scrape_queue q1
        WHERE url LIKE 'http://%'
        AND EXISTS (
            SELECT 1 FROM scr_scrape_queue q2
            WHERE q2.url = 'https://' || substring(q1.url from 8)
        )
    """)
    queue_dupes = cur.rowcount
    click.echo(f"Deleted {queue_dupes} HTTP items that were duplicates of HTTPS items in queue.")

    # 2. Remove HTTP from queue if HTTPS was successfully scraped previously
    # (Checking results table)
    cur.execute("""
        DELETE FROM scr_scrape_queue q1
        WHERE url LIKE 'http://%'
        AND EXISTS (
            SELECT 1 FROM scr_scrape_results r
            WHERE r.url = 'https://' || substring(q1.url from 8)
            AND r.status_code = 200
        )
    """)
    result_dupes = cur.rowcount
    click.echo(f"Deleted {result_dupes} HTTP items because HTTPS version was already scraped successfully.")

    conn.commit()
    conn.close()
    click.echo("Done.")

@cli.command()
@click.option('--keep-versions', default=3, help='Number of historical versions to keep')
def prune_history(keep_versions):
    """
    Prunes old history, keeping only N latest versions per listing.
    Also removes corresponding HTML in scr_scrape_results to save space.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    click.echo(f"Pruning history to keep last {keep_versions} versions...")

    # Delete parsed data beyond N versions
    cur.execute("""
        DELETE FROM scr_parsed_data
        WHERE parsed_id IN (
            SELECT parsed_id
            FROM (
                SELECT parsed_id,
                       ROW_NUMBER() OVER (PARTITION BY uni_listing_id ORDER BY extracted_at DESC) as row_num
                FROM scr_parsed_data
                WHERE uni_listing_id IS NOT NULL
            ) t
            WHERE t.row_num > %s
        )
    """, (keep_versions,))
    
    parsed_deleted = cur.rowcount
    click.echo(f"Deleted {parsed_deleted} old parsed data records.")

    # Delete results that no longer have parsed data AND are not referenced in queue
    # This cleans up large HTML content
    cur.execute("""
        DELETE FROM scr_scrape_results
        WHERE result_id NOT IN (SELECT result_id FROM scr_parsed_data)
        AND result_id NOT IN (SELECT parent_scrape_id FROM scr_scrape_queue WHERE parent_scrape_id IS NOT NULL)
    """)
    results_deleted = cur.rowcount
    click.echo(f"Deleted {results_deleted} orphaned scrape results (HTML content).")

    conn.commit()
    conn.close()
    click.echo("Done.")

if __name__ == '__main__':
    cli()
