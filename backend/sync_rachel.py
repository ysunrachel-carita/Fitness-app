import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv

load_dotenv()

LOCAL_URL = os.getenv("DATABASE_URL")
RENDER_URL = os.getenv("RENDER_DATABASE_URL")

# Mapping configuration
LOCAL_USER_ID = 1
RENDER_USER_ID = 2

def sync_rachel_workouts():
    print("🚀 Starting Rachel's Workout Sync (Local ID 1 -> Render ID 2)...")
    
    local_conn = psycopg2.connect(LOCAL_URL)
    render_conn = psycopg2.connect(RENDER_URL)
    
    local_cur = local_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    render_cur = render_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        # 1. Build Exercise Map (canonical_key -> render_id)
        print("  - Mapping exercises by canonical_key...")
        render_cur.execute("SELECT id, canonical_key FROM exercises")
        exercise_map = {row['canonical_key']: row['id'] for row in render_cur.fetchall() if row['canonical_key']}
        
        # Also get local exercise keys for mapping
        local_cur.execute("SELECT id, canonical_key, name FROM exercises")
        local_exercises = {row['id']: (row['canonical_key'] or row['name'].lower()) for row in local_cur.fetchall()}

        # 2. Fetch Local Sessions
        local_cur.execute("SELECT * FROM workout_sessions WHERE user_id = %s", (LOCAL_USER_ID,))
        sessions = local_cur.fetchall()
        print(f"  - Found {len(sessions)} sessions locally.")

        for session in sessions:
            local_session_id = session['id']
            print(f"    - Syncing session: {session['date']} {session['type']}...")
            
            # 3. Insert Session into Render
            # We exclude 'id' to let Render generate a new one
            render_cur.execute("""
                INSERT INTO workout_sessions (user_id, date, type, notes, context, time_cap_minutes, emom_interval, emom_duration, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                RENDER_USER_ID, session['date'], session['type'], session['notes'],
                session['context'], session['time_cap_minutes'], session['emom_interval'],
                session['emom_duration'], session['created_at']
            ))
            new_session_id = render_cur.fetchone()['id']

            # 4. Fetch and Insert Set Groups
            local_cur.execute("SELECT * FROM set_groups WHERE workout_session_id = %s", (local_session_id,))
            groups = local_cur.fetchall()
            
            for group in groups:
                local_group_id = group['id']
                render_cur.execute("""
                    INSERT INTO set_groups (workout_session_id, order_index, type, pattern_index, completed, shared_weight_kg, rest_seconds)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    new_session_id, group['order_index'], group['type'], group['pattern_index'],
                    group['completed'], group['shared_weight_kg'], group['rest_seconds']
                ))
                new_group_id = render_cur.fetchone()['id']

                # 5. Fetch and Insert Set Components
                local_cur.execute("SELECT * FROM set_components WHERE set_group_id = %s", (local_group_id,))
                components = local_cur.fetchall()
                
                for comp in components:
                    # Resolve Exercise ID on Render
                    local_ex_id = comp['exercise_id']
                    ex_key = local_exercises.get(local_ex_id)
                    render_ex_id = exercise_map.get(ex_key)
                    
                    if not render_ex_id:
                        print(f"      [!] Warning: Could not find exercise '{ex_key}' on Render. Skipping component.")
                        continue

                    render_cur.execute("""
                        INSERT INTO set_components (
                            set_group_id, exercise_id, reps, weight_kg, rpe, notes, 
                            duration_seconds, distance_meters, load_type, load_value
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        new_group_id, render_ex_id, comp['reps'], comp['weight_kg'],
                        comp['rpe'], comp['notes'], comp['duration_seconds'],
                        comp['distance_meters'], comp['load_type'], comp['load_value']
                    ))

        render_conn.commit()
        print("\n✅ Sync Complete! All Rachel's local sessions have been pushed to Render.")

    except Exception as e:
        print(f"\n❌ Sync Failed: {e}")
        render_conn.rollback()
    finally:
        local_cur.close()
        render_cur.close()
        local_conn.close()
        render_conn.close()

if __name__ == "__main__":
    sync_rachel_workouts()
