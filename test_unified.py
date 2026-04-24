import sqlite3
import json
from app import app, get_db

def test_workout_sessions():
    client = app.test_client()
    
    # We need a user session to test login_required endpoints.
    # First, register a test user or just simulate a logged-in user.
    with client.session_transaction() as sess:
        sess['user_id'] = 1  # Assuming user_id 1 exists
        sess['username'] = 'testuser'

    # A. Strength-style workout
    # 4 sets of squat, 1 component per set
    strength_payload = {
        "date": "2026-04-22",
        "type": "strength",
        "notes": "Leg day",
        "set_groups": [
            {
                "type": "normal",
                "repeat": 4,
                "components": [
                    {
                        "exercise_id": 1,  # Squat
                        "reps": 5,
                        "weight_kg": 100
                    }
                ]
            }
        ]
    }
    
    resp = client.post('/workout_sessions', json=strength_payload)
    print("Strength workout response:", resp.get_json())

    # B. Complex workout
    # clean -> clean -> jerk sequence
    complex_payload = {
        "date": "2026-04-22",
        "type": "complex",
        "notes": "Bear complex",
        "set_groups": [
            {
                "type": "complex",
                "repeat": 5,
                "components": [
                    {"exercise_id": 2, "reps": 1, "weight_kg": 60}, # Clean
                    {"exercise_id": 2, "reps": 1, "weight_kg": 60}, # Clean
                    {"exercise_id": 3, "reps": 1, "weight_kg": 60}  # Jerk
                ]
            }
        ]
    }
    
    resp = client.post('/workout_sessions', json=complex_payload)
    print("Complex workout response:", resp.get_json())

    # C. EMOM workout
    # alternating movements, rest sets
    emom_payload = {
        "date": "2026-04-22",
        "type": "emom",
        "repeat": 3,  # 3 rounds
        "set_groups": [
            {
                "type": "emom",
                "components": [{"exercise_id": 1, "reps": 10, "weight_kg": 50}]
            },
            {
                "type": "emom",
                "components": [{"exercise_id": 2, "reps": 15}]
            },
            {
                "type": "rest",
                "components": [] # Rest minute
            }
        ]
    }
    
    resp = client.post('/workout_sessions', json=emom_payload)
    print("EMOM workout response:", resp.get_json())

if __name__ == '__main__':
    test_workout_sessions()
