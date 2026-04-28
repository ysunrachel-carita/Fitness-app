import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def check_wins_table():
    url = os.environ.get("DATABASE_URL")
    print(f"Checking {url}")
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'wins');")
    exists = cur.fetchone()[0]
    print(f"Table 'wins' exists: {exists}")
    if not exists:
        print("Creating table 'wins'...")
        cur.execute("""
            CREATE TABLE wins (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                entry TEXT NOT NULL,
                date DATE NOT NULL DEFAULT CURRENT_DATE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        print("Table 'wins' created.")
    conn.close()

if __name__ == "__main__":
    check_wins_table()
