from flask import Blueprint, request, session, redirect, url_for, render_template, flash, jsonify
from datetime import date
from db import get_db
from utils.auth import login_required
from exercises import get_all_exercises, resolve_exercise
from services.workout_service import create_workout_session
from utils.formatting import _date_only

workout_bp = Blueprint('workout', __name__)

@workout_bp.route('/log_workout', methods=['GET'])
@login_required
def log_workout():
    return render_template(
        'log_workout.html',
        exercises=get_all_exercises(),
        today_date=date.today().isoformat()
    )

@workout_bp.route('/workout_sessions', methods=['POST'])
@login_required
def save_workout_session():
    user_id = session["user_id"]
    payload = request.get_json(silent=True) or {}
    
    if 'set_groups' in payload and 'groups' not in payload:
        payload['groups'] = payload['set_groups']
    if 'type' in payload and 'title' not in payload:
        payload['title'] = payload['type']

    ws_id, error = create_workout_session(user_id, payload)
    
    if error:
        return jsonify({"success": False, "error": error}), 400
        
    return jsonify({"success": True, "id": ws_id})

@workout_bp.route('/workouts/history')
@login_required
def workout_history():
    conn = get_db()
    user_id = session["user_id"]

    date_range = request.args.get('range', '')
    exercise_filter = request.args.get('exercise', '')

    # Build filters
    date_clause = ""
    params = [user_id]
    if date_range:
        params.append(date_range)
        date_clause = "AND ws.date >= (CURRENT_DATE - CAST(%s AS INTEGER) * INTERVAL '1 day')"

    exercise_clause = ""
    if exercise_filter:
        exercise_id, _ = resolve_exercise(conn, exercise_filter)
        if exercise_id:
            exercise_clause = """
                AND ws.id IN (
                    SELECT sg.workout_session_id
                    FROM set_groups sg
                    JOIN set_components sc ON sc.set_group_id = sg.id
                    WHERE sc.exercise_id = %s
                )
            """
            params.append(exercise_id)
        else:
            exercise_clause = "AND 1=0"

    rows = conn.execute(f"""
        SELECT ws.id, ws.date, ws.title, ws.notes, ws.created_at,
               ws.context, ws.time_cap_minutes, ws.emom_interval, ws.emom_duration, ws.result,
               COUNT(DISTINCT sg.id) AS group_count,
               COUNT(sc.id) AS component_count
        FROM workout_sessions ws
        LEFT JOIN set_groups sg ON sg.workout_session_id = ws.id
        LEFT JOIN set_components sc ON sc.set_group_id = sg.id
        WHERE ws.user_id = %s {date_clause} {exercise_clause}
        GROUP BY ws.id
        ORDER BY ws.date DESC, ws.created_at DESC
    """, params).fetchall()

    sessions = []
    for row in rows:
        ws_id = row['id']
        groups = conn.execute("""
            SELECT sg.id, sg.order_index, sg.type, sg.rest_seconds
            FROM set_groups sg
            WHERE sg.workout_session_id = %s
            ORDER BY sg.order_index
        """, (ws_id,)).fetchall()

        group_list = []
        for g in groups:
            comps = conn.execute("""
                SELECT sc.id, e.name AS exercise, sc.reps, sc.weight_kg, 
                       sc.target_type, sc.calories, sc.distance_meters, sc.time_seconds
                FROM set_components sc
                JOIN exercises e ON sc.exercise_id = e.id
                WHERE sc.set_group_id = %s
            """, (g['id'],)).fetchall()
            group_list.append({
                'id': g['id'],
                'order_index': g['order_index'],
                'rest_seconds': g['rest_seconds'],
                'components': [dict(c) for c in comps]
            })

        sessions.append({
            'id': row['id'],
            'date': _date_only(row['date']),
            'name': row['title'] or 'Untitled Workout',
            'notes': row['notes'],
            'context': row['context'],
            'time_cap_minutes': row['time_cap_minutes'],
            'emom_interval': row['emom_interval'],
            'emom_duration': row['emom_duration'],
            'group_count': row['group_count'],
            'component_count': row['component_count'],
            'result': row['result'],
            'groups': group_list,
        })

    logged_exercises_rows = conn.execute("""
        SELECT DISTINCT e.name
        FROM set_components sc
        JOIN set_groups sg ON sc.set_group_id = sg.id
        JOIN workout_sessions ws ON sg.workout_session_id = ws.id
        JOIN exercises e ON sc.exercise_id = e.id
        WHERE ws.user_id = %s
        ORDER BY e.name
    """, (user_id,)).fetchall()
    filter_exercises = [row['name'] for row in logged_exercises_rows]
    conn.close()

    from collections import OrderedDict
    grouped = OrderedDict()
    for ws in sessions:
        grouped.setdefault(ws['date'], []).append(ws)

    return render_template('workout_history.html',
        grouped=grouped,
        current_range=date_range,
        current_exercise=exercise_filter,
        exercises=get_all_exercises(),
        filter_exercises=filter_exercises,
        page='history'
    )
