import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

RENDER_URL = os.getenv("RENDER_DATABASE_URL")
IDS_TO_DELETE = (1, 3, 4)

def delete_users():
    if not RENDER_URL:
        print("RENDER_DATABASE_URL not found in .env")
        return

    conn = psycopg2.connect(RENDER_URL)
    cur = conn.cursor()
    
    try:
        print(f"Attempting to delete users {IDS_TO_DELETE} from Render...")
        
        # We need to delete from child tables first if CASCADE isn't set on the DB level
        # Based on app.py, these tables reference user_id
        child_tables = ["exercise_sessions", "workout_sessions", "runs", "wods", "user_profiles"]
        
        for table in child_tables:
            cur.execute(f"DELETE FROM {table} WHERE user_id IN %s", (IDS_TO_DELETE,))
            print(f"  - Cleaned up {table}")
            
        cur.execute("DELETE FROM users WHERE id IN %s", (IDS_TO_DELETE,))
        print(f"DONE: Deleted users {IDS_TO_DELETE} from users table.")
        
        conn.commit()
    except Exception as e:
        print(f"FAILED: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    delete_users()
