from datetime import date, datetime, timedelta
from collections import defaultdict
from utils.formatting import format_weight, format_rep_label, format_set_label, format_progress_date, _date_only
from utils.progress_math import estimate_one_rep_max, _progress_session_sort_key
from db import get_db
from exercises import resolve_exercise

def _build_best_set(sets):
    if not sets:
        return None
    
    best_set = None
    for s in sets:
        try:
            w = float(s.get('weight_kg'))
            r = int(s.get('reps'))
            val = estimate_one_rep_max(w, r)
            if val is None: continue
            
            if best_set is None or val > best_set['value']:
                best_set = {
                    'weight_kg': w,
                    'reps': r,
                    'value': float(val),
                    'notes': s.get('notes')
                }
        except (TypeError, ValueError):
            continue
    return best_set

def _enrich_session_record(session):
    sets = session.get('sets') or []
    best_set = _build_best_set(sets)
    session['sets'] = sets
    session['set_count'] = len(sets)
    session['best_set'] = best_set
    session['session_value'] = best_set['value'] if best_set else None
    session['date'] = _date_only(session.get('date'))
    session['date_label'] = format_progress_date(session['date'])

    if best_set:
        weight_value = format_weight(best_set['weight_kg'])
        reps_value = best_set['reps']
        rep_label = format_rep_label(reps_value)
        set_label = format_set_label(session['set_count'])
        session['weight_kg'] = best_set['weight_kg']
        session['reps'] = reps_value
        session['weight_display'] = f"{weight_value}kg"
        session['load_label'] = f"{weight_value}kg × {reps_value} {rep_label}"
        session['summary_label'] = f"{session['set_count']} {set_label} • best {weight_value}kg × {reps_value} {rep_label}"
    else:
        session['weight_kg'] = None
        session['reps'] = None
        session['weight_display'] = '-'
        session['load_label'] = '-'
        session['summary_label'] = f"{session['set_count']} {format_set_label(session['set_count'])}"

    return session

def serialize_progress_lift(session):
    return {
        'id': session['id'],
        'lift_session_id': session['id'],
        'exercise': session['exercise'],
        'exercise_label': session['exercise'].title(),
        'weight_kg': session.get('weight_kg'),
        'weight_display': session.get('weight_display', '-'),
        'reps': session.get('reps'),
        'sets': session.get('set_count', len(session.get('sets', []))),
        'notes': session.get('notes'),
        'date': session.get('date'),
        'date_label': session.get('date_label', format_progress_date(session.get('date'))),
        'load_label': session.get('load_label', '-'),
        'summary_label': session.get('summary_label', '-'),
        'session_value': session.get('session_value'),
        'best_set': session.get('best_set'),
    }

