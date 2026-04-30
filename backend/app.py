from datetime import datetime, date, timedelta
from collections import defaultdict
from functools import wraps
import os
import time
from uuid import uuid4
from flask import jsonify
from flask import Flask, render_template, request, session, redirect, url_for, flash
import psycopg2
from psycopg2.extras import DictCursor
import re
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)


app = Flask(__name__)
app.config['DB_ECHO'] = False
print("🔥 APP STARTING")

@app.route('/ping')
def ping():
    return "pong"

@app.route('/api/exercises')
def api_exercises():
    return {"ok": True}

app.secret_key = "replace_this_with_a_random_secret"


@app.template_filter('format_weight')
def format_weight(value):
    if value is None:
        return "-"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}"


@app.template_filter('format_rep_label')
def format_rep_label(value):
    return 'rep' if int(value) == 1 else 'reps'


@app.template_filter('format_set_label')
def format_set_label(value):
    return 'set' if int(value) == 1 else 'sets'


@app.template_filter('format_short_date')
def format_short_date(value):
    if not value:
        return "-"
    if isinstance(value, (date, datetime)):
        return value.strftime("%b %d")

    date_value = str(value).split(' ')[0]

    try:
        return datetime.strptime(date_value, "%Y-%m-%d").strftime("%b %d")
    except (ValueError, TypeError):
        return date_value


def format_progress_date(value):
    if not value:
        return "-"

    date_value = str(value).split(' ')[0]

    try:
        parsed_date = datetime.strptime(date_value, "%Y-%m-%d")
        return f"{parsed_date.day} {parsed_date.strftime('%B %Y')}"
    except ValueError:
        return date_value


RECENT_DAYS = 90


def _date_only(value):
    if not value:
        return "-"

    return str(value).split(' ')[0]


def _build_best_set(sets):
    best_set = None
    best_value = None

    for set_entry in sets or []:
        try:
            weight_value = float(set_entry.get('weight_kg'))
            reps_value = int(set_entry.get('reps'))
            order_index = int(set_entry.get('order_index', 0))
        except (TypeError, ValueError):
            continue

        if weight_value <= 0 or reps_value <= 0:
            continue

        rm_value = estimate_one_rep_max(weight_value, reps_value)
        # If we can't estimate (e.g. too many reps), use the weight itself as a floor
        val_for_comparison = float(rm_value) if rm_value is not None else weight_value

        candidate = dict(set_entry)
        candidate['weight_kg'] = weight_value
        candidate['reps'] = reps_value
        candidate['order_index'] = order_index
        candidate['value'] = val_for_comparison

        if best_value is None or candidate['value'] > best_value:
            best_value = candidate['value']
            best_set = candidate

    return best_set


def _session_metric_value(session):
    best_set = session.get('best_set') or {}

    try:
        if best_set:
            weight_value = float(best_set.get('weight_kg'))
            reps_value = int(best_set.get('reps'))
            if weight_value > 0 and reps_value > 0:
                return float(estimate_one_rep_max(weight_value, reps_value))
    except (TypeError, ValueError):
        pass

    try:
        weight_value = float(session.get('weight_kg'))
        reps_value = int(session.get('reps'))
        if weight_value > 0 and reps_value > 0:
            return float(estimate_one_rep_max(weight_value, reps_value))
    except (TypeError, ValueError):
        pass

    return session.get('session_value')


def _clean_text_value(value):
    if value is None:
        return ''
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _extract_session_payload(req):
    payload = req.get_json(silent=True)
    if isinstance(payload, dict):
        exercise = _clean_text_value(payload.get('exercise'))
        date_str = _clean_text_value(payload.get('date'))
        notes = _clean_text_value(payload.get('notes'))
        unit = _clean_text_value(payload.get('unit')) or 'kg'
        raw_sets = payload.get('sets', []) or []
    else:
        exercise = _clean_text_value(req.form.get('exercise'))
        date_str = _clean_text_value(req.form.get('date'))
        notes = _clean_text_value(req.form.get('notes'))
        unit = _clean_text_value(req.form.get('unit', 'kg')) or 'kg'

        weight_values = req.form.getlist('weight_kg[]') or req.form.getlist('weight_kg') or req.form.getlist('weight')
        reps_values = req.form.getlist('reps[]') or req.form.getlist('reps')

        raw_sets = []
        if weight_values and reps_values and len(weight_values) == len(reps_values):
            raw_sets = [
                {'weight_kg': weight_values[index], 'reps': reps_values[index]}
                for index in range(len(weight_values))
            ]
        else:
            single_weight = req.form.get('weight_kg', '').strip() or req.form.get('weight', '').strip()
            single_reps = req.form.get('reps', '').strip()
            if single_weight and single_reps:
                try:
                    set_count = int(req.form.get('sets', '').strip() or 1)
                except (TypeError, ValueError):
                    set_count = 1
                set_count = max(1, set_count)
                raw_sets = [{'weight_kg': single_weight, 'reps': single_reps} for _ in range(set_count)]

    return {
        'exercise': exercise,
        'date': date_str,
        'notes': notes,
        'unit': unit,
        'sets': raw_sets,
    }


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

    return {
        'locked': False,
        'message': f"✨ Peak estimated 1RM is steady ({format_weight(recent_max)}kg).",
        'emoji': '✨'
    }


def estimate_one_rep_max(weight_kg, reps):
    if weight_kg is None or reps is None:
        return None
    
    try:
        w = float(weight_kg)
        r = float(reps)
    except (TypeError, ValueError):
        return None

    if w <= 0 or r < 1:
        return None

    # We limit estimation to 20 reps for better accuracy
    # For sets > 20 reps, we just return the weight as a conservative baseline
    if r > 20:
        return w
    
    if r == 1:
        return w

    # Epley formula: 1RM = W * (1 + r/30)
    # Using r-1 to ensure 1RM of 1 rep is just the weight itself
    return w * (1 + (r - 1) / 30.0)


def estimate_rep_max_from_one_rm(one_rm, target_reps):
    if one_rm is None or target_reps is None:
        return None

    try:
        orm = float(one_rm)
        r = float(target_reps)
    except (TypeError, ValueError):
        return None

    if orm <= 0 or r < 1:
        return None

    # Inverse Epley: W = 1RM / (1 + (r-1)/30)
    return orm / (1 + (r - 1) / 30.0)


def _progress_date_sort_key(value):
    parsed_date = _progress_date_value(value)

    if parsed_date is None:
        return datetime.min

    return datetime.combine(parsed_date, datetime.min.time())


