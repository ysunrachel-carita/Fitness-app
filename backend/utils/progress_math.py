from datetime import date, datetime
from collections import defaultdict
from utils.formatting import (
    format_weight, format_rep_label, format_progress_date,
    format_pace, format_duration, format_distance, _pace_seconds_per_km
)

RECENT_DAYS = 90

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
    if r > 20:
        return w
    if r == 1:
        return w
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
    best_actuals = {}
    for point in recent_points:
        r = point['reps']
        if 1 <= r <= 20:
            if r not in best_actuals or point['weight_kg'] > best_actuals[r]['weight_kg']:
                best_actuals[r] = point
    rm_profile = []
    for target_rm in range(1, 6):
        actual = best_actuals.get(target_rm)
        estimated_val = estimate_rep_max_from_one_rm(best_one_rm_value, target_rm)
        use_actual = False
        if actual:
            if estimated_val is None or actual['weight_kg'] >= (estimated_val * 0.9):
                use_actual = True
        if use_actual and actual:
            rm_profile.append({
                'rm': target_rm, 'value': float(actual['weight_kg']),
                'display': f"{format_weight(actual['weight_kg'])}kg",
                'kind': 'actual', 'date': actual['date'],
                'date_label': actual['date_label'],
                'meta': _format_rm_point_meta(actual, target_rm=target_rm, kind='actual'),
            })
        elif estimated_val is not None:
            rm_profile.append({
                'rm': target_rm, 'value': float(estimated_val),
                'display': f"{format_weight(estimated_val)}kg",
                'kind': 'estimated', 'date': best_source['date'],
                'date_label': best_source['date_label'],
                'meta': _format_rm_point_meta(best_source, target_rm=target_rm, kind='estimated'),
            })
        else:
            rm_profile.append({
                'rm': target_rm, 'value': 0, 'display': '-', 'kind': 'estimated',
                'date': '-', 'date_label': '-', 'meta': '-',
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
                'exercise': exercise, 'exercise_label': exercise.title(),
                'weight_kg': weight_value, 'weight_display': f"{format_weight(weight_value)}kg",
                'date': session['date'], 'date_label': format_progress_date(session['date']),
                'reps': reps_value, 'sets': 1,
                'session_set_count': session.get('set_count', len(session.get('sets', []))),
                'notes': set_entry.get('notes') or session.get('notes'),
                'lift_session_id': session['id'], 'set_order_index': set_entry.get('order_index', 0),
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
            {'label': 'PRs tracked', 'value': len(entries), 'detail': 'Exercises with best lifts'},
            {'label': 'Heaviest PR', 'value': heaviest_pr['weight_display'] if heaviest_pr else '-', 'detail': heaviest_pr['exercise_label'] if heaviest_pr else 'No records yet'},
            {'label': 'Most recent PR', 'value': most_recent_pr['exercise_label'] if most_recent_pr else '-', 'detail': most_recent_pr['date_label'] if most_recent_pr else 'No records yet'},
        ],
        'heaviest_pr_exercise': heaviest_pr['exercise'] if heaviest_pr else None,
    }

def build_progress_trend(sessions_sorted):
    if len(sessions_sorted) < 5:
        return {'status': 'locked', 'improvement': 0, 'label': 'Locked'}
    
    last_5 = sessions_sorted[-5:]
    first_val = last_5[0].get('session_value') or 0
    last_val = last_5[-1].get('session_value') or 0
    
    if first_val <= 0:
        return {'status': 'neutral', 'improvement': 0, 'label': 'No Change'}
    
    improvement = ((last_val - first_val) / first_val) * 100
    if improvement > 1:
        return {'status': 'improving', 'improvement': round(improvement, 1), 'label': 'Improving'}
    elif improvement < -1:
        return {'status': 'declining', 'improvement': round(improvement, 1), 'label': 'Declining'}
def _enrich_run(row):
    """Add computed display fields to a run row dict."""
    r = dict(row)
    r['pace_display'] = format_pace(r['time_seconds'], r['distance_km'], r.get('unit', 'km'))
    r['duration_display'] = format_duration(r['time_seconds'])
    r['distance_display'] = format_distance(r['distance_km'], r.get('unit', 'km'))
    r['distance_input_value'] = round(r['distance_km'] / 1.60934, 2) if r.get('unit', 'km') == 'mi' else round(r['distance_km'], 2)
    r['duration_minutes_value'] = int(r['time_seconds'] // 60)
    r['time_seconds_value'] = int(r['time_seconds'] % 60)
    r['pace_seconds_per_km'] = _pace_seconds_per_km(r['time_seconds'], r['distance_km'])
    return r