def log_lift_service(user_id, payload):
    """
    payload: dict with exercise, date, notes, unit, sets
    sets: list of { weight_kg, reps }
    """
    from datetime import datetime
    exercise_input = payload.get('exercise', '').strip()
    date_str = payload.get('date') or datetime.now().strftime('%Y-%m-%d')
    notes = payload.get('notes')
    unit = payload.get('unit', 'kg')
    sets = payload.get('sets', [])

    if not exercise_input or not sets:
        return None, "Exercise name and at least one set are required."

    conn = get_db()
    try:
        exercise_id, exercise_name = resolve_exercise(conn, exercise_input)
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        ls_cursor = conn.execute(
            "INSERT INTO lift_sessions (user_id, exercise_id, date, notes, created_at) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (user_id, exercise_id, date_str, notes, created_at)
        )
        ls_id = ls_cursor.lastrowid

        for index, s in enumerate(sets):
            conn.execute(
                "INSERT INTO lift_sets (lift_session_id, weight_kg, reps, order_index) VALUES (%s, %s, %s, %s)",
                (ls_id, s.get('weight_kg'), s.get('reps'), index)
            )

        # Re-fetch for enrichment
        row = conn.execute("SELECT * FROM lift_sessions WHERE id = %s", (ls_id,)).fetchone()
        current_session = dict(row)
        current_session['exercise'] = exercise_name
        current_session['sets'] = sets
        _enrich_session_record(current_session)

        # Get previous session for insights
        prev_row = conn.execute(
            """
            SELECT ls.*, e.name as exercise
            FROM lift_sessions ls
            JOIN exercises e ON ls.exercise_id = e.id
            WHERE ls.user_id = %s AND ls.exercise_id = %s AND ls.date < %s
            ORDER BY ls.date DESC, ls.created_at DESC LIMIT 1
            """,
            (user_id, exercise_id, date_str)
        ).fetchone()

        prev_data = None
        if prev_row:
            prev_session = dict(prev_row)
            prev_sets = conn.execute("SELECT weight_kg, reps FROM lift_sets WHERE lift_session_id = %s", (prev_session['id'],)).fetchall()
            prev_session['sets'] = [dict(ps) for ps in prev_sets]
            _enrich_session_record(prev_session)
            prev_best = prev_session.get('best_set') or {}
            prev_data = {
                'weight': prev_best.get('weight_kg'),
                'reps': prev_best.get('reps')
            }

        conn.commit()
        
        # Calculate if this is a PR
        is_pr = False
        current_val = current_session.get('session_value') or 0
        if current_val > 0:
            all_sets = conn.execute(
                """
                SELECT s.weight_kg, s.reps 
                FROM lift_sets s
                JOIN lift_sessions ls ON s.lift_session_id = ls.id
                WHERE ls.user_id = %s AND ls.exercise_id = %s AND ls.id != %s
                """, (user_id, exercise_id, ls_id)
            ).fetchall()
            
            prev_max = 0
            for s in all_sets:
                try:
                    w = float(s['weight_kg'])
                    r = int(s['reps'])
                    val = estimate_one_rep_max(w, r)
                    if val and val > prev_max:
                        prev_max = val
                except (TypeError, ValueError):
                    pass
                    
            if current_val > prev_max:
                is_pr = True

        return {
            'current_session': current_session,
            'prev_data': prev_data,
            'is_pr': is_pr
        }, None
    finally:
        conn.close()

def _session_metric_value(session):
    try:
        if session.get('best_set'):
            return float(session['best_set']['value'])
        
        weight_value = float(session.get('weight_kg'))
        reps_value = int(session.get('reps'))
        if weight_value > 0 and reps_value > 0:
            return float(estimate_one_rep_max(weight_value, reps_value))
    except (TypeError, ValueError):
        pass
def build_progress_trend(sessions):
    if len(sessions) < 5:
        remaining = 5 - len(sessions)
        return {
            'locked': True,
            'message': f"Log {remaining} more session{'s' if remaining != 1 else ''} to view the full chart.",
            'emoji': '🔒'
        }

    session_metrics = []
    for s in sessions:
        val = _session_metric_value(s)
        if val is not None:
            session_metrics.append(val)
            
    if len(session_metrics) < 5:
        return {
            'locked': True,
            'message': "Log more sessions with weight and reps to view the full chart.",
            'emoji': '🔒'
        }

    recent_metrics = session_metrics[-5:]
    recent_max = max(recent_metrics)
    
    previous_metrics = session_metrics[:-5]
    
    if not previous_metrics:
        return {
            'locked': False,
            'message': f"🔥 Peak estimated 1RM over your last 5 sessions is {format_weight(recent_max)}kg.",
            'emoji': '🔥'
        }

    baseline_metrics = previous_metrics[-5:]
    baseline_max = max(baseline_metrics)
    
    delta = recent_max - baseline_max

    if delta > 0:
        return {
            'locked': False,
            'message': f"📈 Peak estimated 1RM is up recently (+{format_weight(delta)}kg vs previous sessions).",
            'emoji': '📈'
        }

    if delta < 0:
        return {
            'locked': False,
            'message': f"📉 Peak estimated 1RM is down recently ({format_weight(abs(delta))}kg vs previous sessions).",
            'emoji': '📉'
        }

