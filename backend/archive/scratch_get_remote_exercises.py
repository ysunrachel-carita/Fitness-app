import psycopg2
import os

url = "postgresql://postgres.fbtcphsvncmftxnxdkbg:m5m3W2eE3ugIxcHa@aws-1-us-east-1.pooler.supabase.com:6543/postgres"

def get_remote_exercises():
    try:
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        cur.execute("SELECT id, name, category FROM exercises ORDER BY name ASC")
        rows = cur.fetchall()
        print("ID | Name | Category")
        print("-" * 30)
        for row in rows:
            print(f"{row[0]} | {row[1]} | {row[2]}")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_remote_exercises()
