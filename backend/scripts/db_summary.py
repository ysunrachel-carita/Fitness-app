import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv

load_dotenv()

def run_queries():
    url = os.getenv("DATABASE_URL")
    if not url:
        print("DATABASE_URL not found.")
        return
        
    print(f"Connecting to: {url.split('@')[-1]}")
    try:
        conn = psycopg2.connect(url)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        queries = [
            ("1. Exercises Summary", "SELECT count(*) FROM exercises;"),
            ("2. Set Components Summary", "SELECT count(*) FROM set_components;"),
            ("3. Lift Tables (New)", "SELECT (SELECT count(*) FROM lift_sessions) as lift_sessions, (SELECT count(*) FROM lift_sets) as lift_sets;"),
            ("4. Legacy Tables (Old)", "SELECT (SELECT count(*) FROM exercise_sessions) as exercise_sessions, (SELECT count(*) FROM set_entries) as set_entries;"),
            ("5. Workout Summary", "SELECT (SELECT count(*) FROM workout_sessions) as sessions, (SELECT count(*) FROM set_groups) as groups;")
        ]
        
        for title, sql in queries:
            print(f"\n--- {title} ---")
            cur.execute(sql)
            rows = cur.fetchall()
            if not rows:
                print("No data found.")
                continue
                
            # Print headers
            headers = rows[0].keys()
            print(" | ".join(headers))
            print("-" * 50)
            for row in rows:
                print(" | ".join(str(v) for v in row.values()))
                
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_queries()
