from db import get_db
from utils.progress_math import _enrich_run
from utils.insights import generate_run_insight

def get_user_runs(user_id):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM runs WHERE user_id = %s ORDER BY date DESC, created_at DESC",
            (user_id,)
        ).fetchall()
        return [_enrich_run(dict(r)) for r in rows]
    finally:
        conn.close()

def log_run_service(user_id, data):
    """
    data: dict with distance, unit, run_type, duration_minutes, time_seconds, date, notes
    """
    from datetime import datetime
    distance_raw = float(data.get('distance', 0) or 0)
    unit = data.get('unit', 'km')
    run_type = data.get('run_type', 'Run').strip() or 'Run'
    dur_min = int(data.get('duration_minutes', 0) or 0)
    dur_sec = int(data.get('time_seconds', 0) or 0)
    date_str = data.get('date', '').strip() or datetime.now().strftime('%Y-%m-%d')
    notes = data.get('notes', '').strip() or None

    if distance_raw <= 0 or (dur_min == 0 and dur_sec == 0):
        return None, "Please enter a valid distance and duration."

    distance_km = distance_raw / 1.60934 if unit == 'mi' else distance_raw
    time_seconds = dur_min * 60 + dur_sec
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db()
    try:
        run_cursor = conn.execute(
            """
            INSERT INTO runs (user_id, distance_km, time_seconds, unit, run_type, date, notes, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (user_id, distance_km, time_seconds, unit, run_type, date_str, notes, created_at)
        )
        run_id = run_cursor.lastrowid
        
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

        fastest_ever = conn.execute(
            "SELECT MIN(time_seconds / distance_km) FROM runs WHERE user_id = %s AND id != %s",
            (user_id, run_id)
        ).fetchone()[0]
        
        prev_enriched = _enrich_run(dict(previous_run)) if previous_run else None
        insight, emoji, is_pb = generate_run_insight(new_run, prev_enriched, fastest_ever)

        prev_data = None
        if prev_enriched:
            prev_data = {
                'pace': prev_enriched['pace_display'],
                'distance': prev_enriched['distance_display'],
                'duration': prev_enriched['duration_display'],
                'pace_sec': prev_enriched['pace_seconds_per_km'],
            }

        conn.commit()
        return {
            'new_run': new_run,
            'previous': prev_data,
            'insight': insight,
            'emoji': emoji,
            'is_pb': is_pb
        }, None
    finally:
        conn.close()
