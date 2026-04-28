import os
import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv

load_dotenv()

def run_queries():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not found")
        return

    try:
        conn = psycopg2.connect(database_url)
        with conn.cursor(cursor_factory=DictCursor) as cur:
            print("--- Query 1: Exercises ---")
            cur.execute("SELECT id, name, canonical_key, category FROM exercises ORDER BY category, name;")
            rows = cur.fetchall()
            for row in rows:
                print(f"ID: {row['id']} | Name: {row['name']} | Key: {row['canonical_key']} | Category: {row['category']}")
            
            print("\n--- Query 2: Count ---")
            cur.execute("SELECT COUNT(*) as total FROM exercises;")
            total = cur.fetchone()['total']
            print(f"Total exercises: {total}")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_queries()
