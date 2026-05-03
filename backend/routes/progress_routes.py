from flask import Blueprint, request, session, render_template
from db import get_db
from utils.auth import login_required
from exercises import get_all_exercises, resolve_exercise
from services.lift_service import fetch_all_progress_sessions, build_progress_trend
from utils.progress_math import build_pr_gallery, build_estimated_rm_profile
from utils.formatting import format_weight, format_progress_date
from collections import defaultdict

progress_bp = Blueprint('progress', __name__)

@progress_bp.route('/progress')
@login_required
def progress():
    conn = get_db()
    user_id = session["user_id"]
    
    selected_exercise_name = request.args.get('exercise', 'Back Squat')
    _, selected_exercise = resolve_exercise(conn, selected_exercise_name)
    
    all_sessions = fetch_all_progress_sessions(conn, user_id)
    
    sessions_by_ex = defaultdict(list)
    for s in all_sessions:
        sessions_by_ex[s['exercise']].append(s)
        
    exercise_insights = []
    progress_page_data = {
        "selectedExercise": selected_exercise,
        "exercises": {}
    }
    
    for ex_name, ex_sessions in sessions_by_ex.items():
        ex_sessions_asc = list(reversed(ex_sessions))
        
        rm_profile = build_estimated_rm_profile(ex_sessions)
        trend = build_progress_trend(ex_sessions_asc)
        
        lift_count = sum(1 for s in ex_sessions if s.get('source') == 'lift')
        workout_count = sum(1 for s in ex_sessions if s.get('source') == 'workout')
        
        chart_values = []
        chart_dates = []
        for s in ex_sessions_asc[-10:]:
            val = s.get('session_value')
            if val is not None:
                chart_values.append(val)
                chart_dates.append(s.get('date_label'))
                
        sessions_list = []
        for s in ex_sessions:
            sessions_list.append({
                'date': s.get('date'),
                'date_label': s.get('date_label', '-'),
                'summary_label': s.get('summary_label', '-'),
                'weight_display': s.get('weight_display', '-'),
                'reps': s.get('reps', '-'),
                'source': s.get('source', 'lift'),
                'notes': s.get('notes')
            })
            
        insight = {
            'exercise': ex_name,
            'exercise_label': ex_name.title(),
            'sessions_count': len(ex_sessions),
            'lift_count': lift_count,
            'workout_count': workout_count,
            'rm_profile': rm_profile,
            'trend': trend,
            'current_lift': {
                'weight_display': ex_sessions[0].get('weight_display', '-'),
                'date_label': ex_sessions[0].get('date_label', '-'),
                'summary_label': ex_sessions[0].get('summary_label', '-')
            },
            'locked': trend.get('locked', False),
            'sessions_needed': max(0, 5 - len(ex_sessions)),
            'chart_values': chart_values,
            'chart_dates': chart_dates,
            'sessions_list': sessions_list
        }
        
        exercise_insights.append(insight)
        progress_page_data["exercises"][ex_name] = insight
        
    exercise_insights.sort(key=lambda x: x['exercise_label'])
    
    pr_gallery = build_pr_gallery(all_sessions)

    conn.close()
    
    return render_template(
        'progress.html',
        exercise_insights=exercise_insights,
        progress_page_data=progress_page_data,
        pr_gallery=pr_gallery,
        selected_exercise=progress_page_data["exercises"].get(selected_exercise),
        selected_exercise_name=selected_exercise,
        exercises=get_all_exercises(),
        page='progress'
    )
