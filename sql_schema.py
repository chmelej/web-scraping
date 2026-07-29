import psycopg2
from config.settings import DATABASE_URL
def print_schema():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'scr_scrape_queue'")
    for row in cur.fetchall():
        print(row)
print_schema()
