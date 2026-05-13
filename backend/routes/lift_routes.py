from flask import Blueprint, request, session, redirect, url_for, render_template, flash, jsonify
from datetime import date
from db import get_db
from utils.auth import login_required
from utils.request_parsing import _extract_session_payload
from utils.progress_math import build_pr_gallery
from services.lift_service import log_lift_service, serialize_progress_lift, fetch_user_sessions
from exercises import get_all_exercises
from utils.insights import generate_lift_insight

lift_bp = Blueprint('lift', __name__)

@lift_bp.route('/lifts', methods=['GET', 'POST'])
@login_required
def log_lifts():
    user_id = session["user_id"]
    
    if request.method == 'POST':
        payload = _extract_session_payload(request)
        result, error = log_lift_service(user_id, payload)
        
        if error:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "error": error}), 400
            flash(error, "error")
            return redirect(url_for('lift.log_lifts'))

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            is_first_time = result.get('prev_data') is None
            insight, emoji = generate_lift_insight(result['current_session'], result.get('is_pr', False), is_first_time)
            current_session = result['current_session']
            
            return jsonify({
                "success": True,
                "session": serialize_progress_lift(current_session),
                "is_pr": result.get('is_pr', False),
                "is_first_time": is_first_time,
                "insight": insight,
                "emoji": emoji
            })

        flash("Lift logged successfully!", "success")
        return redirect(url_for('lift.log_lifts'))

    # GET request - show PRs
    conn = get_db()
    try:
        prs = build_pr_gallery(fetch_user_sessions(conn, user_id, limit=None, order_desc=True))
        prs_recent = sorted(prs['entries'], key=lambda x: x['date'], reverse=True)[:6]
        prs_truncated = len(prs['entries']) > 6
        
        return render_template(
            "log_lifts.html",
            prs=prs,
            prs_recent=prs_recent,
            prs_truncated=prs_truncated,
            exercises=get_all_exercises(),
            today_date=date.today().isoformat()
        )
    finally:
        conn.close()

@lift_bp.route('/lifts/history')
@login_required
def lift_history():
    conn = get_db()
    user_id = session["user_id"]
    try:
        current_range = request.args.get('range', '')
        current_exercise = request.args.get('exercise', '')
        
        sessions = fetch_user_sessions(
            conn, user_id, 
            exercise=current_exercise if current_exercise else None,
            date_range=current_range if current_range else None,
            limit=None, 
            order_desc=True
        )
        
        # Get only exercises actually logged by this user for the filter dropdown
        logged_exercises_rows = conn.execute("""
            SELECT DISTINCT e.name
            FROM lift_sessions ls
            JOIN exercises e ON ls.exercise_id = e.id
            WHERE ls.user_id = %s
            ORDER BY e.name
        """, (user_id,)).fetchall()
        filter_exercises = [row['name'] for row in logged_exercises_rows]
        
        from collections import OrderedDict
        grouped = OrderedDict()
        for s in sessions:
            date_str = str(s.get('date'))
            if date_str not in grouped:
                grouped[date_str] = []
            grouped[date_str].append(s)
            
        return render_template(
            'lifts_history.html', 
            grouped=grouped, 
            current_range=current_range,
            current_exercise=current_exercise,
            filter_exercises=filter_exercises,
            exercises=get_all_exercises(),
            page='history'
        )
    finally:
        conn.close()

@lift_bp.route('/exercise_recent_performance')
@login_required
def exercise_recent_performance():
    exercise_name = request.args.get('name')
    if not exercise_name:
        return jsonify({'entries': []})

    conn = get_db()
    user_id = session["user_id"]
    
    # Fetch only the single most recent session for this exercise
    recent_sessions = fetch_user_sessions(conn, user_id, exercise=exercise_name, limit=1, order_desc=True)
    conn.close()
    
    if not recent_sessions:
        return jsonify({'entries': []})

    # Show all sets from that single last session
    last_session = recent_sessions[0]
    sets = last_session.get('sets') or []
    
    entries = []
    for s in sets:
        entries.append({
            'display': f"{s['weight_kg']}kg × {s['reps']}"
        })
            
    return jsonify({'entries': entries})

@lift_bp.route('/delete_lift/<int:lift_id>', methods=['POST'])
@login_required
def delete_lift(lift_id):
    conn = get_db()
    user_id = session["user_id"]
    
    # Check ownership
    ls = conn.execute("SELECT id FROM lift_sessions WHERE id = %s AND user_id = %s", (lift_id, user_id)).fetchone()
    if not ls:
        conn.close()
        return jsonify({"success": False, "error": "Lift not found"}), 404
        
    conn.execute("DELETE FROM lift_sessions WHERE id = %s", (lift_id,))
    conn.commit()
    conn.close()
    
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True})
        
    flash("Lift deleted", "success")
    return redirect(url_for('lift.lift_history'))

@lift_bp.route('/lifts/<int:lift_id>/edit', methods=['POST'])
@login_required
def edit_lift(lift_id):
    conn = get_db()
    user_id = session["user_id"]
    
    # Check ownership
    ls = conn.execute("SELECT id FROM lift_sessions WHERE id = %s AND user_id = %s", (lift_id, user_id)).fetchone()
    if not ls:
        conn.close()
        return jsonify({"success": False, "error": "Lift not found"}), 404
        
    try:
        exercise_name = request.form.get("exercise")
        lift_date = request.form.get("date")
        notes = request.form.get("notes")
        weights = request.form.getlist("weight_kg[]")
        reps = request.form.getlist("reps[]")
        
        from exercises import resolve_exercise
        ex_id, ex_name = resolve_exercise(conn, exercise_name)
        
        conn.execute("""
            UPDATE lift_sessions SET exercise_id = %s, date = %s, notes = %s 
            WHERE id = %s
        """, (ex_id, lift_date, notes, lift_id))
        
        # Delete old sets and insert new ones
        conn.execute("DELETE FROM lift_sets WHERE lift_session_id = %s", (lift_id,))
        for i in range(len(weights)):
            w = float(weights[i]) if weights[i] else 0
            r = int(reps[i]) if reps[i] else 0
            conn.execute("""
                INSERT INTO lift_sets (lift_session_id, weight_kg, reps, order_index)
                VALUES (%s, %s, %s, %s)
            """, (lift_id, w, r, i))
            
        conn.commit()
        
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": True})
            
        flash("Lift updated", "success")
        return redirect(url_for('lift.lift_history'))
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()
