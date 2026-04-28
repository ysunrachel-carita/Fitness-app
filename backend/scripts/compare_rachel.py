import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv

load_dotenv()

LOCAL_URL = os.getenv("DATABASE_URL")
RENDER_URL = os.getenv("RENDER_DATABASE_URL")

def compare_rachel_sessions():
    local_conn = psycopg2.connect(LOCAL_URL)
    render_conn = psycopg2.connect(RENDER_URL)
    
    local_cur = local_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    render_cur = render_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        # Fetch Local sessions for Rachel (ID 1)
        local_cur.execute("SELECT date, type, notes FROM workout_sessions WHERE user_id = 1")
        local_sessions = local_cur.fetchall()
        
        # Fetch Render sessions for Rachel (ID 2)
        render_cur.execute("SELECT date, type, notes FROM workout_sessions WHERE user_id = 2")
        render_sessions = render_cur.fetchall()
        
        # Create a "key" for matching: (date, type)
        # Note: date might be a string or datetime, we'll normalize it to string
        render_keys = set((str(s['date']), s['type']) for s in render_sessions)
        
        missing_on_render = []
        for s in local_sessions:
            key = (str(s['date']), s['type'])
            if key not in render_keys:
                missing_on_render.append(s)
        
        print(f"\n--- Rachel's Workout Session Comparison ---")
        print(f"Local (ID 1) sessions: {len(local_sessions)}")
        print(f"Render (ID 2) sessions: {len(render_sessions)}")
        print(f"\nSessions found Locally but MISSING on Render ({len(missing_on_render)}):")
        
        if not missing_on_render:
            print("  [✓] All local sessions for Rachel already exist on Render.")
        else:
            for s in missing_on_render:
                print(f"  - Date: {s['date']} | Type: {s['type']} | Notes: {s['notes']}")
                
    finally:
        local_cur.close()
        render_cur.close()
        local_conn.close()
        render_conn.close()

if __name__ == "__main__":
    compare_rachel_sessions()
