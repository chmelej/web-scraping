import click
import sys
import os
import json

# Add src to path
sys.path.append(os.getcwd())

from src.utils.db import get_db_connection
from datetime import datetime

@click.group()
def cli():
    """Monitoring and stats"""
    pass

@cli.command()
def health():
    """System health check"""
    conn = get_db_connection()
    cur = conn.cursor()

    # Queue status
    click.echo("=== Queue Status ===")
    cur.execute("SELECT * FROM scr_scraping_health")
    for row in cur.fetchall():
        click.echo(f"{row[0]:<12} {row[1]:>6} (avg retries: {row[2]:.1f})")

    # Recent activity
    click.echo("\n=== Last 24h Activity ===")
    cur.execute("""
        SELECT
            COUNT(*) as scrapes,
            COUNT(DISTINCT detected_language) as languages
        FROM scr_scrape_results
        WHERE scraped_at > NOW() - INTERVAL '24 hours'
    """)
    row = cur.fetchone()
    click.echo(f"Scrapes: {row[0]}")
    click.echo(f"Languages: {row[1]}")

    # Parsing backlog
    cur.execute("""
        SELECT COUNT(*) FROM scr_scrape_results
        WHERE processing_status = 'new'
    """)
    backlog = cur.fetchone()[0]
    click.echo(f"\nParsing backlog: {backlog}")

@cli.command()
@click.option('--days', default=7, help='Number of days')
def stats(days):
    """Statistics for last N days"""
    conn = get_db_connection()
    cur = conn.cursor()

    click.echo(f"=== Stats for last {days} days ===\n")

    cur.execute(f"""
        SELECT * FROM scr_daily_stats
        WHERE date > CURRENT_DATE - {days}
        ORDER BY date DESC
    """)

    click.echo(f"{'Date':<12} {'Total':>8} {'Success':>8} {'Languages':>10}")
    click.echo("-" * 45)
    for row in cur.fetchall():
        click.echo(f"{row[0]} {row[1]:>8} {row[2]:>8} {row[3]:>10}")

@cli.command()
def quality():
    """Quality score distribution"""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM scr_quality_distribution")

    click.echo("=== Quality Distribution ===")
    for row in cur.fetchall():
        click.echo(f"{row[0]:<12} {row[1]:>6}")

@cli.command()
def changes():
    """Recent changes summary"""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM scr_recent_changes LIMIT 20")

    click.echo("=== Recent Changes (Top 20) ===")
    click.echo(f"{'Listing ID':<12} {'Field':<20} {'Count':>6} {'Last Change'}")
    click.echo("-" * 60)

    for row in cur.fetchall():
        click.echo(f"{row[0]:<12} {row[1]:<20} {row[2]:>6} {row[3]}")

@cli.command()
def blacklist():
    """Blacklist summary"""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM scr_blacklist_summary")

    click.echo("=== Blacklist Summary ===")
    click.echo(f"{'Reason':<20} {'Domains':>8} {'Avg Fails':>10}")
    click.echo("-" * 45)

    for row in cur.fetchall():
        click.echo(f"{row[0]:<20} {row[1]:>8} {row[2]:>10.1f}")

@cli.command()
@click.argument('unit_listing_id', type=int)
def listing(unit_listing_id):
    """Detail konkrétního listingu"""
    conn = get_db_connection()
    cur = conn.cursor()

    # Latest data
    cur.execute("""
        SELECT data, quality_score, extracted_at, content_language
        FROM scr_parsed_data
        WHERE unit_listing_id = %s
        ORDER BY extracted_at DESC
        LIMIT 1
    """, (unit_listing_id,))

    row = cur.fetchone()
    if not row:
        click.echo(f"No data for listing {unit_listing_id}")
        return

    data, quality, extracted, lang = row

    click.echo(f"=== Listing {unit_listing_id} ===")
    click.echo(f"Language: {lang}")
    click.echo(f"Quality: {quality}/100")
    click.echo(f"Last scraped: {extracted}")
    click.echo("\nData:")
    click.echo(json.dumps(data, indent=2, ensure_ascii=False))

    # Recent changes
    click.echo("\n=== Recent Changes ===")
    cur.execute("""
        SELECT field_name, old_value, new_value, detected_at
        FROM scr_change_history
        WHERE unit_listing_id = %s
        ORDER BY detected_at DESC
        LIMIT 10
    """, (unit_listing_id,))

    for row in cur.fetchall():
        click.echo(f"\n{row[3]} - {row[0]}:")
        click.echo(f"  Old: {row[1]}")
        click.echo(f"  New: {row[2]}")

if __name__ == '__main__':
    cli()
