import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def migrate():
    url = os.getenv("DATABASE_URL")
    if not url:
        print("DATABASE_URL not found.")
        return
        
    print(f"🚀 Starting Migration on: {url.split('@')[-1]}")
    try:
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        
        # 1. Migrate exercise_sessions -> lift_sessions
        print("  - Migrating exercise_sessions to lift_sessions...")
        # Note: We handle the date casting for Postgres
        cur.execute(r"""
            INSERT INTO lift_sessions (id, user_id, exercise_id, notes, date, created_at)
            SELECT id, user_id, exercise_id, notes, 
                   (CASE WHEN date ~ '^\d{4}-\d{2}-\d{2}' THEN date ELSE '1970-01-01' END)::timestamp, 
                   (CASE WHEN created_at ~ '^\d{4}-\d{2}-\d{2}' THEN created_at ELSE '1970-01-01' END)::timestamp
            FROM exercise_sessions
            ON CONFLICT (id) DO NOTHING;
        """)
        
        # 2. Migrate set_entries -> lift_sets
        print("  - Migrating set_entries to lift_sets...")
        cur.execute("""
            INSERT INTO lift_sets (id, lift_session_id, weight_kg, reps, order_index, rpe, notes)
            SELECT id, session_id, weight_kg, reps, order_index, rpe, notes
            FROM set_entries
            ON CONFLICT (id) DO NOTHING;
        """)
        
        # 3. Update sequences to avoid primary key conflicts
        print("  - Updating sequences...")
        cur.execute("SELECT setval('exercise_sessions_id_seq', (SELECT MAX(id) FROM lift_sessions))")
        cur.execute("SELECT setval('set_entries_id_seq', (SELECT MAX(id) FROM lift_sets))")
        
        # 4. Drop old tables
        print("  - Dropping old tables...")
        cur.execute("DROP TABLE IF EXISTS set_entries CASCADE;")
        cur.execute("DROP TABLE IF EXISTS exercise_sessions CASCADE;")
        
        conn.commit()
        print("\n✅ Migration Successful! Old tables removed.")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"\n❌ Migration Failed: {e}")
        if 'conn' in locals(): conn.rollback()

if __name__ == "__main__":
    migrate()
