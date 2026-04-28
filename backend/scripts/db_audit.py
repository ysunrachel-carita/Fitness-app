import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Configuration - Update these in your .env or here
# LOCAL_DATABASE_URL = os.getenv("DATABASE_URL") # Currently set to local in .env
# RENDER_DATABASE_URL = os.getenv("RENDER_DATABASE_URL") 

# For the purpose of this script, we'll ask for them or use placeholders if not found
LOCAL_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/fitness_app")
RENDER_URL = os.getenv("RENDER_DATABASE_URL", "your_render_db_url_here")

TABLES_TO_COMPARE = [
    "users",
    "exercises",
    "workout_sessions",
    "set_groups",
    "set_components",
    "lift_sessions",
    "lift_sets",
    "runs",
    "wods",
    "user_profiles"
]

def get_connection(url):
    try:
        conn = psycopg2.connect(url)
        return conn
    except Exception as e:
        print(f"Error connecting to {url}: {e}")
        return None

def fetch_table_data(conn, table_name):
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        # Handle user_profiles which uses user_id as PK
        key_col = 'user_id' if table_name == 'user_profiles' else 'id'
        return {row[key_col]: dict(row) for row in rows}
    except Exception as e:
        print(f"Error fetching data from {table_name}: {e}")
        return {}
    finally:
        cursor.close()

def compare_tables(local_data, render_data, table_name):
    print(f"\n--- Comparing Table: {table_name} ---")
    
    local_ids = set(local_data.keys())
    render_ids = set(render_data.keys())
    
    only_local = local_ids - render_ids
    only_render = render_ids - local_ids
    common_ids = local_ids & render_ids
    
    if only_local:
        print(f"  [!] {len(only_local)} rows exist ONLY in Local: {sorted(list(only_local))[:10]}{'...' if len(only_local) > 10 else ''}")
    else:
        print("  [✓] No rows exist only in Local.")
        
    if only_render:
        print(f"  [!] {len(only_render)} rows exist ONLY in Render: {sorted(list(only_render))[:10]}{'...' if len(only_render) > 10 else ''}")
    else:
        print("  [✓] No rows exist only in Render.")
        
    diff_count = 0
    for row_id in common_ids:
        local_row = local_data[row_id]
        render_row = render_data[row_id]
        
        diffs = []
        for col, val in local_row.items():
            # Handle potential type mismatches or None comparisons
            if val != render_row.get(col):
                diffs.append(f"{col}: {val} (Local) vs {render_row.get(col)} (Render)")
        
        if diffs:
            diff_count += 1
            if diff_count <= 5: # Only show first 5 differences per table to avoid spam
                print(f"  [Δ] Row ID {row_id} has differences:")
                for d in diffs:
                    print(f"      - {d}")
    
    if diff_count > 5:
        print(f"  ... and {diff_count - 5} more rows with differences.")
    elif diff_count == 0:
        print("  [✓] All common rows match perfectly.")
    else:
        print(f"  [!] Total rows with differences: {diff_count}")

def main():
    if RENDER_URL == "your_render_db_url_here":
        print("Please set RENDER_DATABASE_URL in your .env or the script.")
        return

    print("Connecting to Local DB...")
    local_conn = get_connection(LOCAL_URL)
    
    print("Connecting to Render DB...")
    render_conn = get_connection(RENDER_URL)
    
    if not local_conn or not render_conn:
        print("Failed to connect to one or both databases.")
        return

    try:
        for table in TABLES_TO_COMPARE:
            local_data = fetch_table_data(local_conn, table)
            render_data = fetch_table_data(render_conn, table)
            
            if not local_data and not render_data:
                print(f"\n--- Table: {table} (Empty or missing in both) ---")
                continue
                
            compare_tables(local_data, render_data, table)
            
    finally:
        local_conn.close()
        render_conn.close()

if __name__ == "__main__":
    main()
