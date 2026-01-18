import click
import sys
import os

# Add src to path
sys.path.append(os.getcwd())

from src.utils.bloom import BloomFilterManager
from src.utils.db import get_db_connection

@click.group()
def cli():
    """Bloom filter management"""
    pass

@cli.command()
@click.argument('name')
@click.option('--capacity', default=1000000, help='Max items')
@click.option('--error-rate', default=0.001, help='False positive rate')
def create(name, capacity, error_rate):
    """Vytvoř nový bloom filter"""
    bfm = BloomFilterManager()
    bfm.create_filter(name, capacity, error_rate)
    click.echo(f"✓ Filter '{name}' created (capacity: {capacity:,})")

@cli.command()
@click.argument('name')
@click.argument('file', type=click.File('r'))
def import_items(name, file):
    """Import items ze souboru"""
    bfm = BloomFilterManager()

    items = [line.strip() for line in file if line.strip()]

    added = 0
    for item in items:
        if bfm.add(name, item, source='imported'):
            added += 1

    click.echo(f"✓ Added {added}/{len(items)} items to '{name}'")

@cli.command()
@click.argument('name')
def stats(name):
    """Zobraz statistiky"""
    bfm = BloomFilterManager()
    stats = bfm.stats(name)

    if not stats:
        click.echo(f"Filter '{name}' not found")
        return

    click.echo(f"Filter: {name}")
    click.echo(f"  Items: {stats['item_count']:,}")
    click.echo(f"  False positive rate: {stats['false_positive_rate']}")
    click.echo(f"  Last updated: {stats['last_updated']}")

@cli.command()
def list_filters():
    """Seznam všech filtrů"""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT name, item_count, last_updated
        FROM bloom_filters
        ORDER BY name
    """)

    for row in cur.fetchall():
        click.echo(f"{row[0]:<20} {row[1]:>10,} items  (updated: {row[2]})")

if __name__ == '__main__':
    cli()