def _progress_date_value(value):
    date_value = str(value).split(' ')[0]

    try:
        return datetime.strptime(date_value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _progress_session_sort_key(session):
    return (_progress_date_sort_key(session['date']), session['id'])


def _build_rm_point(session):
    best_set = session.get('best_set') or {}
    weight_kg = best_set.get('weight_kg', session.get('weight_kg'))
    reps = best_set.get('reps', session.get('reps'))

    try:
        weight_value = float(weight_kg)
        reps_value = int(reps)
    except (TypeError, ValueError):
        return None

    if weight_value <= 0 or reps_value < 1:
        return None

    date_value = str(session['date']).split(' ')[0]
    rm_value = estimate_one_rep_max(weight_value, reps_value)

    if rm_value is None:
        return None

    return {
        'session': session,
        'kind': 'actual' if reps_value == 1 else 'estimated',
        'weight_kg': weight_value,
        'reps': reps_value,
        'value': float(rm_value),
        'date': date_value,
        'date_label': format_progress_date(date_value),
        'sort_key': _progress_session_sort_key(session),
    }


def _format_rm_point_meta(point, target_rm=1, kind=None):
    if not point:
        return '-'

    rep_label = format_rep_label(point['reps'])
    resolved_kind = kind or point['kind']
    source_label = 'Actual' if resolved_kind == 'actual' else 'Estimated'
    load_label = f"{format_weight(point['weight_kg'])}kg × {point['reps']} {rep_label}"

    return f"{source_label} {target_rm}RM: {load_label} • {point['date_label']}"


def _build_daily_best_rm_points(rm_points):
    grouped_points = defaultdict(list)

    for point in rm_points:
        grouped_points[point['date']].append(point)

    daily_best_points = []
    for date_value in sorted(grouped_points.keys(), key=_progress_date_sort_key):
        day_points = grouped_points[date_value]
        best_point = max(day_points, key=lambda point: (point['value'], point['sort_key']))
        daily_best_points.append(best_point)

    return daily_best_points


def build_estimated_rm_profile(sessions):
    sessions_sorted = sorted(sessions, key=_progress_session_sort_key)
    rm_points = []

    for session in sessions_sorted:
        rm_point = _build_rm_point(session)
        if rm_point is not None:
            rm_points.append(rm_point)

    if not rm_points:
        return []

    daily_best_points = _build_daily_best_rm_points(rm_points)

    if not daily_best_points:
        return []

    today = date.today()
    recent_points = []

    for point in daily_best_points:
        point_date = _progress_date_value(point['date'])

        if point_date is None:
            continue

        days_old = (today - point_date).days
        if 0 <= days_old <= RECENT_DAYS:
            recent_points.append(point)

    if not recent_points:
        recent_points = daily_best_points

    if not recent_points:
        return []

    best_source = max(recent_points, key=lambda point: (point['value'], point['sort_key']))
    best_one_rm_value = float(best_source['value'])

    # Find the best actual lift for each RM target (1-5) if they exist
    best_actuals = {}
    for point in recent_points:
        r = point['reps']
        if 1 <= r <= 20:
            if r not in best_actuals or point['weight_kg'] > best_actuals[r]['weight_kg']:
                best_actuals[r] = point

    rm_profile = []

    for target_rm in range(1, 6):
        # Prefer actual best for this target if it's better than (or equal to) the estimate from our 1RM
        # or if the estimate is just too far off.
        actual = best_actuals.get(target_rm)
        estimated_val = estimate_rep_max_from_one_rm(best_one_rm_value, target_rm)
        
        # Decide whether to use actual or estimated
        use_actual = False
        if actual:
            if estimated_val is None or actual['weight_kg'] >= (estimated_val * 0.9):
                use_actual = True
        
        if use_actual and actual:
            rm_profile.append({
                'rm': target_rm,
                'value': float(actual['weight_kg']),
                'display': f"{format_weight(actual['weight_kg'])}kg",
                'kind': 'actual',
                'date': actual['date'],
                'date_label': actual['date_label'],
                'meta': _format_rm_point_meta(actual, target_rm=target_rm, kind='actual'),
            })
        elif estimated_val is not None:
            rm_profile.append({
                'rm': target_rm,
                'value': float(estimated_val),
                'display': f"{format_weight(estimated_val)}kg",
                'kind': 'estimated',
                'date': best_source['date'],
                'date_label': best_source['date_label'],
                'meta': _format_rm_point_meta(best_source, target_rm=target_rm, kind='estimated'),
            })
        else:
            # Fallback if somehow both are None
            rm_profile.append({
                'rm': target_rm,
                'value': 0,
                'display': '-',
                'kind': 'estimated',
                'date': '-',
                'date_label': '-',
                'meta': '-',
            })

    return rm_profile


def build_pr_gallery(sessions):
    best_entries = {}

    for session in sessions:
        for set_entry in session.get('sets', []):
            try:
                weight_value = float(set_entry.get('weight_kg'))
                reps_value = int(set_entry.get('reps'))
            except (TypeError, ValueError):
                continue

            if weight_value <= 0 or reps_value <= 0:
                continue

            rm_value = estimate_one_rep_max(weight_value, reps_value)
            if rm_value is None:
                continue

            exercise = session['exercise']
            candidate = {
                'exercise': exercise,
                'exercise_label': exercise.title(),
                'weight_kg': weight_value,
                'weight_display': f"{format_weight(weight_value)}kg",
                'date': session['date'],
                'date_label': format_progress_date(session['date']),
                'reps': reps_value,
                'sets': 1,
                'session_set_count': session.get('set_count', len(session.get('sets', []))),
                'notes': set_entry.get('notes') or session.get('notes'),
                'lift_session_id': session['id'],
                'set_order_index': set_entry.get('order_index', 0),
                'value': float(rm_value),
            }

            current = best_entries.get(exercise)
            if current is None or candidate['weight_kg'] > current['weight_kg'] or (
                candidate['weight_kg'] == current['weight_kg'] and (
                    candidate['date'] > current['date'] or (
                        candidate['date'] == current['date'] and candidate['set_order_index'] > current['set_order_index']
                    )
                )
            ):
                best_entries[exercise] = candidate

    entries = sorted(best_entries.values(), key=lambda item: (-item['weight_kg'], item['exercise_label']))
    heaviest_pr = entries[0] if entries else None
    most_recent_pr = max(entries, key=lambda item: item['date']) if entries else None

    return {
        'entries': entries,
        'highlights': [
            {
                'label': 'PRs tracked',
                'value': len(entries),
                'detail': 'Exercises with best lifts'
            },
            {
                'label': 'Heaviest PR',
                'value': heaviest_pr['weight_display'] if heaviest_pr else '-',
                'detail': heaviest_pr['exercise_label'] if heaviest_pr else 'No records yet'
            },
            {
                'label': 'Most recent PR',
                'value': most_recent_pr['exercise_label'] if most_recent_pr else '-',
                'detail': most_recent_pr['date_label'] if most_recent_pr else 'No records yet'
            },
        ],
        'heaviest_pr_exercise': heaviest_pr['exercise'] if heaviest_pr else None,
    }


# --- DATABASE HELPERS ---


def migrate_legacy_lifts_to_sessions(conn):
    if not _table_exists(conn, 'lifts'):
        return

    legacy_rows = conn.execute(
        "SELECT id, user_id, exercise, weight_kg, reps, sets, notes, date FROM lifts ORDER BY date ASC, id ASC"
    ).fetchall()

    for row in legacy_rows:
        weight_kg = row['weight_kg']
        reps = row['reps']

        if weight_kg is None or reps is None:
            continue

        try:
            weight_value = float(weight_kg)
            reps_value = int(reps)
        except (TypeError, ValueError):
            continue

        if weight_value <= 0 or reps_value <= 0:
            continue

        try:
            set_count = int(row['sets']) if row['sets'] is not None else 1
        except (TypeError, ValueError):
            set_count = 1

        if set_count < 1:
            set_count = 1

        session_date = _date_only(row['date'])
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor = conn.execute(
            """
            INSERT INTO lift_sessions (user_id, exercise, notes, date, created_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (row['user_id'], row['exercise'], row['notes'], session_date, created_at)
        )
        lift_session_id = cursor.lastrowid

        for order_index in range(set_count):
            conn.execute(
                """
                INSERT INTO lift_sets (lift_session_id, weight_kg, reps, order_index, rpe, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (lift_session_id, weight_value, reps_value, order_index, None, None)
            )

    conn.execute("DROP TABLE lifts")


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
            'sets': sets_by_session.get(row['id'], []),
        }
        sessions.append(_enrich_session_record(session))

    return sessions


def fetch_workout_sessions_as_lifts(conn, user_id, date_range=None, limit=None, order_desc=True):
    """
    Pulls exercises from workout_sessions → set_groups → set_components
    and returns them in the same enriched format as fetch_user_sessions(),
    so the progress page can merge both data sources transparently.
    """
    params = [user_id]
    date_clause = ""
    if date_range in ('7', '30'):
        cutoff = (date.today() - timedelta(days=int(date_range))).isoformat()
        date_clause = " AND ws.date >= %s"
        params.append(cutoff)

    rows = conn.execute(f"""
        SELECT DISTINCT sc.exercise_id, e.name AS exercise_name,
                        ws.id AS ws_id, ws.date, ws.notes AS ws_notes
        FROM workout_sessions ws
        JOIN set_groups sg ON sg.workout_session_id = ws.id
        JOIN set_components sc ON sc.set_group_id = sg.id
        JOIN exercises e ON sc.exercise_id = e.id
        WHERE ws.user_id = %s {date_clause}
        ORDER BY ws.date {'DESC' if order_desc else 'ASC'}, ws.id {'DESC' if order_desc else 'ASC'}
    """, params).fetchall()

    # Group by (exercise_id, ws_id) to build one synthetic session per exercise per workout
    from collections import OrderedDict
    grouped = OrderedDict()
    for row in rows:
        key = (row['exercise_id'], row['ws_id'])
        if key not in grouped:
            grouped[key] = {
                'exercise_name': row['exercise_name'],
                'ws_id': row['ws_id'],
                'date': row['date'],
                'notes': row['ws_notes'],
                'sets': []
            }

    # Fetch all set_components for these workout_sessions in one query
    ws_ids = list({r['ws_id'] for r in rows})
    if not ws_ids:
        return []

    placeholders = ','.join(['%s'] * len(ws_ids))
    comp_rows = conn.execute(f"""
        SELECT sg.workout_session_id AS ws_id,
               sc.exercise_id,
               COALESCE(sc.weight_kg, sg.shared_weight_kg) AS weight_kg,
               sc.reps
        FROM set_components sc
        JOIN set_groups sg ON sc.set_group_id = sg.id
        WHERE sg.workout_session_id IN ({placeholders})
          AND sc.exercise_id IS NOT NULL
    """, ws_ids).fetchall()

    for comp in comp_rows:
        key = (comp['exercise_id'], comp['ws_id'])
        if key in grouped:
            w = comp['weight_kg']
            r = comp['reps']
            if w is not None and r is not None and float(w) > 0 and int(r) > 0:
                grouped[key]['sets'].append({
                    'id': None,
                    'lift_session_id': None,
                    'weight_kg': float(w),
                    'reps': int(r),
                    'order_index': 0,
                    'rpe': None,
                    'notes': None,
                })

    sessions = []
    synthetic_id = -1  # negative IDs won't collide with real exercise_session IDs
    for key, data in grouped.items():
        if not data['sets']:
            continue
        session = {
            'id': synthetic_id,
            'user_id': user_id,
            'exercise': data['exercise_name'],
            'notes': data['notes'],
            'date': data['date'],
            'created_at': data['date'],
            'sets': data['sets'],
        }
        synthetic_id -= 1
        sessions.append(_enrich_session_record(session))

    if limit is not None:
        sessions = sessions[:limit]

    return sessions


def fetch_session_by_id(conn, lift_session_id, user_id):
    sessions = fetch_user_sessions(conn, user_id, limit=None, order_desc=True)
    for session in sessions:
        if session['id'] == lift_session_id:
            return session
    return None


@app.context_processor
def inject_profile_photo():
    photo_path = None
    display_name = None
    if session.get('user_id'):
        try:
            conn = get_db()
            profile = conn.execute(
                'SELECT photo_path FROM user_profiles WHERE user_id = %s',
                (session['user_id'],)
            ).fetchone()
            if profile and profile['photo_path']:
                photo_path = profile['photo_path']
            
            user = conn.execute(
                'SELECT display_name FROM users WHERE id = %s',
                (session['user_id'],)
            ).fetchone()
            if user and user['display_name']:
                display_name = user['display_name']
            else:
                display_name = session.get('username', '')
            
            conn.close()
        except Exception as e:
            print(f"⚠️ Error in context processor: {e}")
            display_name = session.get('username', 'User')
    return {'profile_photo': photo_path, 'display_name': display_name}

# --- EXERCISE LISTS BY MUSCLE GROUP ---
# These are now loaded from the database
EXERCISES = {}
ALL_EXERCISES = []
CALORIE_EXERCISES = []
# canonical_key -> display_name, populated by load_exercises_from_db()
EXERCISE_BY_KEY = {}

# --- EXERCISE ALIASES (for normalizing user input) ---
EXERCISE_ALIASES = {
    # Dip variations
    "dips": "Dip",
    "dip": "Dip",
    "chest dip": "Chest Dip",
    "chest dips": "Chest Dip",
    "parallel bar dip": "Parallel Bar Dip",
    "parallel bar dips": "Parallel Bar Dip",
    "ring dip": "Ring Dip",
    "ring dips": "Ring Dip",
    "tricep dip": "Tricep Dip",
    "tricep dips": "Tricep Dip",
    "bench dip": "Bench Dip",
    "bench dips": "Bench Dip",
    "korean dip": "Korean Dip",
    "korean dips": "Korean Dip",
    
    # Pull-up variations
    "pullups": "Pull-up",
    "pull ups": "Pull-up",
    "pullup": "Pull-up",
    "pull up": "Pull-up",
    "pull-ups": "Pull-up",
    "chinups": "Chin-up",
    "chin ups": "Chin-up",
    "chinup": "Chin-up",
    "chin up": "Chin-up",
    "chin-ups": "Chin-up",
    
    # Push-up variations
    "pushups": "Push-up",
    "push ups": "Push-up",
    "pushup": "Push-up",
    "push up": "Push-up",
    "push-ups": "Push-up",
    
    # Air bike / Assault bike
    "air bike": "Assault Bike",
    "airbike": "Assault Bike",
    "assaultbike": "Assault Bike",
    
    # Squat variations
    "squats": "Squat",
    "back squats": "Back Squat",
    "front squats": "Front Squat",
    "deadlifts": "Deadlift",
    "bench press": "Bench Press",
    "bench presses": "Bench Press",
    "overhead press": "Overhead Press",
    "ohp": "Overhead Press",
    
    # Row variations
    "barbell rows": "Barbell Row",
    "dumbbell rows": "Dumbbell Row",
    "t-bar rows": "T-Bar Row",
    
    # Muscle up
    "muscle ups": "Muscle-up",
    "muscleup": "Muscle-up",
    "muscleups": "Muscle-up",
    "bar muscle ups": "Bar Muscle-up",
    "bar muscleup": "Bar Muscle-up",
    "ring muscle ups": "Ring Muscle-up",
    "ring muscleup": "Ring Muscle-up",
    
    # Other common aliases
    "bicep curls": "Bicep Curl",
    "hammer curls": "Hammer Curl",
    "tricep pushdowns": "Tricep Pushdown",
    "cable rows": "Cable Row",
    "lat pulldowns": "Lat Pulldown",
    "leg extensions": "Leg Extension",
    "leg curls": "Leg Curl",
    "calf raises": "Calf Raise",
    "face pulls": "Face Pull",
    "lateral raises": "Lateral Raise",
    "shrugs": "Shrug",
    "planks": "Plank",
    "burpees": "Burpee",
    "thrusters": "Thruster",
    "box jumps": "Box Jump",
    "wall balls": "Wall Ball",
    "kettlebell swings": "Kettlebell Swing",
    "double unders": "Double Under",
    "doubleunder": "Double Under",
    "doubleunders": "Double Under",
    "cleans": "Clean",
    "snatches": "Snatch",
    "jerks": "Jerk",
}

def _friendly_display_name(user_input):
    """Pick a readable display string for a previously-unseen exercise."""
    cleaned = normalize(user_input)
    if cleaned in EXERCISE_ALIASES:
        return EXERCISE_ALIASES[cleaned]
    return (user_input or '').strip()


def normalize_exercise_input(user_input):
    """Back-compat shim: return a canonical display name for free-text input.

    Prefer resolve_exercise() for new code — it returns the FK id alongside
    the display name in a single round-trip. This function remains for any
    template/helper that only needs the display form.
    """
    if not user_input:
        return None
    key = canonical_exercise_key(user_input)
    if not key:
        return None
    if key in EXERCISE_BY_KEY:
        return EXERCISE_BY_KEY[key]
    return _friendly_display_name(user_input) or None

# --- DATABASE ---

class DBCursor:
    """Wraps a psycopg2 cursor. Provides .fetchall(), .fetchone(),
    .lastrowid (populated after INSERT ... RETURNING id), and .rowcount."""

    def __init__(self, cursor, lastrowid=None):
        self._cursor = cursor
        self.lastrowid = lastrowid

    def fetchall(self):
        return self._cursor.fetchall() or []

    def fetchone(self):
        return self._cursor.fetchone()

    def __iter__(self):
        return iter(self._cursor)

    @property
    def rowcount(self):
        return self._cursor.rowcount


class DBConnection:
    """Thin wrapper around a psycopg2 connection.
    Provides conn.execute() / conn.executemany() using native PostgreSQL SQL.
    All queries must use %s placeholders."""

    def __init__(self, conn):
        self.conn = conn

    def execute(self, query, params=None):
        cur = self.conn.cursor(cursor_factory=DictCursor)
        try:
            cur.execute(query, list(params) if params else None)
        except Exception as e:
            print(f"❌ DATABASE ERROR: {e}")
            print(f"QUERY: {query}")
            self.conn.rollback()
            raise
        self.conn.commit()

        # Capture lastrowid if the query used RETURNING id
        lastrowid = None
        if query.strip().upper().startswith("INSERT") and "RETURNING ID" in query.upper():
            row = cur.fetchone()
            if row:
                lastrowid = row[0]

        return DBCursor(cur, lastrowid)

    def executemany(self, query, params_list):
        cur = self.conn.cursor(cursor_factory=DictCursor)
        try:
            cur.executemany(query, params_list)
        except Exception as e:
            print(f"❌ DATABASE ERROR (executemany): {e}")
            print(f"QUERY: {query}")
            self.conn.rollback()
            raise
        self.conn.commit()
        return DBCursor(cur)

    def commit(self):   self.conn.commit()
    def rollback(self): self.conn.rollback()
    def close(self):    self.conn.close()


def get_db():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    conn = psycopg2.connect(database_url.strip())
    print("✅ Database connected.")
    return DBConnection(conn)

def get_all_exercises():
    conn = get_db()
    exercises = [row[0] for row in conn.execute("SELECT name FROM exercises ORDER BY name").fetchall()]
    conn.close()
    return exercises

def get_calorie_exercises():
    conn = get_db()
    exercises = [row[0] for row in conn.execute("SELECT name FROM exercises ORDER BY name").fetchall()]
    conn.close()
    return exercises

def get_exercises_by_category():
    conn = get_db()
    exercises_by_category = {}
    for row in conn.execute("SELECT category, name FROM exercises ORDER BY category, name").fetchall():
        category = row[0]
        exercise = row[1]
        if category not in exercises_by_category:
            exercises_by_category[category] = []
        exercises_by_category[category].append(exercise)
    conn.close()
    return exercises_by_category


def normalize(name):
    if not name:
        return ''
    return ' '.join(name.lower().strip().replace('-', ' ').replace('_', ' ').split())


def canonical_exercise_key(name):
    """Single source-of-truth key for matching exercises.

    1. Normalize the raw input (lowercase, trim, fold hyphen/underscore).
    2. If that matches an alias, return the normalized alias target; this
       collapses plural/spacing variants (e.g. 'pull ups' -> 'pull up').
    3. Otherwise return the normalized input itself.
    """
    if not name:
        return ''
    normalized = normalize(name)
    if not normalized:
        return ''
    alias_target = EXERCISE_ALIASES.get(normalized)
    if alias_target:
        return normalize(alias_target)
    return normalized


def _sql_normalized_name(column_expression):
    return f"LOWER(TRIM(REPLACE(REPLACE({column_expression}, '-', ' '), '_', ' ')))"


def load_exercises_from_db():
    """Populate in-memory caches from the exercises table in a single pass.

    EXERCISE_BY_KEY is the authoritative canonical_key -> display_name map
    used by normalize_exercise_input(). All derived caches (ALL_EXERCISES,
    EXERCISES, CALORIE_EXERCISES) are built from the same query, so they
    cannot drift out of sync with one another.
    """
    global EXERCISES, ALL_EXERCISES, CALORIE_EXERCISES, EXERCISE_BY_KEY

    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT name, category, canonical_key "
            "FROM exercises ORDER BY category, name"
        ).fetchall()
    finally:
        conn.close()

    by_key = {}
    all_names = []
    calorie_names = []
    by_category = {}

    for row in rows:
        name = row['name']
        key = row['canonical_key'] or canonical_exercise_key(name)
        if not key or key in by_key:
            continue
        by_key[key] = name
        all_names.append(name)
        by_category.setdefault(row['category'], []).append(name)

    EXERCISE_BY_KEY = by_key
    ALL_EXERCISES = all_names
    CALORIE_EXERCISES = calorie_names
    EXERCISES = by_category


