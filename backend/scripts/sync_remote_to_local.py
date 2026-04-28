import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv

# --- CONFIGURATION ---
REMOTE_URL = "postgresql://postgres.fbtcphsvncmftxnxdkbg:m5m3W2eE3ugIxcHa@aws-1-us-east-1.pooler.supabase.com:6543/postgres"
LOCAL_URL = "postgresql://postgres:postgres@localhost:5432/fitness_app"

TABLES_TO_SYNC = [
    "users",
    "exercises",
    "workout_sessions",
    "lift_sessions",
    "set_groups",
    "set_components",
    "lift_sets",
    "runs",
    "wods",
    "user_profiles"
]

def sync():
    print("🔄 Starting Full Remote -> Local Sync...")
    
    try:
        remote_conn = psycopg2.connect(REMOTE_URL)
        local_conn = psycopg2.connect(LOCAL_URL)
        
        remote_cur = remote_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        local_cur = local_conn.cursor()
        
        # 1. Clear Local Tables
        print("  - Clearing local tables...")
        for table in reversed(TABLES_TO_SYNC):
            local_cur.execute(f"TRUNCATE TABLE {table} CASCADE;")
        
        # 2. Copy Data
        for table in TABLES_TO_SYNC:
            print(f"  - Syncing table: {table}...")
            remote_cur.execute(f"SELECT * FROM {table}")
            rows = remote_cur.fetchall()
            
            if not rows:
                print(f"    [!] No data found in remote {table}. Skipping.")
                continue
                
            columns = rows[0].keys()
            query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(columns))})"
            
            for row in rows:
                local_cur.execute(query, list(row.values()))
            
            print(f"    [✓] Synced {len(rows)} rows.")

        local_conn.commit()
        print("\n✅ Sync Complete! Your local database is now an exact match of Supabase.")

    except Exception as e:
        print(f"\n❌ Sync Failed: {e}")
        if 'local_conn' in locals(): local_conn.rollback()
    finally:
        if 'remote_conn' in locals(): remote_conn.close()
        if 'local_conn' in locals(): local_conn.close()

if __name__ == "__main__":
    sync()
