import sqlite3
from datetime import datetime, timedelta

def _get_conn(conn):
    if conn:
        return conn
    c = sqlite3.connect('fitness.db')
    c.row_factory = sqlite3.Row
    return c

def weekly_volume_spike(user_id, conn=None):
    c = _get_conn(conn)
    cursor = c.cursor()
    today = datetime.now()
    cur_start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    prev_start = (today - timedelta(days=14)).strftime("%Y-%m-%d")
    
    # lift volume
    cursor.execute('''
        SELECT 
            SUM(CASE WHEN s.date >= ? THEN e.weight_kg * e.reps ELSE 0 END) as cur_lift,
            SUM(CASE WHEN s.date >= ? AND s.date < ? THEN e.weight_kg * e.reps ELSE 0 END) as prev_lift
        FROM exercise_sessions s
        JOIN set_entries e ON s.id = e.session_id
        WHERE s.user_id = ? AND s.date >= ?
    ''', (cur_start, prev_start, cur_start, user_id, prev_start))
    lift_row = cursor.fetchone()
    cur_lift = lift_row['cur_lift'] or 0 if lift_row else 0
    prev_lift = lift_row['prev_lift'] or 0 if lift_row else 0

    # run volume
    cursor.execute('''
        SELECT 
            SUM(CASE WHEN date >= ? THEN distance_km ELSE 0 END) as cur_run,
            SUM(CASE WHEN date >= ? AND date < ? THEN distance_km ELSE 0 END) as prev_run
        FROM runs
        WHERE user_id = ? AND date >= ?
    ''', (cur_start, prev_start, cur_start, user_id, prev_start))
    run_row = cursor.fetchone()
    cur_run = run_row['cur_run'] or 0 if run_row else 0
    prev_run = run_row['prev_run'] or 0 if run_row else 0

    # wod volume
    cursor.execute('''
        SELECT 
            SUM(CASE WHEN date >= ? THEN 1 ELSE 0 END) as cur_wod,
            SUM(CASE WHEN date >= ? AND date < ? THEN 1 ELSE 0 END) as prev_wod
        FROM wods
        WHERE user_id = ? AND date >= ?
    ''', (cur_start, prev_start, cur_start, user_id, prev_start))
    wod_row = cursor.fetchone()
    cur_wod = wod_row['cur_wod'] or 0 if wod_row else 0
    prev_wod = wod_row['prev_wod'] or 0 if wod_row else 0

    messages = []
    
    if prev_lift > 0:
        spike = (cur_lift - prev_lift) / prev_lift * 100
        if spike > 0:
            messages.append(f"Lifting volume increased by {int(spike)}%")
            
    if prev_run > 0:
        spike = (cur_run - prev_run) / prev_run * 100
        if spike > 0:
            messages.append(f"Running volume increased by {int(spike)}%")
            
    if prev_wod > 0:
        spike = (cur_wod - prev_wod) / prev_wod * 100
        if spike > 0:
            messages.append(f"WOD volume increased by {int(spike)}%")

    flag = len(messages) > 0
    return {
        'flag': flag,
        'severity': 'alert' if flag else 'normal',
        'message': ', '.join(messages)
    }

def recovery_flags(user_id, conn=None):
    c = _get_conn(conn)
    cursor = c.cursor()
    today = datetime.now()
    
    # 1. Consecutive high intensity
    cursor.execute('''
        SELECT s.date 
        FROM exercise_sessions s
        JOIN set_entries e ON s.id = e.session_id
        WHERE s.user_id = ? AND e.rpe >= 8
        UNION
        SELECT date FROM wods WHERE user_id = ?
    ''', (user_id, user_id))
    hi_days = sorted(list(set([row[0] for row in cursor.fetchall()])))
    
    consecutive = False
    for i in range(1, len(hi_days)):
        d1 = datetime.strptime(hi_days[i-1], "%Y-%m-%d")
        d2 = datetime.strptime(hi_days[i], "%Y-%m-%d")
        if (d2 - d1).days == 1:
            consecutive = True
            break
            
    if consecutive:
        return {'flag': True, 'severity': 'alert', 'message': 'High intensity on consecutive days'}
        
    # 2. Overtraining (>= 6 days out of last 7)
    week_ago = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    cursor.execute('''
        SELECT date FROM exercise_sessions WHERE user_id = ? AND date >= ?
        UNION
        SELECT date FROM runs WHERE user_id = ? AND date >= ?
        UNION
        SELECT date FROM wods WHERE user_id = ? AND date >= ?
    ''', (user_id, week_ago, user_id, week_ago, user_id, week_ago))
    
    training_days = [row[0] for row in cursor.fetchall()]
    num_days = len(set(training_days))
    
    if num_days >= 6:
        return {'flag': True, 'severity': 'warning', 'message': f'Trained {num_days} days in the last week'}
        
    return {'flag': False, 'severity': 'normal', 'message': ''}

def pr_staleness(user_id, conn=None):
    c = _get_conn(conn)
    cursor = c.cursor()
    today = datetime.now()
    d56 = (today - timedelta(days=56)).strftime("%Y-%m-%d")
    d60 = (today - timedelta(days=60)).strftime("%Y-%m-%d")
    
    cursor.execute('''
        SELECT exercise_id, count(*) as cnt
        FROM exercise_sessions
        WHERE user_id = ? AND date >= ?
        GROUP BY exercise_id
        HAVING cnt >= 8
    ''', (user_id, d56))
    frequent_exercises = cursor.fetchall()
    
    for row in frequent_exercises:
        # Handle both sqlite3.Row and psycopg2 DictRow/tuple
        if hasattr(row, 'keys'):
            ex_id = row['exercise_id']
        elif isinstance(row, (list, tuple)):
            ex_id = row[0]
        else:
            ex_id = row
        
        cursor.execute('''
            SELECT MAX(e.weight_kg) 
            FROM exercise_sessions s
            JOIN set_entries e ON s.id = e.session_id
            WHERE s.user_id = ? AND s.exercise_id = ? AND s.date >= ?
        ''', (user_id, ex_id, d60))
        recent_max = cursor.fetchone()[0] or 0
        
        cursor.execute('''
            SELECT MAX(e.weight_kg) 
            FROM exercise_sessions s
            JOIN set_entries e ON s.id = e.session_id
            WHERE s.user_id = ? AND s.exercise_id = ? AND s.date < ?
        ''', (user_id, ex_id, d60))
        old_max = cursor.fetchone()[0] or 0
        
        if old_max > recent_max:
            cursor.execute('SELECT name FROM exercises WHERE id = ?', (ex_id,))
            name = cursor.fetchone()[0]
            return {'flag': True, 'severity': 'warning', 'message': f'{name} PR is stale'}
            
    return {'flag': False, 'severity': 'normal', 'message': ''}