def fetch_user_sessions(conn, user_id, exercise=None, date_range=None, limit=None, order_desc=True):
    query = """
        SELECT es.id, es.user_id, e.name as exercise, es.notes, es.date, es.created_at
        FROM lift_sessions es
        JOIN exercises e ON es.exercise_id = e.id
        WHERE es.user_id = %s
    """
    params = [user_id]

    if date_range in ('7', '30'):
        cutoff = (date.today() - timedelta(days=int(date_range))).isoformat()
        query += " AND es.date >= %s"
        params.append(cutoff)

    if exercise:
        query += " AND e.name = %s"
        params.append(exercise)

    query += f" ORDER BY es.date {'DESC' if order_desc else 'ASC'}, es.id {'DESC' if order_desc else 'ASC'}"

    if limit is not None:
        query += " LIMIT %s"
        params.append(limit)

    session_rows = conn.execute(query, params).fetchall()
    if not session_rows:
        return []

    lift_session_ids = [row['id'] for row in session_rows]
    placeholders = ','.join(['%s'] * len(lift_session_ids))
    set_rows = conn.execute(
        f"""
        SELECT lift_session_id, id as set_id, weight_kg, reps, order_index, rpe, notes
        FROM lift_sets
        WHERE lift_session_id IN ({placeholders})
        ORDER BY lift_session_id {'DESC' if order_desc else 'ASC'}, order_index ASC
        """,
        lift_session_ids,
    ).fetchall()

    sets_by_session = defaultdict(list)
    for set_row in set_rows:
        sets_by_session[set_row['lift_session_id']].append({
            'id': set_row['set_id'],
            'lift_session_id': set_row['lift_session_id'],
            'weight_kg': set_row['weight_kg'],
            'reps': set_row['reps'],
            'order_index': set_row['order_index'],
            'rpe': set_row['rpe'],
            'notes': set_row['notes'],
        })

    sessions = []
    for row in session_rows:
        session = {
            'id': row['id'],
            'user_id': row['user_id'],
            'exercise': row['exercise'],
            'notes': row['notes'],
            'date': row['date'],
            'created_at': row['created_at'],
            'sets': sets_by_session[row['id']],
        }
        _enrich_session_record(session)
        sessions.append(session)

    return sessions

def fetch_all_progress_sessions(conn, user_id, exercise=None):
    # Get standard lift sessions
    sessions = fetch_user_sessions(conn, user_id, exercise=exercise, limit=None, order_desc=True)
    for s in sessions:
        s['source'] = 'lift'
        
    # Get workout sessions with weight/reps
    query_ws_sets = """
        SELECT ws.id as lift_session_id, sc.id as set_id, sc.weight_kg, sc.reps, sc.sets as num_sets, sc.order_index, sc.notes, e.name as exercise, ws.user_id, ws.date, ws.created_at, ws.notes as session_notes
        FROM workout_sessions ws
        JOIN set_groups sg ON sg.workout_session_id = ws.id
        JOIN set_components sc ON sc.set_group_id = sg.id
        JOIN exercises e ON sc.exercise_id = e.id
        WHERE ws.user_id = %s AND sc.weight_kg IS NOT NULL AND sc.reps IS NOT NULL
    """
    params_ws_sets = [user_id]
    if exercise:
        query_ws_sets += " AND e.name = %s"
        params_ws_sets.append(exercise)
        
    set_rows_ws = conn.execute(query_ws_sets, params_ws_sets).fetchall()
    
    sessions_dict = {}
    for row in set_rows_ws:
        key = (row['lift_session_id'], row['exercise'])
        if key not in sessions_dict:
            sessions_dict[key] = {
                'id': row['lift_session_id'],
                'user_id': row['user_id'],
                'exercise': row['exercise'],
                'notes': row['session_notes'],
                'date': row['date'],
                'created_at': row['created_at'],
                'sets': [],
                'source': 'workout'
            }
        
        num_sets = row.get('num_sets') or 1
        for i in range(num_sets):
            sessions_dict[key]['sets'].append({
                'id': row['set_id'],
                'lift_session_id': row['lift_session_id'],
                'weight_kg': row['weight_kg'],
                'reps': row['reps'],
                'order_index': row['order_index'],
                'rpe': None,
                'notes': row['notes']
            })
            
    for session in sessions_dict.values():
        _enrich_session_record(session)
        sessions.append(session)
        
    # Sort descending
    sessions.sort(key=lambda x: (x['date'], x.get('created_at', '')), reverse=True)
    return sessions
