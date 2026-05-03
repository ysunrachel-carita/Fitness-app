from datetime import date, timedelta
from services.lift_service import fetch_user_sessions
from services.run_service import get_user_runs

def fetch_dashboard_activities(conn, user_id):
    activities = []
    active_dates = set()

    # 1. Lifts
    lifts = fetch_user_sessions(conn, user_id, limit=30, order_desc=True)
    for lift in lifts:
        date_str = str(lift['date'])
        active_dates.add(date_str)
        activities.append({
            'type': 'lift',
            'date': date_str,
            'title': lift['exercise'],
            'subtitle': lift.get('summary_label', ''),
            'detail': {
                'sets': [
                    {'set_num': i+1, 'weight': s.get('weight_kg'), 'reps': s.get('reps')}
                    for i, s in enumerate(lift.get('sets', []))
                ],
                'notes': lift.get('notes')
            }
        })

    # 2. Runs
    runs = get_user_runs(user_id)
    for r in runs:
        date_str = str(r['date'])
        active_dates.add(date_str)
        activities.append({
            'type': 'run',
            'date': date_str,
            'title': r.get('type', 'Run'),
            'subtitle': r.get('distance_display', ''),
            'detail': {
                'distance': r.get('distance_display', ''),
                'duration': r.get('duration_display', ''),
                'pace': r.get('pace_display', ''),
                'notes': r.get('notes')
            }
        })

    # 3. Workouts
    ws_rows = conn.execute("""
        SELECT ws.id, ws.date, ws.title, ws.notes,
               COUNT(DISTINCT sg.id) AS group_count
        FROM workout_sessions ws
        LEFT JOIN set_groups sg ON sg.workout_session_id = ws.id
        WHERE ws.user_id = %s
        GROUP BY ws.id
        ORDER BY ws.date DESC LIMIT 30
    """, (user_id,)).fetchall()

    for row in ws_rows:
        date_str = str(row['date'])
        active_dates.add(date_str)
        ws_id = row['id']
        
        # Get groups and components
        groups = conn.execute("""
            SELECT sg.id, sg.order_index
            FROM set_groups sg
            WHERE sg.workout_session_id = %s
            ORDER BY sg.order_index
        """, (ws_id,)).fetchall()
        
        groups_list = []
        for g in groups:
            comps = conn.execute("""
                SELECT e.name AS exercise, sc.reps, sc.weight_kg
                FROM set_components sc
                JOIN exercises e ON sc.exercise_id = e.id
                WHERE sc.set_group_id = %s
                ORDER BY sc.order_index
            """, (g['id'],)).fetchall()
            groups_list.append([
                {
                    'exercise': c['exercise'],
                    'weight': c['weight_kg'],
                    'reps': c['reps']
                } for c in comps
            ])
            
        activities.append({
            'type': 'workout',
            'date': date_str,
            'title': row['title'] or 'Untitled Workout',
            'subtitle': f"{row['group_count']} groups",
            'detail': {
                'groups': groups_list,
                'notes': row['notes']
            }
        })

    # Sort activities newest first
    activities.sort(key=lambda x: x['date'], reverse=True)

    # Calculate unique active days in the last 7 days
    seven_days_ago = (date.today() - timedelta(days=7)).isoformat()
    weekly_count = sum(1 for d in active_dates if d >= seven_days_ago)

    return activities[:20], weekly_count