def resolve_exercise(conn, user_input):
    """Single entry point for matching or creating an exercise.

    Computes the canonical_key exactly once, does one UNIQUE-index lookup,
    and inserts a new row only if no match exists. On insert, updates the
    in-memory caches incrementally instead of reloading the full catalog.

    Returns (exercise_id, display_name), or (None, None) if input is empty.
    """
    if not user_input:
        return None, None
    key = canonical_exercise_key(user_input)
    if not key:
        return None, None

    row = conn.execute(
        'SELECT id, name FROM exercises WHERE canonical_key = %s', (key,)
    ).fetchone()
    if row:
        return row['id'], row['name']

    display_name = _friendly_display_name(user_input) or key
    cursor = conn.execute(
        'INSERT INTO exercises (name, category, canonical_key) '
        'VALUES (%s, %s, %s) RETURNING id',
        (display_name, 'Other', key),
    )
    # Incrementally refresh the in-memory caches so the next lookup is a cache hit.
    EXERCISE_BY_KEY[key] = display_name
    ALL_EXERCISES.append(display_name)
    EXERCISES.setdefault('Other', []).append(display_name)
    return cursor.lastrowid, display_name

def populate_exercises_if_needed():
    """Seed exercises table with baseline catalog if empty."""
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM exercises").fetchone()[0]
    
    if count == 0:
        # Seed catalog: one entry per canonical exercise, grouped by its
        # primary category. Categories are ordered the same way the old flat
        # list was, so the "first-category-wins" assignment is preserved.
        # Cross-category duplicates have been removed at the source, so no
        # runtime dedup pass is required here.
        seed_by_category = {
            "Legs": [
                "front squat", "back squat", "sumo squat", "goblet squat",
                "overhead squat", "deadlift", "conventional deadlift",
                "sumo deadlift", "romanian deadlift", "lunge", "walking lunge",
                "reverse lunge", "bulgarian split squat", "jumping lunge",
                "leg press", "hack squat", "leg extension", "leg curl",
                "sissy squat", "calf raise", "seated calf raise",
                "standing calf raise", "donkey calf raise", "box squat",
                "zercher squat", "good morning", "hip thrust", "glute bridge",
            ],
            "Chest": [
                "bench press", "flat bench press", "incline bench press",
                "decline bench press", "dumbbell bench press",
                "incline dumbbell press", "decline dumbbell press",
                "close grip bench press", "dips", "chest dips",
                "parallel bar dips", "ring dips", "push-up", "wide push-up",
                "close grip push-up", "decline push-up", "clapping push-up",
                "chest fly", "dumbbell fly", "cable fly", "pec deck",
                "incline fly", "dumbbell pullover", "cable crossover",
                "floor press", "board press",
            ],
            "Back": [
                "pull-up", "chin-up", "wide grip pull-up", "close grip pull-up",
                "mixed grip pull-up", "lat pulldown", "wide grip pulldown",
                "close grip pulldown", "reverse grip pulldown", "bent over row",
                "barbell row", "dumbbell row", "t-bar row", "pendlay row",
                "seated row", "cable row", "machine row", "single arm row",
                "snatch grip deadlift", "hyperextension", "back extension",
                "reverse hyper", "face pull", "reverse fly",
                "dumbbell reverse fly", "renegade row",
            ],
            "Shoulders": [
                "overhead press", "military press", "strict press", "push press",
                "dumbbell shoulder press", "seated dumbbell press",
                "arnold press", "landmine press", "lateral raise",
                "side lateral raise", "cable lateral raise",
                "bent over lateral raise", "front raise", "dumbbell front raise",
                "cable front raise", "plate raise", "rear delt fly",
                "bent over rear delt fly", "reverse pec deck", "upright row",
                "barbell upright row", "dumbbell upright row",
                "kettlebell upright row", "shrug", "barbell shrug",
                "dumbbell shrug", "cable shrug",
            ],
            "Arms": [
                "bicep curl", "barbell curl", "dumbbell curl", "hammer curl",
                "preacher curl", "concentration curl", "cable curl",
                "incline dumbbell curl", "reverse curl", "tricep pushdown",
                "cable tricep pushdown", "rope tricep pushdown", "v-bar pushdown",
                "overhead tricep extension", "dumbbell overhead extension",
                "cable overhead extension", "skull crusher",
                "lying tricep extension", "tricep dip", "bench dip",
            ],
            "Core": [
                "plank", "side plank", "plank with shoulder tap",
                "plank with reach", "crunch", "sit-up", "reverse crunch",
                "hanging leg raise", "toes to bar", "leg raise",
                "lying leg raise", "hanging knee raise", "knee up",
                "russian twist", "cable russian twist", "medicine ball twist",
                "wood chop", "dead bug", "bird dog", "superman",
                "hollow body hold", "ab wheel rollout", "cable crunch",
                "machine crunch", "dragon flag",
            ],
            "CrossFit": [
                "thruster", "wall ball", "box jump", "double under",
                "single under", "triple under", "kettlebell swing",
                "kettlebell snatch", "kettlebell clean", "kettlebell jerk",
                "clean", "power clean", "hang clean", "squat clean",
                "split clean", "jerk", "push jerk", "split jerk", "squat jerk",
                "snatch", "power snatch", "hang snatch", "squat snatch",
                "split snatch", "burpee", "burpee box jump", "burpee pull-up",
                "chest to bar pull-up", "chest to bar", "muscle up",
                "bar muscle up", "ring muscle up", "strict muscle up",
                "handstand push-up", "handstand walk", "wall walk", "pistols",
                "knees to elbow", "rope climb", "sled push", "sled pull",
                "row erg", "meter row", "bike erg", "ski erg", "assault bike",
                "air bike",
            ],
            "Calisthenics": [
                "archer pull-up", "false grip muscle up", "dip", "korean dip",
                "diamond push-up", "archer push-up", "pike push-up",
                "wall handstand push-up", "free handstand push-up",
                "front lever", "back lever", "planche", "straddle planche",
                "full planche", "human flag", "side flag", "l-sit", "v-sit",
                "pistol squat", "shrimp squat", "cossack squat",
                "clapping pull-up", "one arm push-up", "one arm pull-up",
                "l-sit to v-sit",
            ],
            "Full Body": [
                "clean and jerk", "battle rope", "tire flip", "sledge hammer",
                "farmers walk", "suitcase carry", "overhead carry", "yoke walk",
                "prowler push",
            ],
        }
        # Canonical keys whose rows should be flagged as calorie-based cardio.
        calorie_keys = {
            "row erg", "meter row", "bike erg", "ski erg",
            "assault bike", "air bike",
        }

        seen_keys = set()
        rows = []
        for category, names in seed_by_category.items():
            for name in names:
                key = canonical_exercise_key(name)
                if not key or key in seen_keys:
                    continue
                seen_keys.add(key)
                rows.append((name, category, key))

        conn.executemany(
            "INSERT INTO exercises (name, category, canonical_key) "
            "VALUES (%s, %s, %s)",
            rows,
        )
        conn.commit()
    
    conn.close()

def clean_up_duplicate_exercises():
    """Collapse rows that share a canonical_key into a single row.

    Keeps the lowest id per key, repoints lift_sessions.exercise_id to
    that survivor, writes canonical_key on the survivor if missing, and
    deletes the extras. Safe to run repeatedly.
    """
    conn = get_db()
    
    # Early-exit guard: check if any duplicates actually exist using SQL
    # before doing a full table fetch and Python-side processing.
    dupes = conn.execute('''
        SELECT canonical_key, COUNT(*) as cnt 
        FROM exercises 
        WHERE canonical_key IS NOT NULL AND canonical_key != ''
        GROUP BY canonical_key 
        HAVING COUNT(*) > 1
        LIMIT 1
    ''').fetchone()
    
    if not dupes:
        conn.close()
        return

    try:
        exercises = conn.execute(
            "SELECT id, name, canonical_key FROM exercises ORDER BY id"
        ).fetchall()
        grouped = {}

        for row in exercises:
            key = row['canonical_key'] or canonical_exercise_key(row['name'])
            if not key:
                continue
            grouped.setdefault(key, []).append(row)

        for key, rows in grouped.items():
            keep_id = rows[0]['id']
            # Ensure the survivor carries the canonical_key explicitly.
            if not rows[0]['canonical_key']:
                conn.execute(
                    "UPDATE exercises SET canonical_key = %s WHERE id = %s",
                    (key, keep_id),
                )
            if len(rows) < 2:
                continue

            duplicate_ids = [row['id'] for row in rows[1:]]
            placeholders = ','.join('%s' for _ in duplicate_ids)
            conn.execute(
                f"UPDATE lift_sessions SET exercise_id = %s "
                f"WHERE exercise_id IN ({placeholders})",
                [keep_id, *duplicate_ids],
            )
            conn.execute(
                f"DELETE FROM exercises WHERE id IN ({placeholders})",
                duplicate_ids,
            )

        conn.commit()
    finally:
        conn.close()


def _migrate_exercise_canonical_key():
    """Ensure exercises.canonical_key exists, is backfilled, and is UNIQUE.

    Idempotent: safe to call on every startup. Handles legacy databases
    that predate the canonical_key column.
    """
    conn = get_db()
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(exercises)").fetchall()]
        if 'canonical_key' not in cols:
            conn.execute("ALTER TABLE exercises ADD COLUMN canonical_key TEXT")
            conn.commit()

        # Backfill any NULL/empty canonical_key values from the display name.
        rows = conn.execute(
            "SELECT id, name FROM exercises "
            "WHERE canonical_key IS NULL OR canonical_key = ''"
        ).fetchall()
        for row in rows:
            key = canonical_exercise_key(row['name'])
            if not key:
                continue
            conn.execute(
                "UPDATE exercises SET canonical_key = %s WHERE id = %s",
                (key, row['id']),
            )
        conn.commit()
    finally:
        conn.close()


def _ensure_canonical_key_unique_index():
    """Create the UNIQUE index on canonical_key after dedupe has run."""
    conn = get_db()
    try:
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_exercises_canonical_key "
            "ON exercises(canonical_key)"
        )
        conn.commit()
    finally:
        conn.close()

# init_db()  # Commented out because we are using Supabase now

def get_user(username):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE username = %s", (username,)).fetchone()
    conn.close()
    return row

