import sqlite3
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def remove_from_sqlite():
    db_path = 'fitness.db'
    if not os.path.exists(db_path):
        print(f"SQLite database {db_path} not found.")
        return
        
    print(f"Removing columns from SQLite ({db_path})...")
    try:
        conn = sqlite3.connect(db_path)
        # Check SQLite version for DROP COLUMN support (3.35.0+)
        version = sqlite3.sqlite_version_info
        if version >= (3, 35, 0):
            try:
                conn.execute("ALTER TABLE set_components DROP COLUMN load_type")
                conn.execute("ALTER TABLE set_components DROP COLUMN load_value")
                conn.execute("ALTER TABLE exercises DROP COLUMN is_calorie")
                conn.commit()
                print("  [✓] Columns dropped using ALTER TABLE.")
            except sqlite3.OperationalError as e:
                print(f"  [!] Note: {e} (They might already be gone)")
        else:
            # Manual recreation for older SQLite
            print("  [!] SQLite version < 3.35.0. Need to recreate table.")
            # This is complex, so we'll just skip or tell user
            print("  [!] Please manually recreate the table if needed, or use a newer SQLite.")
        conn.close()
    except Exception as e:
        print(f"  [❌] SQLite Error: {e}")

def remove_from_postgres():
    url = os.getenv("DATABASE_URL")
    if not url:
        print("DATABASE_URL not found in .env.")
        return
        
    print(f"Removing columns from Postgres ({url.split('@')[-1]})...")
    try:
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        cur.execute("ALTER TABLE set_components DROP COLUMN IF EXISTS load_type")
        cur.execute("ALTER TABLE set_components DROP COLUMN IF EXISTS load_value")
        cur.execute("ALTER TABLE exercises DROP COLUMN IF EXISTS is_calorie")
        conn.commit()
        cur.close()
        conn.close()
        print("  [✓] Columns dropped successfully (if they existed).")
    except Exception as e:
        print(f"  [❌] Postgres Error: {e}")

if __name__ == "__main__":
    remove_from_sqlite()
    print("-" * 30)
    remove_from_postgres()
    print("\nDone! Code and database are now cleaned up.")
