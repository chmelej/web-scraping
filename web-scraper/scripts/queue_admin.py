import click
import sys
import os

# Add src to path
sys.path.append(os.getcwd())

from src.utils.db import get_db_connection
from src.utils.urls import normalize_url

@click.group()
def cli():
    """Queue management"""
    pass

@cli.command()
@click.argument('url')
@click.option('--unit-id', type=int, help='Unit listing ID')
@click.option('--priority', default=0, help='Priority (higher = sooner)')
def add(url, unit_id, priority):
    """Přidej URL do fronty"""
    conn = get_db_connection()
    cur = conn.cursor()

    normalized = normalize_url(url)

    cur.execute("""
        INSERT INTO scr_scrape_queue (url, unit_listing_id, priority)
        VALUES (%s, %s, %s)
        ON CONFLICT (url, unit_listing_id) DO UPDATE
        SET priority = EXCLUDED.priority,
            status = 'pending',
            next_scrape_at = NOW()
        RETURNING id
    """, (normalized, unit_id, priority))

    queue_id = cur.fetchone()[0]
    conn.commit()

    click.echo(f"✓ Added to queue (ID: {queue_id})")

@cli.command()
@click.argument('file', type=click.File('r'))
@click.option('--unit-id', type=int, help='Default unit listing ID')
def bulk_add(file, unit_id):
    """Bulk import URLs ze souboru (jeden per řádek)"""
    conn = get_db_connection()
    cur = conn.cursor()

    urls = [line.strip() for line in file if line.strip()]

    added = 0
    for url in urls:
        try:
            normalized = normalize_url(url)
            cur.execute("""
                INSERT INTO scr_scrape_queue (url, unit_listing_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (normalized, unit_id))
            added += 1
        except Exception as e:
            click.echo(f"Error adding {url}: {e}")

    conn.commit()
    click.echo(f"✓ Added {added}/{len(urls)} URLs")

@cli.command()
@click.argument('url')
def remove(url):
    """Odstraň URL z fronty"""
    conn = get_db_connection()
    cur = conn.cursor()

    normalized = normalize_url(url)

    cur.execute("""
        DELETE FROM scr_scrape_queue
        WHERE url = %s
        RETURNING id
    """, (normalized,))

    if cur.fetchone():
        conn.commit()
        click.echo("✓ Removed")
    else:
        click.echo("URL not found in queue")

@cli.command()
@click.option('--status', help='Filter by status')
def clear(status):
    """Vyčisti frontu"""
    conn = get_db_connection()
    cur = conn.cursor()

    if status:
        cur.execute("DELETE FROM scr_scrape_queue WHERE status = %s", (status,))
    else:
        if not click.confirm("Clear entire queue?"):
            return
        cur.execute("DELETE FROM scr_scrape_queue")

    count = cur.rowcount
    conn.commit()

    click.echo(f"✓ Removed {count} items")

@cli.command()
def reset_failed():
    """Reset failed items zpět na pending"""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE scr_scrape_queue
        SET status = 'pending',
            retry_count = 0,
            next_scrape_at = NOW()
        WHERE status = 'failed'
    """)

    count = cur.rowcount
    conn.commit()

    click.echo(f"✓ Reset {count} failed items")

@cli.command()
@click.argument('domain')
@click.option('--reason', default='manual', help='Reason for blacklist')
def blacklist(domain, reason):
    """Přidej doménu do blacklistu"""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO scr_domain_blacklist
        (domain, reason, auto_added, notes)
        VALUES (%s, %s, FALSE, 'Added manually')
        ON CONFLICT (domain) DO UPDATE
        SET reason = EXCLUDED.reason
    """, (domain, reason))

    conn.commit()
    click.echo(f"✓ Blacklisted {domain}")

@cli.command()
@click.argument('domain')
def whitelist(domain):
    """Odstraň doménu z blacklistu"""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM scr_domain_blacklist WHERE domain = %s", (domain,))

    if cur.rowcount:
        conn.commit()
        click.echo(f"✓ Removed {domain} from blacklist")
    else:
        click.echo(f"Domain {domain} not in blacklist")

if __name__ == '__main__':
    cli()
