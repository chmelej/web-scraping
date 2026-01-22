from pybloom_live import BloomFilter
import io
from src.utils.db import get_db_connection, get_cursor

class BloomFilterManager:
    def __init__(self):
        self.conn = get_db_connection()
        self.filters = {}

    def create_filter(self, name, capacity=1000000, error_rate=0.001):
        """Vytvoří nový bloom filter"""
        bf = BloomFilter(capacity=capacity, error_rate=error_rate)

        with get_cursor(self.conn, dict_cursor=False) as cur:
            cur.execute("""
                INSERT INTO scr_bloom_filters
                (name, filter_data, item_count, false_positive_rate)
                VALUES (%s, %s, 0, %s)
                ON CONFLICT (name) DO NOTHING
            """, (name, bf.bitarray.tobytes(), error_rate))
            self.conn.commit()

        self.filters[name] = bf
        return bf

    def load_filter(self, name):
        """Načte bloom filter z DB"""
        if name in self.filters:
            return self.filters[name]

        with get_cursor(self.conn) as cur:
            cur.execute("""
                SELECT filter_data FROM scr_bloom_filters WHERE name = %s
            """, (name,))
            row = cur.fetchone()

            if not row:
                # Create if doesn't exist
                return self.create_filter(name)

            # Deserialize
            bf = BloomFilter.fromfile(io.BytesIO(row['filter_data']))
            self.filters[name] = bf
            return bf

    def add(self, filter_name, item, source='scraped'):
        """Přidá item do filtru"""
        bf = self.load_filter(filter_name)

        if item in bf:
            return False # already exists

        bf.add(item)

        # Save to DB
        with get_cursor(self.conn, dict_cursor=False) as cur:
            # Update filter
            cur.execute("""
                UPDATE scr_bloom_filters
                SET filter_data = %s,
                    item_count = item_count + 1,
                    last_updated = NOW()
                WHERE name = %s
            """, (bf.bitarray.tobytes(), filter_name))

            # Save item to items table
            cur.execute("""
                INSERT INTO scr_bloom_filter_items(filter_name, item, source)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (filter_name, item, source))

            self.conn.commit()

        return True

    def check(self, filter_name, item):
        """Zkontroluje zda item existuje v filtru"""
        bf = self.load_filter(filter_name)
        return item in bf

    def stats(self, filter_name):
        """Statistiky filtru"""
        with get_cursor(self.conn) as cur:
            cur.execute("""
                SELECT item_count, false_positive_rate, last_updated
                FROM scr_bloom_filters WHERE name = %s
            """, (filter_name,))
            return cur.fetchone()

    def rebuild_from_db(self, filter_name):
        """Rebuil filtru z bloom_filter_items"""
        with get_cursor(self.conn) as cur:
             cur.execute("SELECT item FROM scr_bloom_filter_items WHERE filter_name = %s", (filter_name,))
             items = cur.fetchall()

             # Delete old filter
             # We should probably get capacity from old filter or config, defaulting to len(items)*2
             capacity = max(len(items) * 2, 100000)

        with get_cursor(self.conn, dict_cursor=False) as cur:
             cur.execute("DELETE FROM scr_bloom_filters WHERE name = %s", (filter_name,))
             self.conn.commit()

        bf = self.create_filter(filter_name, capacity=capacity)

        for row in items:
             bf.add(row['item'])

        # Update DB
        with get_cursor(self.conn, dict_cursor=False) as cur:
            cur.execute("""
                UPDATE scr_bloom_filters
                SET filter_data = %s,
                    item_count = %s
                WHERE name = %s
            """, (bf.bitarray.tobytes(), len(bf), filter_name))
            self.conn.commit()
