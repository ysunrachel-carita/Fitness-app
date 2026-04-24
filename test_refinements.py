import sqlite3
from app import app, get_db, calculate_unified_1rm

def test_refinements():
    client = app.test_client()
    
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'testuser'

    # A. Pattern Preservation
    emom_payload = {
        "date": "2026-04-22",
        "type": "emom",
        "repeat": 2,  # 2 rounds
        "set_groups": [
            {"type": "emom", "components": [{"exercise_id": 1, "reps": 5, "weight_kg": 50}]},
            {"type": "emom", "components": [{"exercise_id": 2, "reps": 10, "weight_kg": 30}]},
            {"type": "rest", "components": []}
        ]
    }
    
    resp = client.post('/workout_sessions', json=emom_payload)
    ws_id = resp.get_json()['workout_session_id']
    print(f"Pattern test session created: {ws_id}")
    
    with app.app_context():
        conn = get_db()
        groups = conn.execute("SELECT order_index, pattern_index FROM set_groups WHERE workout_session_id = ? ORDER BY order_index", (ws_id,)).fetchall()
        print("Pattern indexes for EMOM:", [dict(g) for g in groups])
        # Expect: (0,0), (1,1), (2,2), (3,0), (4,1), (5,2)

    # B. Shared Weight
    complex_payload = {
        "date": "2026-04-22",
        "type": "complex",
        "set_groups": [
            {
                "type": "complex",
                "shared_weight_kg": 100,
                "components": [
                    {"exercise_id": 3, "reps": 1}, # Weight inherited
                    {"exercise_id": 3, "reps": 1, "weight_kg": 105} # Explicit override
                ]
            }
        ]
    }
    
    resp = client.post('/workout_sessions', json=complex_payload)
    ws_id2 = resp.get_json()['workout_session_id']
    print(f"Shared weight session created: {ws_id2}")
    
    # C. Completion Flag & D. 1RM Filtering
    # We will log a warmup set, a working set, and a failed working set.
    # We will test 1RM for exercise 4.
    strength_payload = {
        "date": "2026-04-22",
        "type": "strength",
        "set_groups": [
            {
                "type": "normal",
                "completed": True,
                "components": [{"exercise_id": 4, "reps": 5, "weight_kg": 20}] # Warmup
            },
            {
                "type": "normal",
                "completed": True,
                "components": [{"exercise_id": 4, "reps": 5, "weight_kg": 100}] # Working set
            },
            {
                "type": "normal",
                "completed": False,
                "components": [{"exercise_id": 4, "reps": 5, "weight_kg": 120}] # Failed attempt
            }
        ]
    }
    
    client.post('/workout_sessions', json=strength_payload)
    
    with app.app_context():
        conn = get_db()
        rm = calculate_unified_1rm(conn, 4, 1)
        print("Calculated 1RM for Exercise 4 (Should ignore 20kg and 120kg(failed)): ", rm)
        # 100 * (1 + 5/30) = 116.666...
        conn.close()

if __name__ == '__main__':
    test_refinements()
