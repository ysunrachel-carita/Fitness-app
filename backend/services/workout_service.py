from db import get_db
from exercises import resolve_exercise
from datetime import datetime

def create_workout_session(user_id, data):
    """
    data: dict with title, date, notes, context, time_cap_minutes, emom_interval, emom_duration, result, groups
    groups: list of { title, components }
    components: list of { exercise, sets, reps, weight_kg, weight_percent, calories, distance_km, time_seconds, shuttle_distance }
    """
    conn = get_db()
    try:
        title = data.get('title', 'Workout').strip() or 'Workout'
        date_str = data.get('date', '').strip() or datetime.now().strftime('%Y-%m-%d')
        notes = data.get('notes', '').strip() or None
        context = data.get('context', 'Other')
        time_cap = data.get('time_cap_minutes')
        emom_interval = data.get('emom_interval')
        emom_duration = data.get('emom_duration')
        result = data.get('result')

        ws_cursor = conn.execute(
            """
            INSERT INTO workout_sessions 
            (user_id, date, title, notes, context, time_cap_minutes, emom_interval, emom_duration, result)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (user_id, date_str, title, notes, context, time_cap, emom_interval, emom_duration, result)
        )
        ws_id = ws_cursor.lastrowid

        for group_index, group in enumerate(data.get('groups', [])):
            sg_cursor = conn.execute(
                "INSERT INTO set_groups (workout_session_id, title, order_index) VALUES (%s, %s, %s) RETURNING id",
                (ws_id, group.get('title', '').strip() or f"Group {group_index+1}", group_index)
            )
            sg_id = sg_cursor.lastrowid

            for comp_index, comp in enumerate(group.get('components', [])):
                exercise_name = comp.get('exercise', '').strip()
                if not exercise_name: continue

                ex_id, ex_name = resolve_exercise(conn, exercise_name)
                
                conn.execute(
                    """
                    INSERT INTO set_components 
                    (set_group_id, exercise_id, sets, reps, weight_kg, weight_percent, calories, distance_km, time_seconds, shuttle_distance, order_index)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        sg_id, ex_id, 
                        comp.get('sets'), comp.get('reps'), comp.get('weight_kg'), 
                        comp.get('weight_percent'), comp.get('calories'), 
                        comp.get('distance_km'), comp.get('time_seconds'), 
                        comp.get('shuttle_distance'), comp_index
                    )
                )

        conn.commit()
        return ws_id, None
    except Exception as e:
        return None, str(e)
    finally:
        conn.close()
