import psycopg2
from config.settings import DATABASE_URL
import os

def apply_sql_file(cursor, filepath):
    print(f"Applying {filepath}...")
    with open(filepath, 'r') as f:
        cursor.execute(f.read())

def main():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # Order matters
        migrations = [
            'migrations/001_initial_schema.sql',
            'migrations/002_seed_prompts.sql',
            'migrations/003_monitoring_views.sql',
            'migrations/004_add_change_checked.sql'
        ]

        for migration in migrations:
            if os.path.exists(migration):
                apply_sql_file(cur, migration)
            else:
                print(f"Migration file not found: {migration}")

        conn.commit()
        conn.close()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")

if __name__ == '__main__':
    main()
