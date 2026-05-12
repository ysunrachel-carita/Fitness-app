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
    
    # Call the service to create the session
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
            
            comp_list = [dict(c) for c in comps]
            
            # If an exercise filter is active, we only show this group if it contains the filtered exercise.
            # AND we filter the component list to only show that exercise if desired.
            # (Usually in workouts, you want to see the whole group if any part matches, 
            # but let's filter to just the exercise to satisfy "only shows filtered exercise")
            if exercise_filter:
                filtered_comps = [c for c in comp_list if c['exercise'].lower() == exercise_filter.lower()]
                if not filtered_comps:
                    continue
                comp_list = filtered_comps

            group_list.append({
                'id': g['id'],
                'order_index': g['order_index'],
                'rest_seconds': g['rest_seconds'],
                'components': comp_list
            })

        if not group_list and exercise_filter:
            continue

        sessions.append({
            'id': row['id'],
            'date': _date_only(row['date']),
            'name': row['title'] or 'Untitled Workout',
            'notes': row['notes'],
            'context': row['context'],
            'time_cap_minutes': row['time_cap_minutes'],
            'emom_interval': row['emom_interval'],
            'emom_duration': row['emom_duration'],
            'group_count': len(group_list),
            'component_count': sum(len(g['components']) for g in group_list),
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

@workout_bp.route('/workout_sessions/<int:ws_id>/delete', methods=['POST'])
@login_required
def delete_workout_session(ws_id):
    conn = get_db()
    user_id = session["user_id"]
    
    # Ensure the workout belongs to the user
    ws = conn.execute("SELECT id FROM workout_sessions WHERE id = %s AND user_id = %s", (ws_id, user_id)).fetchone()
    if not ws:
        conn.close()
        return jsonify({"success": False, "error": "Workout not found"}), 404
        
    conn.execute("DELETE FROM workout_sessions WHERE id = %s", (ws_id,))
    conn.commit()
    conn.close()
    
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True})
        
    flash("Workout deleted", "success")
    return redirect(url_for('workout.workout_history'))

@workout_bp.route('/workout_sessions/<int:ws_id>/edit', methods=['POST'])
@login_required
def edit_workout_session(ws_id):
    conn = get_db()
    user_id = session["user_id"]
    
    # Ensure the workout belongs to the user
    ws = conn.execute("SELECT id FROM workout_sessions WHERE id = %s AND user_id = %s", (ws_id, user_id)).fetchone()
    if not ws:
        conn.close()
        return jsonify({"success": False, "error": "Workout not found"}), 404
        
    try:
        # 1. Update main session data
        name = request.form.get("name", "Untitled Workout")
        workout_date = request.form.get("date")
        notes = request.form.get("notes")
        result = request.form.get("result")
        context = request.form.get("context")
        time_cap = request.form.get("time_cap_minutes") or None
        emom_interval = request.form.get("emom_interval") or None
        emom_duration = request.form.get("emom_duration") or None
        
        conn.execute("""
            UPDATE workout_sessions SET 
                title = %s, date = %s, notes = %s, result = %s, 
                context = %s, time_cap_minutes = %s, emom_interval = %s, emom_duration = %s
            WHERE id = %s
        """, (name, workout_date, notes, result, context, time_cap, emom_interval, emom_duration, ws_id))
        
        # 2. Update components (simplified: loop through provided IDs)
        comp_ids = request.form.getlist("comp_id[]")
        comp_exercises = request.form.getlist("comp_exercise[]")
        comp_weights = request.form.getlist("comp_weight[]")
        comp_reps = request.form.getlist("comp_reps[]")
        
        for i, cid in enumerate(comp_ids):
            ex_id, _ = resolve_exercise(conn, comp_exercises[i])
            weight = float(comp_weights[i]) if comp_weights[i] else None
            reps = int(comp_reps[i]) if comp_reps[i] else None
            
            conn.execute("""
                UPDATE set_components SET 
                    exercise_id = %s, weight_kg = %s, reps = %s
                WHERE id = %s
            """, (ex_id, weight, reps, cid))
            
        # 3. Update group rest
        group_ids = request.form.getlist("group_id[]")
        rest_mins = request.form.getlist("group_rest_min[]")
        rest_secs = request.form.getlist("group_rest_seconds[]")
        
        for i, gid in enumerate(group_ids):
            rm = int(rest_mins[i]) if rest_mins[i] else 0
            rs = int(rest_secs[i]) if rest_secs[i] else 0
            total_rest = rm * 60 + rs
            conn.execute("UPDATE set_groups SET rest_seconds = %s WHERE id = %s", (total_rest, gid))

        conn.commit()
        
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            # Return updated session for frontend JS
            return jsonify({
                "success": True, 
                "session": {
                    "id": ws_id,
                    "name": name,
                    "date": workout_date,
                    "notes": notes,
                    "result": result,
                    "context": context,
                    "time_cap_minutes": time_cap,
                    "emom_interval": emom_interval,
                    "emom_duration": emom_duration
                }
            })
            
        flash("Workout updated", "success")
        return redirect(url_for('workout.workout_history'))
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()