def create_user(username, password):
    conn = get_db()
    conn.execute(
        "INSERT INTO users (username, password_hash, display_name, created_at) VALUES (%s, %s, %s, %s)",
        (username, generate_password_hash(password), username, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()
    return get_user(username)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# --- ROUTES ---
@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    if not username or not password:
        return render_template("login.html", error="Username and password required")
    user = get_user(username)
    if user:
        if not check_password_hash(user["password_hash"], password):
            return render_template("login.html", error="Invalid credentials")
    else:
        user = create_user(username, password)
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    user_id = session["user_id"]

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_start_str = week_start.isoformat()
    today_str = today.isoformat()

    weekly_sessions_row = conn.execute(
        '''
        SELECT COUNT(DISTINCT workout_day) AS weekly_sessions
        FROM (
            SELECT date::date::text AS workout_day
            FROM lift_sessions
            WHERE user_id = %s AND date::date::text BETWEEN %s AND %s
            UNION
            SELECT date::date::text AS workout_day
            FROM workout_sessions
            WHERE user_id = %s AND date::date::text BETWEEN %s AND %s
            UNION
            SELECT date::date::text AS workout_day
            FROM runs
            WHERE user_id = %s AND date::date::text BETWEEN %s AND %s
        ) AS combined_workouts
        ''',
        (user_id, week_start_str, today_str, user_id, week_start_str, today_str, user_id, week_start_str, today_str)
    ).fetchone()
    weekly_sessions = weekly_sessions_row['weekly_sessions'] if weekly_sessions_row else 0

    activities = []

    # 1. LIFTS (from lift_sessions)
    lifts_this_week = conn.execute('''
        SELECT es.id, es.date, e.name as title, es.notes
        FROM lift_sessions es
        JOIN exercises e ON es.exercise_id = e.id
        WHERE es.user_id = %s AND es.date BETWEEN %s AND %s
    ''', (user_id, week_start_str, today_str)).fetchall()

    lift_session_ids = [l['id'] for l in lifts_this_week]
    sets_by_session = defaultdict(list)
    if lift_session_ids:
        placeholders = ','.join(['%s'] * len(lift_session_ids))
        all_sets = conn.execute(f'''
            SELECT lift_session_id, weight_kg, reps, order_index 
            FROM lift_sets
            WHERE lift_session_id IN ({placeholders})
            ORDER BY order_index ASC
        ''', lift_session_ids).fetchall()
        for s in all_sets:
            sets_by_session[s['lift_session_id']].append(s)

    for lift in lifts_this_week:
        all_sets = sets_by_session[lift['id']]

        # Filter out sets with missing weight or reps to avoid crashes in max()
        valid_sets = [s for s in all_sets if s.get('weight_kg') is not None and s.get('reps') is not None]
        best_set = max(valid_sets, key=lambda s: float(s['weight_kg']) * (1 + int(s['reps']) / 30.0), default=None) if valid_sets else None
        
        weight_val = best_set['weight_kg'] if best_set else None
        reps_val = best_set['reps'] if best_set else None
        subtitle = f"{format_weight(weight_val)}kg × {reps_val}" if best_set else "No sets logged"

        sets_detail = [
            {'set_num': i + 1, 'weight': format_weight(s['weight_kg']), 'reps': s['reps']}
            for i, s in enumerate(all_sets)
        ]

        activities.append({
            'type': 'lift',
            'date': lift['date'],
            'title': lift['title'],
            'subtitle': subtitle,
            'detail': {'sets': sets_detail, 'notes': lift['notes']}
        })

    # 2. WORKOUTS (from workout_sessions)
    workouts_this_week = conn.execute('''
        SELECT id, date, title, context, time_cap_minutes, notes
        FROM workout_sessions
        WHERE user_id = %s AND date BETWEEN %s AND %s
    ''', (user_id, week_start_str, today_str)).fetchall()

    workout_ids = [w['id'] for w in workouts_this_week]
    groups_by_workout = defaultdict(list)
    comps_by_group = defaultdict(list)

    if workout_ids:
        placeholders = ','.join(['%s'] * len(workout_ids))
        all_groups = conn.execute(f'''
            SELECT id, workout_session_id, order_index, type, shared_weight_kg
            FROM set_groups WHERE workout_session_id IN ({placeholders})
            ORDER BY order_index ASC
        ''', workout_ids).fetchall()
        for g in all_groups:
            groups_by_workout[g['workout_session_id']].append(g)
        
        group_ids = [g['id'] for g in all_groups]
        if group_ids:
            g_placeholders = ','.join(['%s'] * len(group_ids))
            all_comps = conn.execute(f'''
                SELECT sc.set_group_id, e.name AS exercise, sc.reps, sc.weight_kg
                FROM set_components sc
                JOIN exercises e ON sc.exercise_id = e.id
                WHERE sc.set_group_id IN ({g_placeholders})
            ''', group_ids).fetchall()
            for c in all_comps:
                comps_by_group[c['set_group_id']].append(c)

    for w in workouts_this_week:
        title = w['title'] or 'Untitled Workout'
        subtitle = w['context'] or 'Workout'
        if w['context'] in ['AMRAP', 'For Time'] and w['time_cap_minutes']:
            subtitle += f" ({w['time_cap_minutes']} min)"

        groups = groups_by_workout[w['id']]
        groups_detail = []
        for g in groups:
            comps = comps_by_group[g['id']]
            groups_detail.append([
                {
                    'exercise': c['exercise'],
                    'reps': c['reps'],
                    'weight': format_weight(c['weight_kg']) if c['weight_kg'] else None
                }
                for c in comps
            ])

        activities.append({
            'type': 'workout',
            'date': w['date'],
            'title': title,
            'subtitle': subtitle,
            'detail': {'groups': groups_detail, 'notes': w['notes']}
        })

    # 3. RUNS (from runs)
    runs_this_week = conn.execute('''
        SELECT id, date, run_type, distance_km, time_seconds, unit, notes
        FROM runs
        WHERE user_id = %s AND date BETWEEN %s AND %s
    ''', (user_id, week_start_str, today_str)).fetchall()

    for r in runs_this_week:
        unit = dict(r).get('unit', 'km')
        dist = _format_distance(r['distance_km'], unit)
        dur = _format_duration(r['time_seconds'])
        pace = _format_pace(r['time_seconds'], r['distance_km'], unit)

        activities.append({
            'type': 'run',
            'date': r['date'],
            'title': r['run_type'] or 'Run',
            'subtitle': f"{dist} in {dur}",
            'detail': {
                'distance': dist,
                'duration': dur,
                'pace': pace,
                'notes': r['notes']
            }
        })

    conn.close()

    # Sort activities descending by date
    activities.sort(key=lambda x: x['date'], reverse=True)

    return render_template(
        "dashboard.html",
        activities=activities,
        weekly_sessions=weekly_sessions,
        page='home'
    )

@app.route("/profile")
@login_required
def profile():
    conn = get_db()
    user_id = session["user_id"]

    # Get user display name
    user = conn.execute('SELECT display_name FROM users WHERE id = %s', (user_id,)).fetchone()
    display_name = user['display_name'] if user and user['display_name'] else session.get('username', '')

    # Get user profile data
    cursor = conn.execute(
        'SELECT * FROM user_profiles WHERE user_id = %s', (user_id,)
    )
    profile = cursor.fetchone()

    conn.close()

    # Default values if no profile exists
    if not profile:
        profile_data = {
            'display_name': display_name,
            'weight': '',
            'height': '',
            'weight_display': '',
            'height_display': '',
            'weight_unit': 'kg',
            'height_unit': 'cm',
            'height_feet': '',
            'height_inches': '',
            'photo_path': '',
            'preferred_unit': 'kg',
            'goal': '',
            'training_frequency': 3
        }
    else:
        # Convert stored values to display units
        profile_data = {
            'display_name': display_name,
            'weight': profile['weight'],
            'height': profile['height'],
            'weight_display': '',
            'height_display': '',
            'weight_unit': 'kg',
            'height_unit': 'cm',
            'height_feet': '',
            'height_inches': '',
            'photo_path': profile['photo_path'] if profile['photo_path'] else '',
            'preferred_unit': profile['preferred_unit'] or 'kg',
            'goal': profile['goal'] or '',
            'training_frequency': profile['training_frequency'] or 3
        }
        
        # Convert kg to display unit
        if profile['weight']:
            if profile_data['preferred_unit'] == 'lb':
                profile_data['weight_display'] = round(profile['weight'] * 2.20462, 1)
                profile_data['weight_unit'] = 'lb'
            else:
                profile_data['weight_display'] = profile['weight']
                profile_data['weight_unit'] = 'kg'
        
        # Convert cm to display unit
        if profile['height']:
            if profile_data['preferred_unit'] == 'ft-in':
                total_inches = profile['height'] / 2.54
                feet = int(total_inches // 12)
                inches = round(total_inches % 12, 1)
                profile_data['height_feet'] = feet
                profile_data['height_inches'] = inches
                profile_data['height_unit'] = 'ft-in'
            else:
                profile_data['height_display'] = profile['height']
                profile_data['height_unit'] = 'cm'
    
    return render_template("profile.html", profile=profile_data)

@app.route("/profile", methods=["POST"])
@login_required
def update_profile():
    conn = get_db()
    user_id = session["user_id"]
    
    weight = request.form.get('weight', '').strip()
    height = request.form.get('height', '').strip()
    weight_unit = request.form.get('weight_unit', 'kg')
    height_unit = request.form.get('height_unit', 'cm')
    height_feet = request.form.get('height_feet', '').strip()
    height_inches = request.form.get('height_inches', '').strip()
    preferred_unit = request.form.get('preferred_unit', 'kg')
    goal = request.form.get('goal', '').strip()
    training_frequency = request.form.get('training_frequency', '3')
    display_name = request.form.get('display_name', '').strip()

    # Handle display name update
    if display_name:
        conn.execute('UPDATE users SET display_name = %s WHERE id = %s', (display_name, user_id))
        session['display_name'] = display_name

    # Handle photo upload — preserve existing photo if no new one uploaded
    existing = conn.execute(
        'SELECT photo_path FROM user_profiles WHERE user_id = %s', (user_id,)
    ).fetchone()
    photo_path = existing['photo_path'] if existing and existing['photo_path'] else None

    if 'photo' in request.files:
        photo = request.files['photo']
        if photo and photo.filename != '':
            upload_dir = os.path.join(app.static_folder, 'uploads')
            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir)
            
            filename = f"user_{user_id}_{photo.filename}"
            photo_path = filename
            photo.save(os.path.join(upload_dir, filename))
    
    # Convert to base units (kg and cm) for storage
    weight_val = None
    height_val = None
    
    if weight:
        weight_float = float(weight)
        if weight_float < 0:
            flash("Weight cannot be negative", "error")
            conn.close()
            return redirect(url_for('profile'))
        if weight_unit == 'lb':
            weight_val = weight_float / 2.20462  # Convert lb to kg
        else:
            weight_val = weight_float

    if height_unit == 'ft-in':
        # Handle feet/inches input
        if height_feet and height_inches:
            feet_float = float(height_feet)
            inches_float = float(height_inches)
            if feet_float < 0 or inches_float < 0:
                flash("Height cannot be negative", "error")
                conn.close()
                return redirect(url_for('profile'))
            total_inches = (feet_float * 12) + inches_float
            height_val = total_inches * 2.54  # Convert to cm
    elif height:
        height_float = float(height)
        if height_float < 0:
            flash("Height cannot be negative", "error")
            conn.close()
            return redirect(url_for('profile'))
        height_val = height_float  # Already in cm
    
    training_freq_val = int(training_frequency) if training_frequency else 3
    
    # Check if profile exists
    cursor = conn.execute(
        'SELECT user_id FROM user_profiles WHERE user_id = %s', (user_id,)
    )
    existing_profile = cursor.fetchone()
    
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if existing_profile:
        # Update existing profile
        conn.execute("""
            UPDATE user_profiles 
            SET weight = %s, height = %s, preferred_unit = %s, goal = %s, 
                training_frequency = %s, photo_path = %s, updated_at = %s
            WHERE user_id = %s
        """, (weight_val, height_val, preferred_unit, goal, training_freq_val, photo_path, now, user_id))
    else:
        # Create new profile
        conn.execute("""
            INSERT INTO user_profiles 
            (user_id, weight, height, preferred_unit, goal, training_frequency, photo_path, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, weight_val, height_val, preferred_unit, goal, training_freq_val, photo_path, now, now))
    
    conn.commit()
    conn.close()
    
    # Prepare display data with proper unit conversions
    profile_data = {
        'display_name': display_name if display_name else session.get('username', ''),
        'weight': weight_val,
        'height': height_val,
        'weight_display': weight,
        'height_display': height,
        'weight_unit': weight_unit,
        'height_unit': height_unit,
        'height_feet': height_feet,
        'height_inches': height_inches,
        'photo_path': photo_path,
        'preferred_unit': preferred_unit,
        'goal': goal,
        'training_frequency': training_freq_val
    }
    
    return render_template("profile.html", profile=profile_data, success=True)

@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "GET":
        return render_template("change_password.html")

    user_id = session["user_id"]
    current_password = request.form.get('current_password', '').strip()
    new_password = request.form.get('new_password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()

    if not current_password or not new_password or not confirm_password:
        flash("All three password fields are required.", "error")
        return render_template("change_password.html")

    if new_password != confirm_password:
        flash("New passwords do not match.", "error")
        return render_template("change_password.html")

    conn = get_db()
    user = conn.execute('SELECT password_hash FROM users WHERE id = %s', (user_id,)).fetchone()
    if not check_password_hash(user['password_hash'], current_password):
        flash("Current password is incorrect.", "error")
        conn.close()
        return render_template("change_password.html")

    is_valid, error_msg = validate_password_strength(new_password)
    if not is_valid:
        flash(error_msg, "error")
        conn.close()
        return render_template("change_password.html")

    conn.execute('UPDATE users SET password_hash = %s WHERE id = %s',
                 (generate_password_hash(new_password), user_id))
    conn.commit()
    conn.close()
    return render_template("change_password.html", success=True)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    password_confirm = request.form.get("password_confirm", "").strip()

    if not username or not password or not password_confirm:
        return render_template("register.html", error="All fields required")
    if password != password_confirm:
        return render_template("register.html", error="Passwords do not match")
    
    is_valid, error_msg = validate_password_strength(password)
    if not is_valid:
        return render_template("register.html", error=error_msg)
    
    if get_user(username):
        return render_template("register.html", error="Username already taken")

    create_user(username, password)
    return redirect(url_for("register_success"))

@app.route("/register-success")
def register_success():
    return render_template("register_success.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# -------------------------
def validate_password_strength(password):
    """Validate password meets strength requirements.
    Returns (is_valid, error_message) tuple.
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    
    has_letter = any(c.isalpha() for c in password)
    has_number = any(c.isdigit() for c in password)
    has_special = any(not c.isalnum() for c in password)
    
    if not has_letter:
        return False, "Password must include at least 1 letter"
    if not has_number:
        return False, "Password must include at least 1 number"
    if not has_special:
        return False, "Password must include at least 1 special character"
    
    return True, None


def score_exercise(name, query):
    name_n = canonical(name)
    query_n = canonical(query)

    # exact match
    if name_n == query_n:
        return 0

    # strongest: starts with query
    if name_n.startswith(query_n):
        return 1

    # strong: token starts with query (pull-up → pullup → pull)
    tokens = name_n.split()
    if any(t.startswith(query_n) for t in tokens):
        return 2

    # medium: substring match
    if query_n in name_n:
        return 3

    # weak fallback
    return 4

def canonical(s):
    return s.lower().replace("-", "").replace(" ", "").strip()



def _format_pace(time_seconds, distance_km, unit='km'):
    """Returns pace string like '5:32 /km' or '8:54 /mi'."""
    if not distance_km or distance_km <= 0 or not time_seconds or time_seconds <= 0:
        return '-'
    distance_unit = (distance_km / 1.60934) if unit == 'mi' else distance_km
    if distance_unit <= 0:
        return '-'
    pace_sec = time_seconds / distance_unit
    minutes = int(pace_sec // 60)
    seconds = int(pace_sec % 60)
    return f"{minutes}:{seconds:02d} /{unit}"


def _format_duration(time_seconds):
    """Returns duration as 'H:MM:SS' or 'M:SS'."""
    total_minutes = int(time_seconds // 60)
    seconds = int(time_seconds % 60)
    if total_minutes >= 60:
        hours = total_minutes // 60
        mins = total_minutes % 60
        return f"{hours}:{mins:02d}:{seconds:02d}"
    return f"{total_minutes}:{seconds:02d}"


def _format_distance(distance_km, unit='km'):
    """Returns distance string in the logged unit."""
    if distance_km is None:
        return f"0.00 {unit}"
    if unit == 'mi':
        return f"{float(distance_km) / 1.60934:.2f} mi"
    return f"{float(distance_km):.2f} km"


def _pace_seconds_per_km(time_seconds, distance_km):
    """Returns pace in seconds/km for sorting (lower = faster)."""
    if not distance_km or distance_km <= 0:
        return float('inf')
    return time_seconds / distance_km


def _enrich_run(row):
    """Add computed display fields to a run row dict."""
    r = dict(row)
    r['pace_display'] = _format_pace(r['time_seconds'], r['distance_km'], r.get('unit', 'km'))
    r['duration_display'] = _format_duration(r['time_seconds'])
    r['distance_display'] = _format_distance(r['distance_km'], r.get('unit', 'km'))
    r['distance_input_value'] = round(r['distance_km'] / 1.60934, 2) if r.get('unit', 'km') == 'mi' else round(r['distance_km'], 2)
    r['duration_minutes_value'] = int(r['time_seconds'] // 60)
    r['time_seconds_value'] = int(r['time_seconds'] % 60)
    r['pace_seconds_per_km'] = _pace_seconds_per_km(r['time_seconds'], r['distance_km'])
    return r



@app.route('/lifts', methods=['GET', 'POST'])
@login_required
def log_lifts():
    conn = get_db()
    user_id = session["user_id"]
    
    if request.method == 'POST':
        payload = _extract_session_payload(request)
        exercise_id, exercise = resolve_exercise(conn, payload['exercise'])
        date_str = payload['date']
        notes = payload['notes']
        unit = payload['unit']
        raw_sets = payload['sets']

        try:
            if not exercise_id or not raw_sets:
                conn.close()
                return redirect(url_for('log_lifts'))

            entry_date = date_str or datetime.now().strftime('%Y-%m-%d')
            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            notes_val = notes if notes else None

            session_cursor = conn.execute(
                """
                INSERT INTO lift_sessions (user_id, exercise_id, notes, date, created_at)
                VALUES (%s, %s, %s, %s, %s) RETURNING id
                """,
                (user_id, exercise_id, notes_val, entry_date, created_at)
            )
            lift_session_id = session_cursor.lastrowid

            cleaned_sets = []
            for index, set_entry in enumerate(raw_sets):
                try:
                    weight_val = float(set_entry.get('weight_kg', set_entry.get('weight', 0)))
                    reps_val = int(set_entry.get('reps', 0))
                except (TypeError, ValueError, AttributeError):
                    continue

                if weight_val <= 0 or reps_val <= 0:
                    continue

                if unit == 'lb':
                    weight_val = weight_val / 2.20462

                conn.execute(
                    """
                    INSERT INTO lift_sets (lift_session_id, weight_kg, reps, order_index, rpe, notes)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (lift_session_id, weight_val, reps_val, index, None, None)
                )
                cleaned_sets.append({'weight_kg': weight_val, 'reps': reps_val, 'order_index': index})

            if not cleaned_sets:
                conn.execute('DELETE FROM lift_sessions WHERE id = %s', (lift_session_id,))
                conn.commit()
                conn.close()
                return redirect(url_for('log_lifts'))

            conn.commit()

            current_session = _enrich_session_record({
                'id': lift_session_id,
                'user_id': user_id,
                'exercise': exercise,
                'notes': notes_val,
                'date': entry_date,
                'created_at': created_at,
                'sets': cleaned_sets,
            })

            previous_session = conn.execute(
                """
                SELECT id
                FROM lift_sessions
                WHERE user_id = %s
                  AND exercise_id = %s
                  AND date < %s
                ORDER BY date DESC
                LIMIT 1
                """,
                (user_id, exercise_id, entry_date)
            ).fetchone()

            prev_data = None
            insight = "First time logging this exercise!"
            emoji = "🎉"

            if previous_session:
                prev_full = fetch_session_by_id(conn, previous_session['id'], user_id)
                if prev_full and prev_full.get('best_set'):
                    prev_data = {
                        'weight': prev_full['best_set']['weight_kg'],
                        'reps': prev_full['best_set']['reps'],
                        'sets': prev_full.get('set_count', len(prev_full.get('sets') or [])),
                        'date': prev_full.get('date')
                    }
                    current_best = current_session.get('best_set') or {}
                    current_w = current_best.get('weight_kg')
                    current_r = current_best.get('reps')
                    prev_w = prev_data['weight']
                    prev_r = prev_data['reps']

                    if current_w and prev_w and current_r and prev_r:
                        if current_w > prev_w and current_r >= prev_r:
                            insight = "Stronger than last session"
                            emoji = "🔥"
                        elif current_w < prev_w and current_r > prev_r:
                            insight = "Higher reps at lower weight — strong volume work"
                            emoji = "💪"
                        elif current_w > prev_w and current_r < prev_r:
                            insight = "Heavier weight with fewer reps — building strength"
                            emoji = "📈"
                        elif current_w < prev_w and current_r <= prev_r:
                            insight = "Last session was heavier - variation like this is normal, room to push next time"
                            emoji = "💪"
                        else:
                            insight = "Consistent with last session — solid baseline"
                            emoji = "✨"

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                conn.close()
                return jsonify({
                    "success": True,
                    "current": {
                        "weight": current_session.get('best_set', {}).get('weight_kg'),
                        "reps": current_session.get('best_set', {}).get('reps')
                    },
                    "session": serialize_progress_lift(current_session),
                    "previous": prev_data,
                    "insight": insight,
                    "emoji": emoji,
                    "is_pr": bool(current_session.get('best_set')) and (prev_data is None or current_session.get('best_set', {}).get('weight_kg', 0) > prev_data.get('weight', 0))
                })

            if prev_data:
                session['lift_feedback'] = {
                    'current_w': current_session.get('best_set', {}).get('weight_kg'),
                    'current_r': current_session.get('best_set', {}).get('reps'),
                    'prev_w': prev_data['weight'],
                    'prev_r': prev_data['reps'],
                    'insight': insight
                }

            conn.close()
            flash("Lift logged successfully", "success")
            return redirect(url_for('log_lifts'))

        except ValueError:
            conn.close()
            return redirect(url_for('log_lifts'))

    # GET request - show PRs
    prs = build_pr_gallery(fetch_user_sessions(conn, user_id, limit=None, order_desc=True))
    prs_recent = sorted(prs['entries'], key=lambda x: x['date'], reverse=True)[:6]
    prs_truncated = len(prs['entries']) > 6

    conn.close()
    
    return render_template(
        "log_lifts.html",
        prs=prs,
        prs_recent=prs_recent,
        prs_truncated=prs_truncated,
        exercises=ALL_EXERCISES,
        today_date=date.today().isoformat()
    )

# --- UTILITY ---

def get_all_sets_for_exercise(conn, exercise_id, user_id):
    query = """
        SELECT se.weight_kg as weight, se.reps, es.date, 1 as completed
        FROM lift_sets se
        JOIN lift_sessions es ON se.lift_session_id = es.id
        WHERE es.user_id = %s AND es.exercise_id = %s
        
        UNION ALL
        
        SELECT COALESCE(sc.weight_kg, sg.shared_weight_kg) as weight, sc.reps, ws.date, sg.completed
        FROM set_components sc
        JOIN set_groups sg ON sc.set_group_id = sg.id
        JOIN workout_sessions ws ON sg.workout_session_id = ws.id
        WHERE ws.user_id = %s AND sc.exercise_id = %s
        AND NOT (COALESCE(sc.weight_kg, sg.shared_weight_kg) IS NULL AND sc.reps IS NULL)
    """
    rows = conn.execute(query, (user_id, exercise_id, user_id, exercise_id)).fetchall()
    return [{"weight": r["weight"], "reps": r["reps"], "date": r["date"], "completed": bool(r["completed"])} for r in rows]

def calculate_unified_1rm(conn, exercise_id, user_id):
    sets = get_all_sets_for_exercise(conn, exercise_id, user_id)
    
    # Step 1: initial max
    initial_max = None
    valid_sets = []
    for s in sets:
        if not s.get("completed"):
            continue
        weight = s.get("weight")
        reps = s.get("reps")
        if weight is None or reps is None:
            continue
        if reps > 10 or reps <= 0 or weight <= 0:
            continue
        valid_sets.append(s)
        
        rm = weight * (1 + reps / 30.0)
        if initial_max is None or rm > initial_max:
            initial_max = rm

    if initial_max is None:
        return None

    # Step 2: refined max
    refined_max = None
    for s in valid_sets:
        weight = s.get("weight")
        if weight < 0.7 * initial_max:
            continue
            
        rm = weight * (1 + s.get("reps") / 30.0)
        if refined_max is None or rm > refined_max:
            refined_max = rm
            
    return refined_max

@app.route('/log_workout', methods=['GET'])
@login_required
def log_workout():
    return render_template(
        'log_workout.html',
        exercises=ALL_EXERCISES,
        today_date=date.today().isoformat()
    )

@app.route('/exercise_recent_performance', methods=['GET'])
@login_required
def exercise_recent_performance():
    conn = get_db()
    user_id = session["user_id"]
    exercise_name = request.args.get('name', '').strip()
    
    if not exercise_name:
        conn.close()
        return jsonify([])
        
    exercise_id, _ = resolve_exercise(conn, exercise_name)
    if not exercise_id:
        conn.close()
        return jsonify([])
        
    query = """
        SELECT se.weight_kg, se.reps, es.date, se.order_index as ord
        FROM lift_sets se
        JOIN lift_sessions es ON se.lift_session_id = es.id
        WHERE es.user_id = %s AND es.exercise_id = %s
          AND (se.reps > 0 OR se.weight_kg > 0)

        UNION ALL

        SELECT COALESCE(sc.weight_kg, sg.shared_weight_kg) as weight_kg, sc.reps, ws.date, sg.order_index as ord
        FROM set_components sc
        JOIN set_groups sg ON sc.set_group_id = sg.id
        JOIN workout_sessions ws ON sg.workout_session_id = ws.id
        WHERE ws.user_id = %s AND sc.exercise_id = %s
          AND (sc.reps > 0 OR COALESCE(sc.weight_kg, sg.shared_weight_kg) > 0)

        ORDER BY date DESC, ord ASC
        LIMIT 50
    """
    
    rows = conn.execute(query, (user_id, exercise_id, user_id, exercise_id)).fetchall()
    conn.close()
    
    if not rows:
        return jsonify([])
        
    most_recent_date_str = str(rows[0]['date']).split(' ')[0]
    
    results = []
    today = date.today()
    
    try:
        row_date = datetime.strptime(most_recent_date_str, "%Y-%m-%d").date()
        days_ago = (today - row_date).days
        days_ago = max(0, days_ago)
        days_str = f"{days_ago}d ago" if days_ago != 0 else "Today"
    except ValueError:
        days_str = ""

    for row in rows:
        date_str = str(row['date']).split(' ')[0]
        if date_str != most_recent_date_str:
            continue
            
        weight = row['weight_kg']
        reps = row['reps']
        
        display = ""
        
        if weight is not None and reps is not None:
            formatted_weight = format_weight(weight)
            display = f"{formatted_weight}kg × {reps}"
        elif weight is not None:
            formatted_weight = format_weight(weight)
            display = f"{formatted_weight}kg"
        elif reps is not None:
            display = f"{reps} reps"
            
        if display:
            results.append({
                "weight": weight,
                "reps": reps,
                "display": display
            })
            
    return jsonify({
        "days_ago_label": days_str,
        "entries": results
    })

@app.route('/workout_sessions', methods=['POST'])
@login_required
def create_workout_session():
    conn = get_db()
    user_id = session["user_id"]
    payload = request.get_json(silent=True) or {}
    
    date_str = payload.get('date', datetime.now().strftime('%Y-%m-%d'))
    ws_type = payload.get('type') or payload.get('name')
    notes = payload.get('notes', '')
    result = payload.get('result')

    context          = payload.get('context') or None
    time_cap_minutes = payload.get('time_cap_minutes')
    emom_interval    = payload.get('emom_interval')
    emom_duration    = payload.get('emom_duration')
    time_cap_minutes = int(time_cap_minutes) if time_cap_minutes else None
    emom_interval    = int(emom_interval)    if emom_interval    else None
    emom_duration    = int(emom_duration)    if emom_duration    else None

    session_repeat = int(payload.get('repeat', 1))
    raw_groups = payload.get('set_groups', [])

    has_basic_info = bool(ws_type or notes or context)
    has_components = any(len(g.get('components', [])) > 0 for g in raw_groups)

    if not has_basic_info and not has_components:
        conn.close()
        return jsonify({"success": False, "error": "Cannot save an empty workout. Please add exercises or notes."}), 400

    for group in raw_groups:
        rest_seconds = group.get('rest_seconds')
        if rest_seconds is not None:
            try:
                if int(rest_seconds) < 0:
                    conn.close()
                    return jsonify({"success": False, "error": "Rest time cannot be negative"}), 400
            except ValueError:
                pass
                
        for comp in group.get('components', []):
            reps = comp.get('reps')
            weight_kg = comp.get('weight_kg')
            if reps is not None:
                try:
                    if int(reps) < 0:
                        conn.close()
                        return jsonify({"success": False, "error": "Reps cannot be negative"}), 400
                except ValueError:
                    pass
            if weight_kg is not None:
                try:
                    if float(weight_kg) < 0:
                        conn.close()
                        return jsonify({"success": False, "error": "Weight cannot be negative"}), 400
                except ValueError:
                    pass

    try:
        ws_cursor = conn.execute(
            """INSERT INTO workout_sessions
               (user_id, date, title, notes, context, time_cap_minutes, emom_interval, emom_duration, result)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (user_id, date_str, ws_type, notes, context, time_cap_minutes, emom_interval, emom_duration, result)
        )
        ws_id = ws_cursor.lastrowid
        
        order_index = 0
        for _ in range(session_repeat):
            pattern_index = 0
            for group in raw_groups:
                group_repeat = int(group.get('repeat', 1))
                group_type = group.get('type')
                shared_weight_kg = group.get('shared_weight_kg')
                completed = group.get('completed', True)
                components = group.get('components', [])
                rest_seconds = group.get('rest_seconds')
                rest_seconds = int(rest_seconds) if rest_seconds else None

                for _ in range(group_repeat):
                    sg_cursor = conn.execute(
                        """INSERT INTO set_groups 
                           (workout_session_id, order_index, type, pattern_index, completed, shared_weight_kg, rest_seconds) 
                           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                        (ws_id, order_index, group_type, pattern_index, completed, shared_weight_kg, rest_seconds)
                    )
                    sg_id = sg_cursor.lastrowid
                    
                    for comp in components:
                        exercise_id = comp.get('exercise_id')
                        exercise_name = comp.get('exercise')
                        
                        if not exercise_id and exercise_name:
                            exercise_id, _ = resolve_exercise(conn, exercise_name)
                            
                        target_type = comp.get('target_type', 'reps')
                        reps = comp.get('reps')
                        weight_kg = comp.get('weight_kg')
                        rpe = comp.get('rpe')
                        c_notes = comp.get('notes')
                        
                        calories = comp.get('calories')
                        distance_meters = comp.get('distance_meters')
                        
                        time_sec = comp.get('time_seconds')
                        if target_type == 'time':
                            mins = int(comp.get('minutes') or 0)
                            secs = int(comp.get('seconds') or 0)
                            time_sec = mins * 60 + secs
                        
                        height_inch = comp.get('height_inch')
                        
                        if exercise_id is not None:
                            conn.execute(
                                """INSERT INTO set_components 
                                   (set_group_id, exercise_id, reps, weight_kg, rpe, notes, time_seconds, distance_meters, calories, height_inch, target_type)
                                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                                (sg_id, exercise_id, reps, weight_kg, rpe, c_notes, time_sec, distance_meters, calories, height_inch, target_type)
                            )
                    
                    order_index += 1
                pattern_index += 1
                    
        conn.commit()
        return jsonify({"success": True, "workout_session_id": ws_id})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 400
    finally:
        conn.close()


@app.route('/workouts/history')
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
        date_clause = "AND CAST(julianday('now') - julianday(ws.date) AS INTEGER) <= %s"

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

    # For each session, fetch its groups + components
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

    # Group by date for the template (ordered dict — most recent first)
    from collections import OrderedDict
    grouped = OrderedDict()
    for ws in sessions:
        grouped.setdefault(ws['date'], []).append(ws)

    return render_template('workout_history.html',
        grouped=grouped,
        current_range=date_range,
        current_exercise=exercise_filter,
        exercises=ALL_EXERCISES,
        filter_exercises=filter_exercises,
        page='history'
    )


@app.route('/workout_sessions/<int:id>/delete', methods=['POST'])
@login_required
def delete_workout_session(id):
    conn = get_db()
    user_id = session["user_id"]
    row = conn.execute("SELECT id FROM workout_sessions WHERE id = %s AND user_id = %s", (id, user_id)).fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "error": "Not found"}), 404
    conn.execute("DELETE FROM workout_sessions WHERE id = %s", (id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route('/workout_sessions/<int:id>/edit', methods=['POST'])
@login_required
def edit_workout_session(id):
    conn = get_db()
    user_id = session["user_id"]
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    existing = conn.execute(
        "SELECT * FROM workout_sessions WHERE id = %s AND user_id = %s", (id, user_id)
    ).fetchone()
    if not existing:
        conn.close()
        return jsonify({"success": False, "error": "Not found"}), 404

    name     = request.form.get("name",  "").strip() or None
    notes    = request.form.get("notes", "").strip() or None
    result   = request.form.get("result", "").strip() or None
    date_str = request.form.get("date",  "").strip() or existing["date"]
    
    context          = request.form.get("context") or None
    time_cap_minutes = request.form.get("time_cap_minutes")
    emom_interval    = request.form.get("emom_interval")
    emom_duration    = request.form.get("emom_duration")
    try:
        time_cap_minutes = int(time_cap_minutes) if time_cap_minutes else None
        emom_interval    = int(emom_interval)    if emom_interval    else None
        emom_duration    = int(emom_duration)    if emom_duration    else None
    except ValueError:
        conn.close()
        return jsonify({"success": False, "error": "Invalid number format for context fields"}), 400
    
    if time_cap_minutes is not None and time_cap_minutes < 0:
        conn.close()
        return jsonify({"success": False, "error": "Time cap cannot be negative"}), 400
    if emom_interval is not None and emom_interval < 0:
        conn.close()
        return jsonify({"success": False, "error": "EMOM interval cannot be negative"}), 400
    if emom_duration is not None and emom_duration < 0:
        conn.close()
        return jsonify({"success": False, "error": "EMOM duration cannot be negative"}), 400

    conn.execute(
        """UPDATE workout_sessions 
           SET title = %s, notes = %s, result = %s, date = %s, context = %s, time_cap_minutes = %s, emom_interval = %s, emom_duration = %s 
           WHERE id = %s AND user_id = %s""",
        (name, notes, result, date_str, context, time_cap_minutes, emom_interval, emom_duration, id, user_id)
    )

    # Update individual set_components (exercise name, reps, weight_kg)
    comp_ids      = request.form.getlist("comp_id[]")
    comp_names    = request.form.getlist("comp_exercise[]")
    comp_reps     = request.form.getlist("comp_reps[]")
    comp_weights  = request.form.getlist("comp_weight[]")

    for i, comp_id in enumerate(comp_ids):
        try:
            comp_id_int = int(comp_id)
        except (ValueError, TypeError):
            continue

        # Verify ownership — component must belong to a group in this session
        owner = conn.execute("""
            SELECT sc.id FROM set_components sc
            JOIN set_groups sg ON sc.set_group_id = sg.id
            WHERE sc.id = %s AND sg.workout_session_id = %s
        """, (comp_id_int, id)).fetchone()
        if not owner:
            continue

        ex_name = comp_names[i].strip() if i < len(comp_names) else ''
        reps_raw = comp_reps[i].strip() if i < len(comp_reps) else ''
        wt_raw   = comp_weights[i].strip() if i < len(comp_weights) else ''
        
        try:
            reps_val   = int(reps_raw)   if reps_raw else None
            weight_val = float(wt_raw) if wt_raw else None
        except ValueError:
            conn.close()
            return jsonify({"success": False, "error": "Invalid number format for weight/reps"}), 400
        
        if reps_val is not None and reps_val < 0:
            conn.close()
            return jsonify({"success": False, "error": "Reps cannot be negative"}), 400
        if weight_val is not None and weight_val < 0:
            conn.close()
            return jsonify({"success": False, "error": "Weight cannot be negative"}), 400

        if ex_name:
            exercise_id, _ = resolve_exercise(conn, ex_name)
            conn.execute(
                "UPDATE set_components SET exercise_id = %s, reps = %s, weight_kg = %s WHERE id = %s",
                (exercise_id, reps_val, weight_val, comp_id_int)
            )
        else:
            conn.execute(
                "UPDATE set_components SET reps = %s, weight_kg = %s WHERE id = %s",
                (reps_val, weight_val, comp_id_int)
            )

    # Update rest_seconds per group
    group_ids    = request.form.getlist("group_id[]")
    group_mins   = request.form.getlist("group_rest_min[]")
    group_rests  = request.form.getlist("group_rest_seconds[]")

    for i, group_id in enumerate(group_ids):
        try:
            gid = int(group_id)
        except (ValueError, TypeError):
            continue
        owner_g = conn.execute(
            "SELECT id FROM set_groups WHERE id = %s AND workout_session_id = %s", (gid, id)
        ).fetchone()
        if not owner_g:
            continue
        min_raw  = group_mins[i].strip()  if i < len(group_mins)  else ''
        sec_raw  = group_rests[i].strip() if i < len(group_rests) else ''
        try:
            min_val  = int(min_raw) if min_raw else 0
            sec_val  = int(sec_raw) if sec_raw else 0
        except ValueError:
            conn.close()
            return jsonify({"success": False, "error": "Invalid number format for rest time"}), 400
        
        if min_val < 0 or sec_val < 0:
            conn.close()
            return jsonify({"success": False, "error": "Rest time cannot be negative"}), 400
            
        rest_val = (min_val * 60 + sec_val) or None
        conn.execute(
            "UPDATE set_groups SET rest_seconds = %s WHERE id = %s",
            (rest_val, gid)
        )

    conn.commit()

    # Fetch updated groups for the JSON response
    updated_groups = []
    groups = conn.execute("""
        SELECT sg.id, sg.order_index, sg.rest_seconds
        FROM set_groups sg WHERE sg.workout_session_id = %s
        ORDER BY sg.order_index
    """, (id,)).fetchall()
    for g in groups:
        comps = conn.execute("""
            SELECT sc.id, e.name AS exercise, sc.reps, sc.weight_kg
            FROM set_components sc
            JOIN exercises e ON sc.exercise_id = e.id
            WHERE sc.set_group_id = %s
        """, (g['id'],)).fetchall()
        updated_groups.append({
            'id': g['id'],
            'order_index': g['order_index'],
            'rest_seconds': g['rest_seconds'],
            'components': [dict(c) for c in comps]
        })

    conn.close()

    if is_ajax:
        return jsonify({
            "success": True,
            "session": {
                "id": id,
                "name": name or "Untitled Workout",
                "notes": notes or "",
                "date": date_str,
                "context": context,
                "time_cap_minutes": time_cap_minutes,
                "emom_interval": emom_interval,
                "emom_duration": emom_duration,
                "result": result,
                "groups": updated_groups,
            }
        })

    return redirect(url_for("workout_history"))


@app.route('/delete_lift/<int:id>', methods=['POST'])
@login_required
def delete_lift(id):
    conn = get_db()
    user_id = session["user_id"]

    cursor = conn.execute(
        'DELETE FROM lift_sessions WHERE id = %s AND user_id = %s',
        (id, user_id)
    )
    conn.commit()
    conn.close()

    if cursor.rowcount > 0:
        return {"success": True}
    else:
        return {"success": False, "error": "Lift not found"}, 404


@app.route('/delete_wod/<int:id>', methods=['POST'])
@login_required
def delete_wod(id):
    conn = get_db()
    user_id = session["user_id"]
    
    # Verify ownership and delete
    cursor = conn.execute(
        'DELETE FROM wods WHERE id = %s AND user_id = %s',
        (id, user_id)
    )
    conn.commit()
    conn.close()
    
    if cursor.rowcount > 0:
        return {"success": True}
    else:
        return {"success": False, "error": "WOD not found"}, 404


@app.route('/edit_lift/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_lift(id):
    conn = get_db()
    user_id = session["user_id"]
    
    if request.method == 'POST':
        payload = _extract_session_payload(request)
        exercise_id, exercise = resolve_exercise(conn, payload['exercise'])
        notes = payload['notes']
        date_str = payload['date']
        unit = payload['unit']
        raw_sets = payload['sets']

        try:
            existing = conn.execute(
                'SELECT id FROM lift_sessions WHERE id = %s AND user_id = %s',
                (id, user_id)
            ).fetchone()
            if not existing:
                conn.close()
                flash("Lift not found", "error")
                return redirect(url_for('lifts_history'))

            if not exercise_id:
                conn.close()
                flash("Please choose an exercise", "error")
                return redirect(url_for('edit_lift', id=id))
            conn.execute("""
                UPDATE lift_sessions
                SET exercise_id = %s, notes = %s, date = %s
                WHERE id = %s AND user_id = %s
            """, (exercise_id, notes or None, date_str, id, user_id))

            conn.execute('DELETE FROM lift_sets WHERE lift_session_id = %s', (id,))

            cleaned_sets = []
            for index, set_entry in enumerate(raw_sets):
                try:
                    weight_val = float(set_entry.get('weight_kg', set_entry.get('weight', 0)))
                    reps_val = int(set_entry.get('reps', 0))
                except (TypeError, ValueError, AttributeError):
                    continue

                if weight_val <= 0 or reps_val <= 0:
                    continue

                if unit == 'lb':
                    weight_val = weight_val / 2.20462

                conn.execute("""
                    INSERT INTO lift_sets (lift_session_id, weight_kg, reps, order_index, rpe, notes)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (id, weight_val, reps_val, index, None, None))
                cleaned_sets.append(True)

            if not cleaned_sets:
                raise ValueError("At least one valid set is required")

            conn.commit()
            flash("Lift updated successfully", "success")
        except ValueError:
            flash("Invalid weight or reps", "error")

        conn.close()
        redirect_args = {}
        if request.form.get('filter_range'):
            redirect_args['range'] = request.form['filter_range']
        if request.form.get('filter_exercise'):
            redirect_args['exercise'] = request.form['filter_exercise']
        return redirect(url_for('lifts_history', **redirect_args))

    conn.close()
    return redirect(url_for('lifts_history'))


@app.route('/edit_wod/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_wod(id):
    conn = get_db()
    user_id = session["user_id"]
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        workout_text = request.form.get('workout_text', '').strip()
        result = request.form.get('result', '').strip()
        notes = request.form.get('notes', '').strip()
        date_str = request.form.get('date', '').strip()
        
        if workout_text and result:
            conn.execute("""
                UPDATE wods 
                SET name = %s, workout_text = %s, result = %s, notes = %s, date = %s
                WHERE id = %s AND user_id = %s
            """, (name or None, workout_text, result, notes or None, date_str, id, user_id))
            conn.commit()
            flash("WOD updated successfully", "success")
        else:
            flash("Workout text and result are required", "error")
        
        conn.close()
        redirect_args = {}
        if request.form.get('filter_range'):
            redirect_args['range'] = request.form['filter_range']
        return redirect(url_for('wods_history', **redirect_args))
    
    # GET - fetch the WOD for editing
    wod = conn.execute(
        'SELECT * FROM wods WHERE id = %s AND user_id = %s',
        (id, user_id)
    ).fetchone()
    conn.close()
    
    if not wod:
        flash("WOD not found", "error")
        return redirect(url_for('log_wod'))
    
    return render_template('edit_wod.html', wod=wod)


@app.route('/lifts/history')
@login_required
def lifts_history():
    conn = get_db()
    user_id = session["user_id"]

    # Read filter params
    date_range = request.args.get('range', '')
    exercise_filter = request.args.get('exercise', '')

    sessions = fetch_user_sessions(conn, user_id, exercise=exercise_filter or None, date_range=date_range or None, limit=None, order_desc=True)

    grouped = defaultdict(list)
    for lift in sessions:
        grouped[lift['date']].append(lift)

    prs = build_pr_gallery(fetch_user_sessions(conn, user_id, limit=None, order_desc=True))
    exercises = [r['exercise'] for r in conn.execute(
        '''SELECT DISTINCT e.name as exercise
           FROM lift_sessions es
           JOIN exercises e ON es.exercise_id = e.id
           WHERE es.user_id = %s ORDER BY e.name''',
        (user_id,)
    ).fetchall()]

    conn.close()

    return render_template('lifts_history.html',
        grouped=grouped,
        prs=prs,
        exercises=exercises,
        current_range=date_range,
        current_exercise=exercise_filter,
        page='history'
    )


@app.route('/wods/history')
@login_required
def wods_history():
    conn = get_db()
    user_id = session["user_id"]

    # Read filter params
    date_range = request.args.get('range', '')
    wod_type_filter = request.args.get('wod_type', '')

    # Build query with optional filters
    query = 'SELECT * FROM wods WHERE user_id = %s'
    params = [user_id]

    if date_range in ('7', '30'):
        cutoff = (date.today() - timedelta(days=int(date_range))).isoformat()
        query += ' AND date >= %s'
        params.append(cutoff)

    if wod_type_filter:
        query += ' AND wod_type = %s'
        params.append(wod_type_filter)

    query += ' ORDER BY date DESC, id DESC'
    wods = conn.execute(query, params).fetchall()

    # Group WODs by date
    grouped = defaultdict(list)
    for wod in wods:
        day = str(wod['date']).split(' ')[0]
        grouped[day].append(wod)

    conn.close()

    return render_template('wods_history.html',
        grouped=grouped,
        current_range=date_range,
        current_wod_type=wod_type_filter
    )


@app.route('/log_run', methods=['GET', 'POST'])
@login_required
def log_run():
    conn = get_db()
    user_id = session["user_id"]

    if request.method == 'POST':
        try:
            distance_raw = float(request.form.get('distance', 0) or 0)
            unit = request.form.get('unit', 'km')
            run_type = request.form.get('run_type', 'Run').strip() or 'Run'
            dur_min = int(request.form.get('duration_minutes', 0) or 0)
            dur_sec = int(request.form.get('time_seconds', 0) or 0)
            date_str = request.form.get('date', '').strip() or datetime.now().strftime('%Y-%m-%d')
            notes = request.form.get('notes', '').strip() or None

            if distance_raw <= 0 or (dur_min == 0 and dur_sec == 0):
                conn.close()
                flash("Please enter a valid distance and duration.", "error")
                return redirect(url_for('log_run'))

            distance_km = distance_raw / 1.60934 if unit == 'mi' else distance_raw
            time_seconds = dur_min * 60 + dur_sec
            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            run_cursor = conn.execute(
                """
                INSERT INTO runs (user_id, distance_km, time_seconds, unit, run_type, date, notes, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (user_id, distance_km, time_seconds, unit, run_type, date_str, notes, created_at)
            )
            run_id = run_cursor.lastrowid
            conn.commit()

            new_run = _enrich_run({
                'id': run_id,
                'user_id': user_id,
                'distance_km': distance_km,
                'time_seconds': time_seconds,
                'unit': unit,
                'run_type': run_type,
                'date': date_str,
                'notes': notes,
                'created_at': created_at,
            })

            previous_run = conn.execute(
                "SELECT * FROM runs WHERE user_id = %s AND date < %s ORDER BY date DESC, created_at DESC LIMIT 1",
                (user_id, date_str)
            ).fetchone()

            prev_data = None
            insight = "First run logged — great start!"
            emoji = "🎉"
            is_pb = False

            if previous_run:
                prev_enriched = _enrich_run(dict(previous_run))
                prev_data = {
                    'pace': prev_enriched['pace_display'],
                    'distance': prev_enriched['distance_display'],
                    'duration': prev_enriched['duration_display'],
                    'pace_sec': prev_enriched['pace_seconds_per_km'],
                }
                curr_pace = new_run['pace_seconds_per_km']
                prev_pace = prev_enriched['pace_seconds_per_km']

                if curr_pace < prev_pace * 0.98:
                    insight = "Faster than last run — great pace!"
                    emoji = "🔥"
                    # Check all-time PB
                    fastest_ever = conn.execute(
                        "SELECT MIN(time_seconds / distance_km) FROM runs WHERE user_id = %s AND id != %s",
                        (user_id, run_id)
                    ).fetchone()[0]
                    if fastest_ever is None or curr_pace < fastest_ever:
                        is_pb = True
                        insight = "New pace PB — fastest run ever!"
                        emoji = "🏆"
                elif curr_pace > prev_pace * 1.02:
                    insight = "Recovery run or tough day? You got this"
                    emoji = "💪"
                else:
                    insight = "Consistent pace — solid baseline"
                    emoji = "✨"
            else:
                fastest_ever = conn.execute(
                    "SELECT MIN(time_seconds / distance_km) FROM runs WHERE user_id = %s AND id != %s",
                    (user_id, run_id)
                ).fetchone()[0]
                if fastest_ever is None or new_run['pace_seconds_per_km'] < fastest_ever:
                    is_pb = True

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                conn.close()
                return jsonify({
                    "success": True,
                    "run": {
                        "id": new_run['id'],
                        "distance_display": new_run['distance_display'],
                        "duration_display": new_run['duration_display'],
                        "time_seconds": new_run['time_seconds'],
                        "pace_display": new_run['pace_display'],
                        "run_type": new_run.get('run_type', 'Run'),
                        "date": new_run['date'],
                        "notes": new_run['notes'] or '',
                        "pace_seconds_per_km": new_run['pace_seconds_per_km'],
                        "distance_km": new_run['distance_km'],
                    },
                    "previous": prev_data,
                    "insight": insight,
                    "emoji": emoji,
                    "is_pb": is_pb,
                })

            conn.close()
            flash("Run logged successfully!", "success")
            return redirect(url_for('log_run'))

        except (ValueError, TypeError):
            conn.close()
            flash("Invalid input — please check your distance and duration.", "error")
            return redirect(url_for('log_run'))

    # GET
    all_rows = conn.execute(
        "SELECT * FROM runs WHERE user_id = %s ORDER BY date DESC, created_at DESC",
        (user_id,)
    ).fetchall()

    total_runs = len(all_rows)
    all_enriched = [_enrich_run(dict(r)) for r in all_rows]

    fastest_runs = sorted(all_enriched, key=lambda x: x['pace_seconds_per_km'])[:3]
    longest_runs = sorted(all_enriched, key=lambda x: (-x['distance_km'], x['time_seconds']))[:3]

    best_pace = fastest_runs[0]['pace_display'] if fastest_runs else '-'

    conn.close()
    return render_template(
        'log_run.html',
        total_runs=total_runs,
        best_pace=best_pace,
        fastest_runs=fastest_runs,
        longest_runs=longest_runs,
        today_date=date.today().isoformat(),
    )


@app.route('/runs/history')
@login_required
def runs_history():
    conn = get_db()
    user_id = session["user_id"]

    date_range = request.args.get('range', '')
    query = "SELECT * FROM runs WHERE user_id = %s"
    params = [user_id]

    if date_range in ('7', '30'):
        cutoff = (date.today() - timedelta(days=int(date_range))).isoformat()
        query += ' AND date >= %s'
        params.append(cutoff)

    query += ' ORDER BY date DESC, created_at DESC'
    rows = conn.execute(query, params).fetchall()
    conn.close()

    enriched = [_enrich_run(dict(r)) for r in rows]

    grouped = defaultdict(list)
    for r in enriched:
        grouped[str(r['date']).split(' ')[0]].append(r)

    return render_template('runs_history.html',
        grouped=grouped,
        current_range=date_range,
        page='history'
    )


@app.route('/edit_run/<int:run_id>', methods=['POST'])
@login_required
def edit_run(run_id):
    conn = get_db()
    user_id = session["user_id"]
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    try:
        existing = conn.execute(
            'SELECT * FROM runs WHERE id = %s AND user_id = %s',
            (run_id, user_id)
        ).fetchone()
        if not existing:
            conn.close()
            if is_ajax:
                return jsonify({"success": False, "error": "Run not found"}), 404
            flash("Run not found", "error")
            return redirect(url_for('runs_history', range=request.form.get('filter_range', '')))

        distance_raw = float(request.form.get('distance', 0) or 0)
        unit = request.form.get('unit', 'km')
        run_type = request.form.get('run_type', 'Run').strip() or 'Run'
        dur_min = int(request.form.get('duration_minutes', 0) or 0)
        dur_sec = int(request.form.get('time_seconds', 0) or 0)
        date_str = request.form.get('date', '').strip() or existing['date']
        notes = request.form.get('notes', '').strip() or None

        if distance_raw <= 0 or (dur_min == 0 and dur_sec == 0):
            raise ValueError("Invalid run data")

        distance_km = distance_raw / 1.60934 if unit == 'mi' else distance_raw
        time_seconds = dur_min * 60 + dur_sec

        conn.execute(
            """
            UPDATE runs
            SET distance_km = %s, time_seconds = %s, unit = %s, run_type = %s, date = %s, notes = %s
            WHERE id = %s AND user_id = %s
            """,
            (distance_km, time_seconds, unit, run_type, date_str, notes, run_id, user_id)
        )
        conn.commit()

        updated = _enrich_run({
            'id': run_id,
            'user_id': user_id,
            'distance_km': distance_km,
            'time_seconds': time_seconds,
            'unit': unit,
            'run_type': run_type,
            'date': date_str,
            'notes': notes,
            'created_at': existing['created_at'],
        })

        if is_ajax:
            conn.close()
            return jsonify({
                "success": True,
                "run": {
                    "id": updated['id'],
                    "distance_display": updated['distance_display'],
                    "distance_input_value": updated['distance_input_value'],
                    "duration_display": updated['duration_display'],
                    "time_seconds": updated['time_seconds'],
                    "duration_minutes_value": updated['duration_minutes_value'],
                    "time_seconds_value": updated['time_seconds_value'],
                    "pace_display": updated['pace_display'],
                    "pace_seconds_per_km": updated['pace_seconds_per_km'],
                    "run_type": updated.get('run_type', 'Run'),
                    "unit": updated.get('unit', 'km'),
                    "date": updated['date'],
                    "notes": updated['notes'] or '',
                },
            })

        conn.close()
        flash("Run updated successfully", "success")
        redirect_args = {}
        if request.form.get('filter_range'):
            redirect_args['range'] = request.form['filter_range']
        return redirect(url_for('runs_history', **redirect_args))

    except (ValueError, TypeError):
        conn.close()
        if is_ajax:
            return jsonify({"success": False, "error": "Invalid input — please check your distance and duration."}), 400
        flash("Invalid input — please check your distance and duration.", "error")
        return redirect(url_for('runs_history', range=request.form.get('filter_range', '')))


@app.route('/delete_run/<int:run_id>', methods=['POST'])
@login_required
def delete_run(run_id):
    conn = get_db()
    user_id = session["user_id"]
    run = conn.execute(
        "SELECT id FROM runs WHERE id = %s AND user_id = %s", (run_id, user_id)
    ).fetchone()
    if run:
        conn.execute("DELETE FROM runs WHERE id = %s", (run_id,))
        conn.commit()
        conn.close()
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return {"success": True}
        return redirect(url_for('log_run'))
    conn.close()
    return {"success": False, "error": "Run not found"}, 404


@app.route('/wins')
@login_required
def wins():
    conn = get_db()
    user_id = session["user_id"]
    
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_last_week = start_of_week - timedelta(days=7)
    seven_days_ago = today - timedelta(days=7)

    wins_rows = conn.execute(
        "SELECT id, category, entry, date FROM wins WHERE user_id = %s ORDER BY date DESC, id DESC",
        (user_id,)
    ).fetchall()
    
    streak_count = 0
    groups = []
    current_week_wins = []
    last_week_wins = []
    older_wins = defaultdict(list)
    
    for w in wins_rows:
        win_dict = dict(w)
        win_date = win_dict.get('date')
        if isinstance(win_date, str):
            try:
                win_date = datetime.strptime(win_date, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                win_date = today
        elif isinstance(win_date, datetime):
            win_date = win_date.date()
        elif not isinstance(win_date, date):
            win_date = today
            
        if win_date >= seven_days_ago:
            streak_count += 1
            
        if win_date >= start_of_week:
            current_week_wins.append(win_dict)
        elif win_date >= start_of_last_week:
            last_week_wins.append(win_dict)
        else:
            month_label = win_date.strftime('%B %Y')
            older_wins[month_label].append(win_dict)
            
    if current_week_wins:
        groups.append({'label': 'This week', 'entries': current_week_wins})
    if last_week_wins:
        groups.append({'label': 'Last week', 'entries': last_week_wins})
        
    # Sort older month labels (B Y) properly
    sorted_months = sorted(older_wins.keys(), key=lambda l: datetime.strptime(l, '%B %Y'), reverse=True)
    for label in sorted_months:
        groups.append({'label': label, 'entries': older_wins[label]})
        
    conn.close()
    return render_template('wins.html', 
                         groups=groups, 
                         streak_count=streak_count,
                         today_str=today.isoformat(),
                         page='wins')

@app.route('/wins/create', methods=['POST'])
@login_required
def create_win():
    user_id = session["user_id"]
    category = request.form.get('category')
    entry = request.form.get('entry')
    date_str = request.form.get('date') or date.today().isoformat()
    
    if not category or not entry:
        flash("Category and description are required", "error")
        return redirect(url_for('wins'))
        
    conn = get_db()
    conn.execute(
        "INSERT INTO wins (user_id, category, entry, date) VALUES (%s, %s, %s, %s)",
        (user_id, category, entry, date_str)
    )
    conn.commit()
    conn.close()
    
    return redirect(url_for('wins'))

@app.route('/wins/<int:win_id>/delete', methods=['POST'])
@login_required
def delete_win(win_id):
    user_id = session["user_id"]
    conn = get_db()
    conn.execute("DELETE FROM wins WHERE id = %s AND user_id = %s", (win_id, user_id))
    conn.commit()
    conn.close()
    return redirect(url_for('wins'))


@app.route('/progress')
@login_required
def progress():
    conn = get_db()
    user_id = session["user_id"]

    selected_exercise_name = request.args.get('exercise', '').strip() or None

    lift_sessions    = fetch_user_sessions(conn, user_id, limit=None, order_desc=False)
    workout_sessions = fetch_workout_sessions_as_lifts(conn, user_id, limit=None, order_desc=False)

    # Merge and sort by date ascending (progress page needs chronological order)
    sessions = sorted(lift_sessions + workout_sessions, key=lambda s: str(s['date']))

    if not sessions:
        conn.close()
        return render_template(
            'progress.html',
            exercise_insights=[],
            progress_overview=None,
            pr_gallery=None,
            selected_exercise=None,
            selected_exercise_name=None,
            progress_page_data={"selectedExercise": None, "exercises": {}}
        )

    # Group by exercise
    exercises_data = defaultdict(list)
    for lift in sessions:
        exercises_data[lift['exercise']].append(lift)

    # Process each exercise
    exercise_insights = []
    progress_exercises = {}
    all_training_days = set()
    total_volume = 0

    for exercise, lift_sessions in exercises_data.items():
        sessions_sorted = sorted(lift_sessions, key=_progress_session_sort_key)
        sessions_count = len(lift_sessions)
        best_lift = max(sessions_sorted, key=lambda x: (x.get('session_value') or 0, _progress_session_sort_key(x)))
        latest_lift = sessions_sorted[-1]
        recent_sessions = list(reversed(sessions_sorted[-5:]))

        progress_exercises[exercise] = {
            'exercise': exercise,
            'exercise_label': exercise.title(),
            'sessions_count': sessions_count,
            'sessions_needed': max(0, 5 - sessions_count),
            'locked': sessions_count < 5,
            'best_lift': serialize_progress_lift(best_lift),
            'current_lift': serialize_progress_lift(latest_lift),
            'recent_sessions': [serialize_progress_lift(session) for session in recent_sessions],
            'chart_values': [session.get('session_value') for session in sessions_sorted],
            'chart_dates': [format_progress_date(session['date']) for session in sessions_sorted],
            'trend': build_progress_trend(sessions_sorted),
            'rm_profile': build_estimated_rm_profile(sessions_sorted),
        }

        for lift_session in sessions_sorted:
            day_value = str(lift_session['date']).split(' ')[0]
            all_training_days.add(day_value)
            for set_entry in lift_session.get('sets', []):
                try:
                    total_volume += float(set_entry['weight_kg']) * int(set_entry['reps'])
                except (TypeError, ValueError, KeyError):
                    continue

        exercise_insights.append({
            'exercise': exercise,
            'sessions_count': sessions_count,
            'best_lift': serialize_progress_lift(best_lift),
            'latest_lift': serialize_progress_lift(latest_lift),
        })

    # Sort by session count (most sessions first)
    exercise_insights.sort(key=lambda x: x['sessions_count'], reverse=True)

    # Robust exercise selection
    if not selected_exercise_name and exercise_insights:
        selected_exercise_name = exercise_insights[0]['exercise']

    selected_exercise = None
    if selected_exercise_name:
        # Try exact match first
        selected_exercise = progress_exercises.get(selected_exercise_name)
        
        # If not found, try case-insensitive match
        if not selected_exercise:
            search_name = selected_exercise_name.lower().strip()
            for name, data in progress_exercises.items():
                if name.lower().strip() == search_name:
                    selected_exercise = data
                    selected_exercise_name = name # Use the actual name from our dict
                    break

    # Better highlights for the overview
    most_trained = exercise_insights[0] if exercise_insights else None
    
    # Heaviest lift: Absolute max weight lifted for 1+ reps
    heaviest_lift = None
    if sessions:
        valid_lifts = [s for s in sessions if s.get('weight_kg')]
        if valid_lifts:
            heaviest_lift = max(valid_lifts, key=lambda x: (x['weight_kg'], _progress_session_sort_key(x)))
    
    # Latest lift: Most recent session
    latest_lift = sessions[-1] if sessions else None

    progress_overview = {
        'performance_highlights': [
            {
                'label': 'Sessions',
                'value': len(sessions),
                'detail': 'Lift sessions recorded'
            },
            {
                'label': 'Training days',
                'value': len(all_training_days),
                'detail': 'Unique days logged'
            },
            {
                'label': 'Exercises',
                'value': len(exercise_insights),
                'detail': 'Movements tracked'
            },
            {
                'label': 'Total Volume',
                'value': f"{format_weight(total_volume)}kg",
                'detail': 'Total kg moved'
            },
        ],
        'training_summaries': []
    }

    if most_trained:
        progress_overview['training_summaries'].append({
            'label': 'Most trained',
            'value': most_trained['exercise'].title(),
            'detail': f"{most_trained['sessions_count']} logged sessions"
        })
    
    if heaviest_lift:
        progress_overview['training_summaries'].append({
            'label': 'Heaviest lift',
            'value': f"{format_weight(heaviest_lift['weight_kg'])}kg",
            'detail': f"{heaviest_lift['exercise'].title()} • {format_progress_date(heaviest_lift['date'])}"
        })

    if latest_lift:
        progress_overview['training_summaries'].append({
            'label': 'Latest workout',
            'value': latest_lift['exercise'].title(),
            'detail': f"{format_progress_date(latest_lift['date'])} • {format_weight(latest_lift.get('weight_kg'))}kg"
        })

    pr_gallery = build_pr_gallery(sessions)

    progress_page_data = {
        'selectedExercise': selected_exercise_name,
        'exercises': progress_exercises,
    }

    conn.close()

    return render_template(
        'progress.html',
        exercise_insights=exercise_insights,
        progress_overview=progress_overview,
        pr_gallery=pr_gallery,
        selected_exercise=selected_exercise,
        selected_exercise_name=selected_exercise_name,
        progress_page_data=progress_page_data,
        page='progress'
    )


# Load exercise cache at startup
try:
    load_exercises_from_db()
except Exception as e:
    print(f"⚠️ Could not load exercise cache: {e}")


if __name__ == "__main__":
    app.run()