from flask import Blueprint, request, session, redirect, url_for, render_template, flash, jsonify
from datetime import date
from db import get_db
from utils.auth import login_required
from utils.request_parsing import _extract_session_payload
from utils.progress_math import build_pr_gallery
from services.lift_service import log_lift_service, serialize_progress_lift, fetch_user_sessions
from exercises import get_all_exercises

lift_bp = Blueprint('lift', __name__)

@lift_bp.route('/lifts', methods=['GET', 'POST'])
@login_required
def log_lifts():
    conn = get_db()
    user_id = session["user_id"]
    
    if request.method == 'POST':
        payload = _extract_session_payload(request)
        result, error = log_lift_service(user_id, payload)
        
        if error:
            flash(error, "error")
            return redirect(url_for('lift.log_lifts'))

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            current_session = result['current_session']
            from utils.insights import generate_lift_insight
            insight, emoji = generate_lift_insight(current_session, result['prev_data'])
            
            return jsonify({
                "success": True,
                "session": serialize_progress_lift(current_session),
                "previous": result['prev_data'],
                "insight": insight,
                "emoji": emoji,
                "is_pr": result.get('is_pr', False)
            })

        flash("Lift logged successfully!", "success")
        return redirect(url_for('lift.log_lifts'))

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
        exercises=get_all_exercises(),
        today_date=date.today().isoformat()
    )

@lift_bp.route('/lifts/history')
@login_required
def lift_history():
    conn = get_db()
    user_id = session["user_id"]
    sessions = fetch_user_sessions(conn, user_id, limit=None, order_desc=True)
    conn.close()
    
    from collections import OrderedDict
    grouped = OrderedDict()
    for s in sessions:
        date_str = str(s.get('date'))
        if date_str not in grouped:
            grouped[date_str] = []
        grouped[date_str].append(s)
        
    return render_template('lifts_history.html', grouped=grouped, page='history')

@lift_bp.route('/exercise_recent_performance')
@login_required
def exercise_recent_performance():
    exercise_name = request.args.get('name')
    if not exercise_name:
        return jsonify({'entries': []})

    conn = get_db()
    user_id = session["user_id"]
    
    # fetch_user_sessions is already imported from lift_service
    recent_sessions = fetch_user_sessions(conn, user_id, exercise=exercise_name, limit=3, order_desc=True)
    conn.close()
    
    entries = []
    for s in recent_sessions:
        if s.get('best_set'):
            bs = s['best_set']
            entries.append({
                'display': f"{bs['weight_kg']}kg × {bs['reps']}"
            })
            
    return jsonify({'entries': entries})
