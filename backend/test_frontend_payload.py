import sqlite3
from app import app, get_db

def test_frontend_payload():
    client = app.test_client()
    
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'testuser'

    payload = {
        "date": "2026-04-23",
        "name": "Murph Variant",
        "notes": "Felt good",
        "result": "30:00",
        "repeat": 2,
        "set_groups": [
            {
                "components": [
                    {"exercise": "Pull Up", "reps": 50},
                    {"exercise": "Push Up", "reps": 100}
                ]
            }
        ]
    }
    
    resp = client.post('/workout_sessions', json=payload)
    data = resp.get_json()
    print("Frontend Payload Test Response:", data)
    
    if data.get('success'):
        ws_id = data['workout_session_id']
        with app.app_context():
            conn = get_db()
            ws = conn.execute("SELECT type, notes FROM workout_sessions WHERE id = ?", (ws_id,)).fetchone()
            print("Session DB check:", dict(ws))
            
            comps = conn.execute("SELECT exercise_id, reps FROM set_components JOIN set_groups ON set_groups.id = set_components.set_group_id WHERE set_groups.workout_session_id = ?", (ws_id,)).fetchall()
            print("Components DB check:", [dict(c) for c in comps])

if __name__ == '__main__':
    test_frontend_payload()
